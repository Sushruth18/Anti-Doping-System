import json
import statistics
from datetime import date, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Athlete, Sample
from app.db.session import Base, get_db
from app.main import app

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_GROUND_TRUTH_PATH = _REPO_ROOT / "data" / "ground_truth.json"
_ATHLETES_PATH = _REPO_ROOT / "data" / "athletes.json"
_SAMPLES_PATH = _REPO_ROOT / "data" / "samples.json"


def _find_seeded_athlete_id(pattern_type: str) -> int:
    # ground_truth.json is looked up here, in the test, only to pick which
    # already-seeded athlete_id to exercise the endpoint against — the
    # endpoint itself never reads it (see CLAUDE.md's standing guardrail).
    ground_truth = json.loads(_GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    for row in ground_truth:
        if row.get("is_synthetic_anomaly") and row.get("pattern_type") == pattern_type:
            return row["athlete_id"]
    raise AssertionError(f"no seeded athlete found with pattern_type={pattern_type!r}")


@pytest.fixture()
def db_session(tmp_path):
    db_path = tmp_path / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path.as_posix()}", connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        app.dependency_overrides.clear()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    return TestClient(app)


def _seed_athlete(db_session, athlete_id: int) -> None:
    # Loads this one athlete's real generator output from data/athletes.json
    # + data/samples.json (the same files app/db/seed.py reads) into the
    # test's own throwaway DB, rather than depending on the untracked local
    # backend/app.db — keeps the test deterministic and CI-safe while still
    # exercising real seeded values, not hand-fabricated ones.
    athletes_data = json.loads(_ATHLETES_PATH.read_text(encoding="utf-8"))
    samples_data = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))

    athlete_row = next(row for row in athletes_data if row["id"] == athlete_id)
    db_session.add(Athlete(**athlete_row))

    for row in samples_data:
        if row["athlete_id"] != athlete_id:
            continue
        row = dict(row)
        row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
        db_session.add(Sample(**row))

    db_session.commit()


def test_simulation_evasion_epo_micro_dosing_smoke(client, db_session):
    athlete_id = _find_seeded_athlete_id("epo")
    _seed_athlete(db_session, athlete_id)

    response = client.get("/simulation/evasion", params={"athlete_id": athlete_id})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "athlete_id",
        "biomarker",
        "pattern",
        "sample_count",
        "single_sample_scores",
        "single_sample_flagged_any",
        "cusum_result",
        "cusum_flagged",
        "baseline_window_used",
        "detection_sample_count",
    }
    assert body["athlete_id"] == athlete_id
    assert body["biomarker"] == "hb"
    assert body["pattern"] == "micro_dosing"
    assert body["sample_count"] == len(body["single_sample_scores"])
    assert isinstance(body["single_sample_flagged_any"], bool)
    assert isinstance(body["cusum_flagged"], bool)
    assert set(body["cusum_result"].keys()) == {
        "cusum_upper",
        "cusum_lower",
        "flagged",
        "flagged_at_index",
        "threshold",
    }
    assert body["cusum_result"]["threshold"] == 5.0
    # default baseline_window=5: the earliest 5 samples are held out to
    # establish the baseline, CUSUM only runs against what's left.
    assert body["baseline_window_used"] == 5
    assert body["detection_sample_count"] == body["sample_count"] - 5
    assert len(body["cusum_result"]["cusum_upper"]) == body["detection_sample_count"]
    assert len(body["cusum_result"]["cusum_lower"]) == body["detection_sample_count"]


