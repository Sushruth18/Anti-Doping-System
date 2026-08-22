"""Synthetic data generator — v1.3: variable sample counts per athlete (8-20 overall,
15-20 biased for EPO/steroid); all biomarker correlation and archetype injection logic
unchanged from v1.2."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from random import Random

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- CONFIG ---
CONFIG = {
    "n_athletes": 80,
    "n_sports": 5,
    "seed": 42,
    # v1.3: variable sample counts — draw from [n_samples_min, n_samples_max].
    # EPO and steroid athletes are drawn from [n_samples_drift_min, n_samples_max]
    # to give subtle drift patterns a longer runway to be detectable.
    "n_samples_min": 8,
    "n_samples_max": 20,
    "n_samples_drift_min": 15,   # lower bound for epo / steroid archetypes
    "samples_start_date": "2025-01-15",
    "sample_interval_days": 28,
    # AR(1) increment: epsilon_t = rho * epsilon_{t-1} + N(0, step_std)
    "walk_autocorrelation": 0.75,
    "hb_step_std": 0.12,
    "hct_step_std": 0.35,
    "ret_pct_step_std": 0.04,
    "te_ratio_step_std": 0.03,
    "hb_hct_coupling": 2.85,
    # v1.2 anomaly injection (unchanged)
    "anomaly_rate": 0.06,
    "anomaly_archetypes": ["transfusion", "epo", "steroid"],

    # Transfusion
    "transfusion_hb_spike": 1.8,
    "transfusion_hct_spike": 5.0,
    "transfusion_ret_pct_drop": 0.35,
    "transfusion_window_len": 2,

    # EPO micro-dosing
    "epo_hb_rise": 0.8,
    "epo_hct_rise": 2.0,
    "epo_ret_pct_rise": 0.20,
    "epo_te_ratio_rise": 0.05,
    "epo_window_len": 3,

    # Steroid micro-dosing
    "steroid_te_ratio_rise": 0.30,
    "steroid_hb_rise": 0.15,
    "steroid_ret_pct_drop": 0.05,
    "steroid_window_len": 2,
}

BIOMARKER_KEYS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")

# Per-sport population priors — seed the Bayesian baseline before samples exist.
SPORT_PRIORS: dict[str, dict[str, dict[str, float]]] = {
    "Cycling": {
        "hb": {"mean": 15.4, "std": 0.75},
        "hct": {"mean": 45.0, "std": 2.0},
        "ret_pct": {"mean": 1.05, "std": 0.26},
        "te_ratio": {"mean": 1.15, "std": 0.22},
    },
    "Running": {
        "hb": {"mean": 14.8, "std": 0.70},
        "hct": {"mean": 43.5, "std": 1.9},
        "ret_pct": {"mean": 1.12, "std": 0.28},
        "te_ratio": {"mean": 1.10, "std": 0.20},
    },
    "Swimming": {
        "hb": {"mean": 14.5, "std": 0.65},
        "hct": {"mean": 42.8, "std": 1.8},
        "ret_pct": {"mean": 1.08, "std": 0.27},
        "te_ratio": {"mean": 1.08, "std": 0.18},
    },
    "Rowing": {
        "hb": {"mean": 15.1, "std": 0.72},
        "hct": {"mean": 44.8, "std": 2.1},
        "ret_pct": {"mean": 1.00, "std": 0.24},
        "te_ratio": {"mean": 1.12, "std": 0.21},
    },
    "Triathlon": {
        "hb": {"mean": 14.9, "std": 0.68},
        "hct": {"mean": 44.0, "std": 1.9},
        "ret_pct": {"mean": 1.10, "std": 0.27},
        "te_ratio": {"mean": 1.10, "std": 0.20},
    },
}

SPORTS = list(SPORT_PRIORS.keys())[: CONFIG["n_sports"]]

# Physiological clamp ranges
BOUNDS = {
    "hb": (12.0, 18.0),
    "hct": (36.0, 52.0),
    "ret_pct": (0.5, 2.5),
    "te_ratio": (0.6, 2.0),
}

FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Taylor", "Casey", "Morgan", "Riley", "Quinn",
    "Avery", "Blake", "Cameron", "Dakota", "Emery", "Finley", "Gray", "Harper",
    "Indigo", "Jules", "Kai", "Logan", "Marlow", "Noel", "Oakley", "Parker",
]
LAST_NAMES = [
    "Chen", "Okonkwo", "Petrov", "Santos", "Kim", "Andersson", "Nakamura",
    "Dupont", "Silva", "Hansen", "Morales", "Nguyen", "Patel", "Rossi", "Walsh",
    "Okafor", "Berg", "Costa", "Dubois", "Eriksson", "Fischer", "Gomez", "Hayes",
    "Ivanov",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PLOT_DIR = REPO_ROOT / "ml" / "plots"
ANOMALY_PLOT_PATH = PLOT_DIR / "anomaly_check_v12.png"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

SAMPLE_FIELDS = (
    "date",
    "hb",
    "hct",
    "ret_pct",
    "off_score",
    "te_ratio",
    "competition_flag",
    "altitude_flag",
    "injury_flag",
)


def compute_off_score(hb_g_dL: float, ret_pct: float) -> float:
    """Locked formula: off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct)."""
    return (hb_g_dL * 10) - (60 * math.sqrt(ret_pct))


def sport_prior_with_off_score(sport: str) -> dict[str, dict[str, float]]:
    """Return full prior dict including derived off_score mean/std for a sport."""
    prior = {k: dict(v) for k, v in SPORT_PRIORS[sport].items()}
    off_mean = round(
        compute_off_score(prior["hb"]["mean"], prior["ret_pct"]["mean"]), 1
    )
    prior["off_score"] = {"mean": off_mean, "std": 9.5}
    return prior


def clamp(value: float, biomarker: str) -> float:
    lo, hi = BOUNDS[biomarker]
    return max(lo, min(hi, value))



def correlated_biomarker_walks(
    rng: Random,
    n_steps: int,
    sport: str,
) -> dict[str, list[float]]:
    """Generate correlated hb/hct/ret_pct/te_ratio series for one athlete.

    hb and hct share momentum (hct delta tracks hb delta). ret_pct and te_ratio
    use independent AR(1) walks with a small shared environmental shock so they
    are weakly correlated with each other but not independent noise.
    """
    prior = SPORT_PRIORS[sport]
    rho = CONFIG["walk_autocorrelation"]

    # Individual baseline offsets (correlated hb/hct draw at t=0)
    z_hb = rng.gauss(0, 1)
    z_hct = 0.85 * z_hb + 0.53 * rng.gauss(0, 1)  # correlated start
    hb0 = prior["hb"]["mean"] + z_hb * prior["hb"]["std"] * 0.35
    hct0 = prior["hct"]["mean"] + z_hct * prior["hct"]["std"] * 0.35
    ret0 = prior["ret_pct"]["mean"] + rng.gauss(0, prior["ret_pct"]["std"] * 0.35)
    te0 = prior["te_ratio"]["mean"] + rng.gauss(0, prior["te_ratio"]["std"] * 0.35)

    hb_series: list[float] = [clamp(hb0, "hb")]
    hct_series: list[float] = [clamp(hct0, "hct")]
    ret_series: list[float] = [clamp(ret0, "ret_pct")]
    te_series: list[float] = [clamp(te0, "te_ratio")]

    eps_hb = eps_hct = eps_ret = eps_te = 0.0

    for _ in range(n_steps - 1):
        shared_env = rng.gauss(0, 0.02)

        eps_hb = (rho * eps_hb) + rng.gauss(0, CONFIG["hb_step_std"])
        new_hb = clamp(hb_series[-1] + eps_hb, "hb")
        delta_hb = new_hb - hb_series[-1]

        eps_hct = (rho * eps_hct) + rng.gauss(0, CONFIG["hct_step_std"])
        # Physiology: hct moves with hb (coupled) plus its own autocorrelated noise
        new_hct = clamp(
            hct_series[-1] + (CONFIG["hb_hct_coupling"] * delta_hb) + eps_hct,
            "hct",
        )

        eps_ret = (rho * eps_ret) + rng.gauss(0, CONFIG["ret_pct_step_std"]) + shared_env
        new_ret = clamp(ret_series[-1] + eps_ret, "ret_pct")

        eps_te = (rho * eps_te) + rng.gauss(0, CONFIG["te_ratio_step_std"]) + shared_env
        new_te = clamp(te_series[-1] + eps_te, "te_ratio")

        hb_series.append(new_hb)
        hct_series.append(new_hct)
        ret_series.append(new_ret)
        te_series.append(new_te)

    return {
        "hb": [round(v, 2) for v in hb_series],
        "hct": [round(v, 2) for v in hct_series],
        "ret_pct": [round(v, 2) for v in ret_series],
        "te_ratio": [round(v, 2) for v in te_series],
    }


def generate_name(rng: Random, index: int) -> str:
    first = FIRST_NAMES[index % len(FIRST_NAMES)]
    last = LAST_NAMES[(index // len(FIRST_NAMES)) % len(LAST_NAMES)]
    suffix = (index // (len(FIRST_NAMES) * len(LAST_NAMES))) + 1
    if suffix > 1:
        return f"{first} {last} {suffix}"
    return f"{first} {last}"


def assign_sports(n_athletes: int) -> list[str]:
    """Even sport assignment across n_sports."""
    sports: list[str] = []
    for i in range(n_athletes):
        sports.append(SPORTS[i % len(SPORTS)])
    return sports


def generate_athletes(rng: Random) -> list[dict]:
    sport_assignments = assign_sports(CONFIG["n_athletes"])
    athletes = []
    for i in range(CONFIG["n_athletes"]):
        sport = sport_assignments[i]
        prior = sport_prior_with_off_score(sport)
        athletes.append(
            {
                "id": i + 1,
                "name": generate_name(rng, i),
                "sport": sport,
                "age": rng.randint(18, 35),
                "baseline_prior_json": json.dumps(prior),
            }
        )
    return athletes


def assign_sample_counts(
    rng: Random,
    athletes: list[dict],
    epo_ids: set[int],
    steroid_ids: set[int],
) -> dict[int, int]:
    """Draw a sample count for each athlete.

    EPO and steroid athletes draw from [n_samples_drift_min, n_samples_max]
    to give their gradual drift patterns a longer runway.
    Clean athletes and transfusion athletes draw from the full
    [n_samples_min, n_samples_max] range — transfusion is a sharp
    spike pattern and does not need extra length.
    """
    counts: dict[int, int] = {}
    for athlete in athletes:
        aid = athlete["id"]
        if aid in epo_ids or aid in steroid_ids:
            n = rng.randint(CONFIG["n_samples_drift_min"], CONFIG["n_samples_max"])
        else:
            n = rng.randint(CONFIG["n_samples_min"], CONFIG["n_samples_max"])
        counts[aid] = n
    return counts


def generate_samples(
    rng: Random,
    athletes: list[dict],
    sample_counts: dict[int, int],
) -> list[dict]:
    samples: list[dict] = []
    sample_id = 1
    start = date.fromisoformat(CONFIG["samples_start_date"])
    interval = timedelta(days=CONFIG["sample_interval_days"])

    for athlete in athletes:
        n = sample_counts[athlete["id"]]
        walks = correlated_biomarker_walks(rng, n, athlete["sport"])

        for step in range(n):
            hb = walks["hb"][step]
            ret_pct = walks["ret_pct"][step]
            sample_date = start + (interval * step)

            samples.append(
                {
                    "id": sample_id,
                    "athlete_id": athlete["id"],
                    "date": sample_date.isoformat(),
                    "hb": hb,
                    "hct": walks["hct"][step],
                    "ret_pct": ret_pct,
                    "off_score": round(compute_off_score(hb, ret_pct), 1),
                    "te_ratio": walks["te_ratio"][step],
                    # Context flags out of scope — all False until later tasks
                    "competition_flag": False,
                    "altitude_flag": False,
                    "injury_flag": False,
                }
            )
            sample_id += 1

    return samples


def select_anomaly_athletes(rng: Random, athlete_ids: list[int]) -> list[int]:
    """Pick ~anomaly_rate fraction of athletes for injection."""
    n_anomaly = max(1, round(CONFIG["n_athletes"] * CONFIG["anomaly_rate"]))
    n_anomaly = min(n_anomaly, len(athlete_ids))
    return sorted(rng.sample(athlete_ids, n_anomaly))


def _build_by_athlete(samples: list[dict]) -> dict[int, list[dict]]:
    """Group and sort samples by athlete_id."""
    by_athlete: dict[int, list[dict]] = {}
    for sample in samples:
        by_athlete.setdefault(sample["athlete_id"], []).append(sample)
    for rows in by_athlete.values():
        rows.sort(key=lambda s: s["date"])
    return by_athlete


def inject_transfusion_anomalies(
    rng: Random,
    samples: list[dict],
    affected: list[int],
) -> list[int]:
    """Blood-transfusion archetype: sharp hb/hct rise + ret_pct suppression.

    te_ratio is left unchanged (transfusion does not directly elevate T/E;
    steroid/EPO archetypes may touch te_ratio in later tasks).

    Returns affected athlete IDs.
    """
    if not affected:
        return []

    by_athlete = _build_by_athlete(samples)
    window_len = CONFIG["transfusion_window_len"]

    for athlete_id in affected:
        rows = by_athlete[athlete_id]
        n_steps = len(rows)   # use actual per-athlete count
        # Window starts after at least one baseline sample; fits within series
        max_start = n_steps - window_len
        start_idx = rng.randint(1, max(1, max_start))

        for offset in range(window_len):
            idx = start_idx + offset
            row = rows[idx]
            # Ramp spike within window — sharpest rise at the last window sample
            ramp = (offset + 1) / window_len
            hb_add = CONFIG["transfusion_hb_spike"] * ramp
            hct_add = CONFIG["transfusion_hct_spike"] * ramp
            ret_drop = CONFIG["transfusion_ret_pct_drop"] * ramp

            row["hb"] = round(clamp(row["hb"] + hb_add, "hb"), 2)
            row["hct"] = round(clamp(row["hct"] + hct_add, "hct"), 2)
            row["ret_pct"] = round(clamp(row["ret_pct"] - ret_drop, "ret_pct"), 2)
            # te_ratio unchanged for transfusion archetype
            row["off_score"] = round(
                compute_off_score(row["hb"], row["ret_pct"]), 1
            )

    return affected


def inject_epo_anomalies(
    rng: Random,
    samples: list[dict],
    affected: list[int],
) -> list[int]:
    """EPO micro-dosing archetype: subtle Hb/HCT/reticulocyte/T-E changes."""

    by_athlete = _build_by_athlete(samples)
    window_len = CONFIG["epo_window_len"]

    for athlete_id in affected:
        rows = by_athlete[athlete_id]
        n_steps = len(rows)   # use actual per-athlete count

        max_start = n_steps - window_len
        start_idx = rng.randint(1, max(1, max_start))

        for offset in range(window_len):
            idx = start_idx + offset
            row = rows[idx]

            ramp = (offset + 1) / window_len

            row["hb"] = round(
                clamp(
                    row["hb"] + CONFIG["epo_hb_rise"] * ramp,
                    "hb",
                ),
                2,
            )

            row["hct"] = round(
                clamp(
                    row["hct"] + CONFIG["epo_hct_rise"] * ramp,
                    "hct",
                ),
                2,
            )

            row["ret_pct"] = round(
                clamp(
                    row["ret_pct"] + CONFIG["epo_ret_pct_rise"] * ramp,
                    "ret_pct",
                ),
                2,
            )

            row["te_ratio"] = round(
                clamp(
                    row["te_ratio"] + CONFIG["epo_te_ratio_rise"] * ramp,
                    "te_ratio",
                ),
                2,
            )

            row["off_score"] = round(
                compute_off_score(row["hb"], row["ret_pct"]),
                1,
            )

    return affected


def inject_steroid_anomalies(
    rng: Random,
    samples: list[dict],
    affected: list[int],
) -> list[int]:
    """Steroid micro-dosing archetype: subtle T/E ratio elevation."""

    by_athlete = _build_by_athlete(samples)
    window_len = CONFIG["steroid_window_len"]

    for athlete_id in affected:
        rows = by_athlete[athlete_id]
        n_steps = len(rows)   # use actual per-athlete count

        max_start = n_steps - window_len
        start_idx = rng.randint(1, max(1, max_start))

        for offset in range(window_len):
            idx = start_idx + offset
            row = rows[idx]

            ramp = (offset + 1) / window_len

            row["te_ratio"] = round(
                clamp(
                    row["te_ratio"]
                    + CONFIG["steroid_te_ratio_rise"] * ramp,
                    "te_ratio",
                ),
                2,
            )

            row["hb"] = round(
                clamp(
                    row["hb"] + CONFIG["steroid_hb_rise"] * ramp,
                    "hb",
                ),
                2,
            )

            row["ret_pct"] = round(
                clamp(
                    row["ret_pct"]
                    - CONFIG["steroid_ret_pct_drop"] * ramp,
                    "ret_pct",
                ),
                2,
            )

            row["off_score"] = round(
                compute_off_score(row["hb"], row["ret_pct"]),
                1,
            )

    return affected


def write_ground_truth(
    path: Path,
    athletes: list[dict],
    transfusion_ids: list[int],
    epo_ids: list[int],
    steroid_ids: list[int],
) -> None:
    """Write per-athlete anomaly labels matching the schema.md ground_truth shape:
    [{athlete_id, is_synthetic_anomaly, pattern_type}] — one row per athlete.
    """
    anomaly_map: dict[int, str] = {}
    for aid in transfusion_ids:
        anomaly_map[aid] = "transfusion"
    for aid in epo_ids:
        anomaly_map[aid] = "epo"
    for aid in steroid_ids:
        anomaly_map[aid] = "steroid"

    rows = []
    for athlete in athletes:
        aid = athlete["id"]
        is_anomaly = aid in anomaly_map
        rows.append(
            {
                "athlete_id": aid,
                "is_synthetic_anomaly": is_anomaly,
                "pattern_type": anomaly_map.get(aid),  # None for clean athletes
            }
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2)
        f.write("\n")


def save_anomaly_comparison_plot(
    samples: list[dict],
    athletes: list[dict],
    affected_ids: list[int],
    out_path: Path,
) -> None:
    """Plot hb/hct for one affected vs one unaffected athlete."""
    if not affected_ids:
        return

    athlete_map = {a["id"]: a for a in athletes}
    by_athlete: dict[int, list[dict]] = {}
    for sample in samples:
        by_athlete.setdefault(sample["athlete_id"], []).append(sample)
    for rows in by_athlete.values():
        rows.sort(key=lambda s: s["date"])

    affected_id = affected_ids[0]
    control_id = next(aid for aid in sorted(by_athlete) if aid not in affected_ids)

    fig, axes = plt.subplots(2, 2, figsize=(10, 6), sharex="col")
    pairs = [
        (affected_id, athlete_map[affected_id]["name"], "Affected (transfusion)"),
        (control_id, athlete_map[control_id]["name"], "Unaffected (baseline)"),
    ]

    for col, (aid, name, label) in enumerate(pairs):
        rows = by_athlete[aid]
        dates = [r["date"] for r in rows]
        hb = [r["hb"] for r in rows]
        hct = [r["hct"] for r in rows]

        axes[0, col].plot(dates, hb, "o-", linewidth=2, color="#d62728" if col == 0 else "#1f77b4")
        axes[0, col].set_title(f"{label}\n{name} (id={aid})")
        axes[0, col].set_ylabel("Hb (g/dL)")
        axes[0, col].grid(True, alpha=0.3)

        axes[1, col].plot(dates, hct, "s-", linewidth=2, color="#d62728" if col == 0 else "#1f77b4")
        axes[1, col].set_ylabel("Hct (%)")
        axes[1, col].set_xlabel("Date")
        axes[1, col].grid(True, alpha=0.3)

    fig.suptitle("v1.2 anomaly check — spike vs smooth baseline", fontsize=12)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def is_nan(value) -> bool:
    return isinstance(value, float) and math.isnan(value)


def validate_baseline_prior_json(raw: str | None) -> list[str]:
    errors: list[str] = []
    if raw is None:
        errors.append("baseline_prior_json is null")
        return errors
    try:
        prior = json.loads(raw)
    except json.JSONDecodeError:
        errors.append("baseline_prior_json is not valid JSON")
        return errors
    if not isinstance(prior, dict):
        errors.append("baseline_prior_json must decode to an object")
        return errors
    for key in BIOMARKER_KEYS:
        if key not in prior:
            errors.append(f"baseline_prior_json missing biomarker '{key}'")
            continue
        entry = prior[key]
        if not isinstance(entry, dict):
            errors.append(f"prior '{key}' must be {{mean, std}} object")
            continue
        if "mean" not in entry or "std" not in entry:
            errors.append(f"prior '{key}' missing mean or std")
        elif is_nan(entry["mean"]) or is_nan(entry["std"]):
            errors.append(f"prior '{key}' contains NaN")
    return errors


def validate(athletes: list[dict], samples: list[dict]) -> tuple[dict[str, bool], list[str]]:
    checks: dict[str, bool] = {}
    errors: list[str] = []

    checks["athlete_count"] = len(athletes) == CONFIG["n_athletes"]
    if not checks["athlete_count"]:
        errors.append(f"Expected {CONFIG['n_athletes']} athletes, got {len(athletes)}")

    athlete_ids = {a["id"] for a in athletes}
    prior_ok = True
    for athlete in athletes:
        prior_errors = validate_baseline_prior_json(athlete.get("baseline_prior_json"))
        if prior_errors:
            prior_ok = False
            for err in prior_errors:
                errors.append(f"Athlete {athlete.get('id')}: {err}")
    checks["baseline_prior_json"] = prior_ok

    fields_ok = True
    types_ok = True
    nan_ok = True
    ranges_ok = True
    off_score_ok = True
    flags_ok = True
    fk_ok = True

    for sample in samples:
        for field in SAMPLE_FIELDS:
            if field not in sample:
                fields_ok = False
                errors.append(f"Sample {sample.get('id')}: missing '{field}'")

        if sample.get("athlete_id") not in athlete_ids:
            fk_ok = False
            errors.append(f"Sample {sample.get('id')}: invalid athlete_id")

        for biomarker in ("hb", "hct", "ret_pct", "te_ratio", "off_score"):
            val = sample.get(biomarker)
            if val is None or not isinstance(val, (int, float)):
                types_ok = False
            elif is_nan(float(val)):
                nan_ok = False

        for biomarker in ("hb", "hct", "ret_pct", "te_ratio"):
            val = sample.get(biomarker)
            if isinstance(val, (int, float)) and not is_nan(val):
                lo, hi = BOUNDS[biomarker]
                if not (lo <= val <= hi):
                    ranges_ok = False
                    errors.append(
                        f"Sample {sample.get('id')}: {biomarker}={val} outside [{lo}, {hi}]"
                    )

        for flag in ("competition_flag", "altitude_flag", "injury_flag"):
            if sample.get(flag) is not True and sample.get(flag) is not False:
                flags_ok = False

        expected_off = round(compute_off_score(sample["hb"], sample["ret_pct"]), 1)
        if sample["off_score"] != expected_off:
            off_score_ok = False
            errors.append(
                f"Sample {sample.get('id')}: off_score {sample['off_score']} != {expected_off}"
            )

    checks["sample_fields"] = fields_ok
    checks["sample_types"] = types_ok
    checks["no_nans"] = nan_ok
    checks["biomarker_ranges"] = ranges_ok
    checks["off_score_formula"] = off_score_ok
    checks["context_flags_false"] = all(
        s["competition_flag"] is False
        and s["altitude_flag"] is False
        and s["injury_flag"] is False
        for s in samples
    )
    checks["athlete_fk"] = fk_ok
    checks["flags_bool"] = flags_ok

    return checks, errors


def print_validation_report(
    checks: dict[str, bool], errors: list[str], samples: list[dict]
) -> bool:
    labels = {
        "athlete_count": f"Athlete count == {CONFIG['n_athletes']}",
        "baseline_prior_json": "baseline_prior_json present + shaped {biomarker: {mean, std}}",
        "sample_fields": "All sample fields present (8 biomarker/flag fields)",
        "sample_types": "Biomarker fields numeric",
        "no_nans": "No NaNs in biomarkers",
        "biomarker_ranges": "Biomarkers in physiological ranges",
        "off_score_formula": "off_score matches locked formula (all rows)",
        "context_flags_false": "competition/altitude/injury flags all False",
        "athlete_fk": "Valid athlete_id FK on every sample",
        "flags_bool": "Flag fields are bool",
    }

    print("\n" + "=" * 72)
    print("VALIDATION REPORT (v1.2)")
    print("=" * 72)
    print(f"{'Check':<62} {'Result'}")
    print("-" * 72)
    for key, label in labels.items():
        status = "PASS" if checks.get(key, False) else "FAIL"
        print(f"{label:<62} {status}")

    spot_indices = [0, len(samples) // 2, len(samples) - 1]
    print("\noff_score spot-checks (3 rows):")
    spot_ok = True
    for idx in spot_indices:
        s = samples[idx]
        expected = round(compute_off_score(s["hb"], s["ret_pct"]), 1)
        ok = s["off_score"] == expected
        spot_ok = spot_ok and ok
        print(
            f"  sample {s['id']}: hb={s['hb']}, ret_pct={s['ret_pct']} "
            f"-> expected={expected}, stored={s['off_score']} [{'OK' if ok else 'MISMATCH'}]"
        )
    print(f"{'off_score spot-check (3 rows)':<62} {'PASS' if spot_ok else 'FAIL'}")

    overall = all(checks.values()) and spot_ok
    print("-" * 72)
    print(f"{'OVERALL':<62} {'PASS' if overall else 'FAIL'}")
    if errors:
        print("\nFirst errors:")
        for err in errors[:10]:
            print(f"  - {err}")
        if len(errors) > 10:
            print(f"  ... and {len(errors) - 10} more")
    return overall


def write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def print_sample_count_summary(
    sample_counts: dict[int, int],
    transfusion_ids: list[int],
    epo_ids: list[int],
    steroid_ids: list[int],
) -> None:
    """Print per-archetype sample-count distribution for pre-commit review."""
    import statistics

    label_map: dict[int, str] = {}
    for aid in transfusion_ids:
        label_map[aid] = "transfusion"
    for aid in epo_ids:
        label_map[aid] = "epo"
    for aid in steroid_ids:
        label_map[aid] = "steroid"

    groups: dict[str, list[int]] = {
        "clean":        [],
        "transfusion":  [],
        "epo":          [],
        "steroid":      [],
    }
    for aid, n in sample_counts.items():
        groups[label_map.get(aid, "clean")].append(n)

    all_counts = list(sample_counts.values())
    print()
    print("=" * 60)
    print("SAMPLE COUNT DISTRIBUTION SUMMARY (v1.3)")
    print("=" * 60)
    print(f"{'Group':<16} {'n_athletes':>10} {'min':>5} {'max':>5} {'median':>7}")
    print("-" * 60)
    for group, counts in groups.items():
        if not counts:
            continue
        med = statistics.median(counts)
        print(f"{group:<16} {len(counts):>10} {min(counts):>5} {max(counts):>5} {med:>7.1f}")
    print("-" * 60)
    med_all = statistics.median(all_counts)
    print(f"{'ALL':<16} {len(all_counts):>10} {min(all_counts):>5} {max(all_counts):>5} {med_all:>7.1f}")
    print()
    print("Per-athlete counts:")
    for group, counts in groups.items():
        if not counts:
            continue
        print(f"  {group}: {sorted(counts)}")
    print("=" * 60)
    print()


def main(write_files: bool = True) -> None:
    """Generate dataset.

    Args:
        write_files: If False, runs the full pipeline and prints the
            sample-count summary but does NOT write athletes.json,
            samples.json, or ground_truth.json.  Use this to review
            the distribution before committing.
    """
    rng = Random(CONFIG["seed"])

    athletes = generate_athletes(rng)

    # --- Anomaly athlete selection must happen BEFORE sample generation
    # so we can bias sample counts for epo/steroid athletes. ---
    # We do a dry-run selection using a cloned rng state so the
    # actual anomaly selection later (which consumes rng) is identical.
    from copy import deepcopy
    rng_clone = deepcopy(rng)
    # --- Select anomaly athletes ONCE, before any sample generation. ---
    # All three draws happen here in sequence, consuming rng in a fixed order,
    # so the same IDs are used for both sample-count biasing and actual injection.
    athlete_ids = [a["id"] for a in athletes]
    transfusion_ids = select_anomaly_athletes(rng, athlete_ids)
    epo_ids         = select_anomaly_athletes(rng, athlete_ids)
    steroid_ids     = select_anomaly_athletes(rng, athlete_ids)

    # Assign sample counts — epo/steroid get the biased high-end range
    sample_counts = assign_sample_counts(
        rng,
        athletes,
        epo_ids=set(epo_ids),
        steroid_ids=set(steroid_ids),
    )

    # --- Print distribution summary ---
    print_sample_count_summary(sample_counts, transfusion_ids, epo_ids, steroid_ids)

    if not write_files:
        print("[DRY RUN] write_files=False — no data files written.")
        return

    samples = generate_samples(rng, athletes, sample_counts)

    # Inject anomalies using the pre-selected IDs (no second rng draw for selection)
    inject_transfusion_anomalies(rng, samples, transfusion_ids)
    inject_epo_anomalies(rng, samples, epo_ids)
    inject_steroid_anomalies(rng, samples, steroid_ids)

    affected_ids = sorted(set(transfusion_ids + epo_ids + steroid_ids))

    for sample in samples:
        sample["off_score"] = round(
            compute_off_score(sample["hb"], sample["ret_pct"]),
            1,
        )

    write_ground_truth(
        GROUND_TRUTH_PATH,
        athletes,
        transfusion_ids,
        epo_ids,
        steroid_ids,
    )

    athletes_path = DATA_DIR / "athletes.json"
    samples_path = DATA_DIR / "samples.json"
    write_json(athletes_path, athletes)
    write_json(samples_path, samples)

    print(f"Wrote {len(athletes)} athletes -> {athletes_path}")
    print(f"Wrote {len(samples)} samples -> {samples_path}")
    print(f"Ground truth -> {GROUND_TRUTH_PATH}")
    print(
        "Sports: " + ", ".join(f"{s}={sum(1 for a in athletes if a['sport'] == s)}" for s in SPORTS)
    )
    print(
        f"Anomalies injected:"
        f" transfusion={len(transfusion_ids)},"
        f" epo={len(epo_ids)},"
        f" steroid={len(steroid_ids)},"
        f" unique_athletes={len(affected_ids)}"
    )

    if affected_ids:
        save_anomaly_comparison_plot(samples, athletes, affected_ids, ANOMALY_PLOT_PATH)
        print(f"Anomaly plot -> {ANOMALY_PLOT_PATH}")

        # Spot-check off_score on first affected athlete's window samples
        by_aid: dict[int, list[dict]] = {}
        for s in samples:
            by_aid.setdefault(s["athlete_id"], []).append(s)
        aid = affected_ids[0]
        rows = sorted(by_aid[aid], key=lambda s: s["date"])
        print(f"\noff_score spot-check (affected athlete {aid}):")
        for row in rows:
            expected = round(compute_off_score(row["hb"], row["ret_pct"]), 1)
            ok = row["off_score"] == expected
            print(
                f"  sample {row['id']}: hb={row['hb']}, ret_pct={row['ret_pct']} "
                f"-> off_score={row['off_score']} (expected {expected}) "
                f"[{'OK' if ok else 'STALE'}]"
            )

    checks, errors = validate(athletes, samples)
    passed = print_validation_report(checks, errors, samples)
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
