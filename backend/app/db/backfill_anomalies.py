"""Backfill Anomaly rows for athletes whose existing samples were never
scored.

The only write path for Anomaly rows is POST /athletes/{id}/samples, which
only fires on new sample ingestion. Seeded athletes with pre-existing
samples (from db/seed.py, not that route) never get scored, so
GET /athletes' latest_anomaly_score stays null for the whole seeded cohort
until each athlete happens to receive a brand-new sample.

This module scores each athlete's CURRENT latest sample (no new sample
required) and persists the result the same way the POST route does. It is
idempotent — safe to run on every backend boot, chained after db/seed.py in
render.yaml's startCommand, alongside seed.py's now-symmetric anomalies
clear-and-reinsert-adjacent behavior (seed.py wipes `anomalies` on every
reseed; this module then repopulates it).
"""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from datetime import datetime

# Allow running as a plain script (`python backfill_anomalies.py`) as well
# as a module (`python -m app.db.backfill_anomalies`), same approach as
# seed.py and init_db.py.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

from sqlalchemy.orm import Session  # noqa: E402

from app.db.models import Anomaly, Athlete, Sample  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.ml.anomaly import ANOMALY_METHOD, get_anomaly_score, normalize_anomaly_score  # noqa: E402


@dataclass
class BackfillSummary:
    total_athletes: int = 0
    scored: int = 0
    already_scored: int = 0
    skipped_no_samples: int = 0
    skipped_no_baseline: int = 0
    skipped_degenerate_variance: int = 0

    def __str__(self) -> str:
        return (
            f"total_athletes={self.total_athletes} scored={self.scored} "
            f"already_scored={self.already_scored} "
            f"skipped_no_samples={self.skipped_no_samples} "
            f"skipped_no_baseline={self.skipped_no_baseline} "
            f"skipped_degenerate_variance={self.skipped_degenerate_variance}"
        )


def backfill_anomalies(db: Session) -> BackfillSummary:
    """Score every athlete's latest sample that doesn't already have an
    Anomaly row, and persist the result.

    Idempotent: dedup is scoped to the specific `sample_id`, not to "has
    this athlete ever been scored" — an athlete who later receives a
    genuinely new sample (via POST /athletes/{id}/samples or a future
    backfill run) will get that new sample scored too, building real
    history over time rather than freezing each athlete at one score.

    Skip reasons are logged as distinct counters rather than folded into
    one, since they indicate different things: `skipped_no_samples` is
    benign (seeded athlete with no samples at all), while
    `skipped_no_baseline` and `skipped_degenerate_variance` indicate a
    data-integrity problem worth a human's attention.
    """
    summary = BackfillSummary()
    athletes = db.query(Athlete).all()
    summary.total_athletes = len(athletes)

    for athlete in athletes:
        latest_sample = (
            db.query(Sample)
            .filter(Sample.athlete_id == athlete.id)
            .order_by(Sample.date.desc())
            .first()
        )
        if latest_sample is None:
            summary.skipped_no_samples += 1
            print(f"[backfill_anomalies] athlete {athlete.id}: skipped (no samples yet)")
            continue

        if not athlete.baseline_prior_json:
            summary.skipped_no_baseline += 1
            print(
                f"[backfill_anomalies] athlete {athlete.id}: skipped "
                "(missing/invalid baseline_prior_json — data integrity issue)"
            )
            continue

        already_scored = (
            db.query(Anomaly.id).filter(Anomaly.sample_id == latest_sample.id).first()
            is not None
        )
        if already_scored:
            summary.already_scored += 1
            continue

        result = get_anomaly_score(athlete.id, db)
        if result["reason"] is not None:
            # baseline_prior_json was present but scoring still failed
            # (e.g. zero/missing posterior variance for a biomarker) —
            # distinct from the two pre-checks above, so counted separately.
            summary.skipped_degenerate_variance += 1
            print(
                f"[backfill_anomalies] athlete {athlete.id}: skipped "
                f"(scoring failed: {result['reason']})"
            )
            continue

        raw_distance = result["anomaly_score"]
        db.add(
            Anomaly(
                athlete_id=athlete.id,
                sample_id=latest_sample.id,
                anomaly_score=normalize_anomaly_score(raw_distance),
                mahalanobis_distance=raw_distance,
                method=ANOMALY_METHOD,
                created_at=datetime.utcnow(),
            )
        )
        summary.scored += 1

    db.commit()
    return summary


def rescore_all_anomalies(db: Session) -> int:
    """One-time repair pass: recompute `anomaly_score` for EVERY existing
    Anomaly row from its already-persisted `mahalanobis_distance`, using
    whatever `ANOMALY_SCORE_SCALE` is currently in `app.ml.anomaly`.

    Only runs when explicitly requested (--force / FORCE_RESCORE) — see
    `run()`. Exists because `backfill_anomalies` above is intentionally
    idempotent-by-skip (dedup on `sample_id`), so rows written under a
    since-recalibrated `ANOMALY_SCORE_SCALE` are never revisited by a normal
    boot run. This does not recompute `mahalanobis_distance` itself (that
    raw-distance formula hasn't changed) and does not touch
    `normalize_anomaly_score` or the scale constant — it only reapplies the
    current scale to the existing raw distance.
    """
    anomalies = db.query(Anomaly).all()
    for anomaly in anomalies:
        anomaly.anomaly_score = normalize_anomaly_score(anomaly.mahalanobis_distance)
    db.commit()
    return len(anomalies)


def run() -> BackfillSummary:
    force = "--force" in sys.argv[1:] or os.environ.get("FORCE_RESCORE", "").lower() in (
        "1",
        "true",
        "yes",
    )

    db = SessionLocal()
    try:
        summary = backfill_anomalies(db)
        print(f"[backfill_anomalies] done: {summary}")

        if force:
            rescored = rescore_all_anomalies(db)
            print(
                f"[backfill_anomalies] --force: rescored {rescored} existing "
                "anomaly rows using the current ANOMALY_SCORE_SCALE"
            )

        return summary
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