def test_simulation_evasion_steroid_micro_dosing_smoke(client, db_session):
    athlete_id = _find_seeded_athlete_id("steroid")
    _seed_athlete(db_session, athlete_id)

    response = client.get(
        "/simulation/evasion",
        params={"athlete_id": athlete_id, "pattern": "steroid_micro_dosing"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["athlete_id"] == athlete_id
    assert body["biomarker"] == "te_ratio"
    assert body["pattern"] == "steroid_micro_dosing"
    assert body["sample_count"] == len(body["single_sample_scores"])
    assert body["baseline_window_used"] == 5
    assert body["detection_sample_count"] == body["sample_count"] - 5


def test_simulation_evasion_unknown_athlete_404(client, db_session):
    response = client.get("/simulation/evasion", params={"athlete_id": 999999})

    assert response.status_code == 404


def test_simulation_evasion_insufficient_samples_for_baseline_split_422(client, db_session):
    # Real seeded athletes now have 8-20 samples each (post-regeneration),
    # so the thin-history case can no longer be reached by picking a
    # seeded athlete and cranking baseline_window up -- construct a
    # throwaway athlete with fewer samples than baseline_window + 3
    # requires directly. Default baseline_window=5 needs 5+3=8 samples
    # minimum; this athlete only has 3.
    athlete = Athlete(name="Insufficient Samples Athlete", sport="Cycling", age=25)
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    for i in range(3):
        db_session.add(
            Sample(
                athlete_id=athlete.id,
                date=date(2026, 1, 1 + i),
                hb=14.0,
                hct=42.0,
                ret_pct=1.5,
                off_score=66.51530771650467,
                te_ratio=1.0,
            )
        )
    db_session.commit()

    response = client.get(
        "/simulation/evasion",
        params={"athlete_id": athlete.id},
    )

    assert response.status_code == 422
    assert "insufficient samples for reliable baseline+detection split" in response.json()["detail"]


def test_simulation_evasion_default_baseline_window_is_five(client, db_session):
    # Confirms the new default (5, changed from 2) holds out samples 1-5 as
    # the CUSUM calibration window and scoring begins at sample 6 -- not
    # sample 3, which is where the old default of 2 would have started.
    athlete = Athlete(
        name="Default Baseline Window Athlete",
        sport="Cycling",
        age=25,
        baseline_prior_json=(
            '{"hb": {"mean": 15.4, "std": 0.75}, "hct": {"mean": 45.0, "std": 2.0}, '
            '"ret_pct": {"mean": 1.05, "std": 0.26}, "te_ratio": {"mean": 1.15, "std": 0.22}, '
            '"off_score": {"mean": 92.5, "std": 9.5}}'
        ),
    )
    db_session.add(athlete)
    db_session.commit()
    db_session.refresh(athlete)

    hb_values = [14.0, 14.1, 13.9, 14.05, 13.95, 16.5, 16.6, 16.7]
    for i, hb in enumerate(hb_values):
        db_session.add(
            Sample(
                athlete_id=athlete.id,
                date=date(2026, 1, 1 + i),
                hb=hb,
                hct=42.0,
                ret_pct=1.5,
                off_score=66.51530771650467,
                te_ratio=1.0,
            )
        )
    db_session.commit()

    response = client.get("/simulation/evasion", params={"athlete_id": athlete.id})

    assert response.status_code == 200
    body = response.json()
    assert body["baseline_window_used"] == 5
    assert body["detection_sample_count"] == len(hb_values) - 5
    assert len(body["cusum_result"]["cusum_upper"]) == len(hb_values) - 5
    assert len(body["cusum_result"]["cusum_lower"]) == len(hb_values) - 5

    # The held-out baseline is samples 1-5 (hb_values[:5]); CUSUM's first
    # scored point is sample 6 (hb_values[5] == 16.5), standardized against
    # that baseline mean/std -- not sample 3, which is what baseline_window=2
    # used to score first.
    baseline_slice = hb_values[:5]
    baseline_mean = statistics.mean(baseline_slice)
    baseline_std = statistics.stdev(baseline_slice)
    k = 0.5
    expected_first_z = (hb_values[5] - baseline_mean) / baseline_std
    expected_first_upper = max(0.0, expected_first_z - k)
    assert body["cusum_result"]["cusum_upper"][0] == pytest.approx(expected_first_upper)


def test_simulation_evasion_baseline_window_below_two_422(client, db_session):
    athlete_id = _find_seeded_athlete_id("epo")
    _seed_athlete(db_session, athlete_id)

    response = client.get(
        "/simulation/evasion",
        params={"athlete_id": athlete_id, "baseline_window": 1},
    )

    assert response.status_code == 422

def _seed_full_cohort(db_session) -> None:
    # Budget allocation needs many candidates to be meaningful (a single
    # athlete can't demonstrate "selection stops when the budget runs
    # out"), so this loads the whole real seeded cohort rather than one
    # athlete at a time like _seed_athlete above.
    athletes_data = json.loads(_ATHLETES_PATH.read_text(encoding="utf-8"))
    samples_data = json.loads(_SAMPLES_PATH.read_text(encoding="utf-8"))

    for row in athletes_data:
        db_session.add(Athlete(**row))
    for row in samples_data:
        row = dict(row)
        row["date"] = datetime.strptime(row["date"], "%Y-%m-%d").date()
        db_session.add(Sample(**row))

    db_session.commit()


def test_budget_recommendations_200_with_expected_keys(client, db_session):
    _seed_full_cohort(db_session)

    response = client.get("/recommendations/budget", params={"budget": 50})

    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "budget",
        "selected",
        "total_cost",
        "total_value",
        "athletes_evaluated",
        "candidates_considered",
        "candidates_selected",
    }
    assert body["budget"] == 50
    assert body["candidates_selected"] == len(body["selected"])
    if body["selected"]:
        assert set(body["selected"][0].keys()) == {
            "athlete_id",
            "name",
            "action_type",
            "value_score",
            "cost",
            "cumulative_cost_after",
            "explanation_text",
        }


def test_budget_recommendations_small_budget_caps_selection(client, db_session):
    _seed_full_cohort(db_session)

    response = client.get("/recommendations/budget", params={"budget": 2})

    assert response.status_code == 200
    body = response.json()
    # The real seeded 80-athlete cohort has well more than 2 actionable
    # recommendations (see test_action_engine.py/test_recommendations.py's
    # Logan Rossi/Indigo Berg cases, among others) -- this confirms the cap
    # is the budget doing its job, not "there just weren't more candidates."
    assert body["candidates_considered"] > 2
    assert len(body["selected"]) <= 2
    assert body["total_cost"] <= 2


@pytest.mark.parametrize("budget", [0, -5])
def test_budget_recommendations_non_positive_budget_422(client, db_session, budget):
    response = client.get("/recommendations/budget", params={"budget": budget})

    assert response.status_code == 422


def test_budget_recommendations_athletes_evaluated_vs_candidates_considered_diverge(
    client, db_session
):
    # Concrete numeric example against the real 80-athlete seeded cohort
    # (hand-confirmed by running compute_recommendation directly over
    # every seeded athlete, same as this route's own loop):
    #   80 athletes total -> all 80 have enough history to be scored at
    #   all (athletes_evaluated == 80), but 9 of them score "no_action"
    #   (nothing anomalous -> nothing to fund) and are excluded from the
    #   budget pool, leaving candidates_considered == 71. The two counts
    #   must diverge by exactly that 9, not collapse to the same number.
    _seed_full_cohort(db_session)

    response = client.get("/recommendations/budget", params={"budget": 1000})

    assert response.status_code == 200
    body = response.json()
    assert body["athletes_evaluated"] == 80
    assert body["candidates_considered"] == 71
    assert body["athletes_evaluated"] - body["candidates_considered"] == 9


def test_budget_recommendations_excludes_insufficient_history_athlete_from_both_counts(
    client, db_session
):
    _seed_full_cohort(db_session)

    baseline_response = client.get("/recommendations/budget", params={"budget": 1000})
    assert baseline_response.status_code == 200
    baseline_body = baseline_response.json()
    baseline_evaluated = baseline_body["athletes_evaluated"]
    baseline_considered = baseline_body["candidates_considered"]
    assert baseline_evaluated > 0  # non-trivial pool, not a vacuous check

    # No samples at all -- compute_recommendation returns None for this
    # athlete (insufficient_history), same case
    # test_compute_recommendation_unscored_athlete_returns_none covers
    # directly against action_engine. It was never scored at all, so it
    # must not move athletes_evaluated (unlike a real no_action result,
    # which DOES count toward athletes_evaluated but not
    # candidates_considered) or candidates_considered.
    db_session.add(Athlete(name="No Samples Athlete", sport="Cycling", age=25))
    db_session.commit()

    response = client.get("/recommendations/budget", params={"budget": 1000})

    assert response.status_code == 200
    body = response.json()
    assert body["athletes_evaluated"] == baseline_evaluated
    assert body["candidates_considered"] == baseline_considered
