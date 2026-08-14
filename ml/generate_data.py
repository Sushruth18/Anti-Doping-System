"""v0 synthetic data generator — real Hb random walk, placeholder other biomarkers."""

from __future__ import annotations

import json
import math
from datetime import date, timedelta
from pathlib import Path
from random import Random

# --- CONFIG ---
CONFIG = {
    "n_athletes": 10,
    "seed": 42,
    "biomarkers": ["hb"],  # v0: only Hb is generated; hct/ret_pct/te_ratio are placeholders
    "n_samples_per_athlete": 5,
    "samples_start_date": "2025-01-15",
    "sample_interval_days": 28,
    # AR(1)-style Hb walk: next = previous + drift + correlated_noise
    "hb_drift": 0.0,  # g/dL per sample (0 = no systematic trend)
    "hb_autocorrelation": 0.75,  # rho: inertia of the increment (0=independent, ~1=smooth drift)
    "hb_noise_std": 0.12,  # std of fresh shock each step (after autocorrelation)
}

# Placeholder constants (v1 will replace with correlated generated values).
# Population-average-ish values, clearly not athlete-specific at this stage.
PLACEHOLDER_HCT = 42.5  # % — typical adult male athlete hematocrit
PLACEHOLDER_RET_PCT = 1.0  # % — mid-normal reticulocyte percentage (not a fraction)
PLACEHOLDER_TE_RATIO = 1.0  # unitless — normal T/E reference

# Hb random-walk bounds (g/dL)
HB_MIN = 12.0
HB_MAX = 18.0

SPORTS = ["Cycling", "Running", "Swimming", "Rowing", "Triathlon"]

FIRST_NAMES = [
    "Alex", "Jordan", "Sam", "Taylor", "Casey",
    "Morgan", "Riley", "Quinn", "Avery", "Blake",
]
LAST_NAMES = [
    "Chen", "Okonkwo", "Petrov", "Santos", "Kim",
    "Andersson", "Nakamura", "Dupont", "Silva", "Hansen",
]

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

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
    """Locked formula: off_score = (hb_g_dL * 10) - 60 * sqrt(ret_pct).

    At v0, ret_pct is a placeholder constant, so off_score tracks Hb only and
    is provisional until v1 generates real ret_pct values.
    """
    return (hb_g_dL * 10) - (60 * math.sqrt(ret_pct))


def random_walk_hb(rng: Random, n_steps: int, start: float) -> list[float]:
    """Generate a clamped AR(1)-style random walk for Hb (g/dL).

    Each step: hb_t = hb_{t-1} + drift + epsilon_t
    where epsilon_t = rho * epsilon_{t-1} + N(0, noise_std).

    Autocorrelation on the increment produces smooth day-to-day drift instead of
    independent step noise (v0).
    """
    rho = CONFIG["hb_autocorrelation"]
    drift = CONFIG["hb_drift"]
    noise_std = CONFIG["hb_noise_std"]

    values = [start]
    epsilon = 0.0
    for _ in range(n_steps - 1):
        epsilon = (rho * epsilon) + rng.gauss(0, noise_std)
        next_val = values[-1] + drift + epsilon
        next_val = max(HB_MIN, min(HB_MAX, next_val))
        values.append(next_val)
    return [round(v, 2) for v in values]


def generate_athletes(rng: Random) -> list[dict]:
    athletes = []
    for i in range(CONFIG["n_athletes"]):
        athletes.append(
            {
                "id": i + 1,
                "name": f"{FIRST_NAMES[i]} {LAST_NAMES[i]}",
                "sport": rng.choice(SPORTS),
                "age": rng.randint(18, 35),
                "baseline_prior_json": None,
            }
        )
    return athletes


def generate_samples(rng: Random, athletes: list[dict]) -> list[dict]:
    samples: list[dict] = []
    sample_id = 1
    start = date.fromisoformat(CONFIG["samples_start_date"])
    interval = timedelta(days=CONFIG["sample_interval_days"])

    for athlete in athletes:
        hb_start = round(rng.uniform(13.0, 16.5), 2)
        hb_series = random_walk_hb(rng, CONFIG["n_samples_per_athlete"], hb_start)

        for step, hb in enumerate(hb_series):
            sample_date = start + (interval * step)
            # off_score uses placeholder ret_pct — provisional until v1
            off_score = round(compute_off_score(hb, PLACEHOLDER_RET_PCT), 1)

            samples.append(
                {
                    "id": sample_id,
                    "athlete_id": athlete["id"],
                    "date": sample_date.isoformat(),  # schema Date → ISO YYYY-MM-DD
                    "hb": hb,
                    "hct": PLACEHOLDER_HCT,
                    "ret_pct": PLACEHOLDER_RET_PCT,
                    "off_score": off_score,
                    "te_ratio": PLACEHOLDER_TE_RATIO,
                    # Context flags out of scope at v0 — all False (competition / altitude / injury-TUE)
                    "competition_flag": False,
                    "altitude_flag": False,
                    "injury_flag": False,
                }
            )
            sample_id += 1

    return samples


def validate(athletes: list[dict], samples: list[dict]) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if len(athletes) != CONFIG["n_athletes"]:
        errors.append(f"Expected {CONFIG['n_athletes']} athletes, got {len(athletes)}")

    athlete_ids = {a["id"] for a in athletes}
    for athlete in athletes:
        if not isinstance(athlete["id"], int):
            errors.append(f"Athlete id must be int, got {type(athlete['id'])}")
        if athlete["baseline_prior_json"] is not None:
            errors.append(f"Athlete {athlete['id']}: baseline_prior_json must be null at v0")

    for sample in samples:
        for field in SAMPLE_FIELDS:
            if field not in sample:
                errors.append(f"Sample {sample.get('id')}: missing field '{field}'")

        if sample.get("athlete_id") not in athlete_ids:
            errors.append(f"Sample {sample.get('id')}: invalid athlete_id {sample.get('athlete_id')}")

        hb = sample.get("hb")
        if hb is None or (isinstance(hb, float) and math.isnan(hb)):
            errors.append(f"Sample {sample.get('id')}: hb is NaN or missing")
        elif not (HB_MIN <= hb <= HB_MAX):
            errors.append(f"Sample {sample.get('id')}: hb={hb} outside [{HB_MIN}, {HB_MAX}]")

        for field in ("hct", "ret_pct", "off_score", "te_ratio"):
            val = sample.get(field)
            if val is None or (isinstance(val, float) and math.isnan(val)):
                errors.append(f"Sample {sample.get('id')}: {field} is NaN or missing")

        for flag in ("competition_flag", "altitude_flag", "injury_flag"):
            if sample.get(flag) is not True and sample.get(flag) is not False:
                errors.append(f"Sample {sample.get('id')}: {flag} must be bool")

        expected_off = round(compute_off_score(sample["hb"], sample["ret_pct"]), 1)
        if sample["off_score"] != expected_off:
            errors.append(
                f"Sample {sample.get('id')}: off_score {sample['off_score']} != expected {expected_off}"
            )

    # Manual spot-check rows (first two samples)
    if len(samples) >= 2:
        for idx in (0, 1):
            s = samples[idx]
            manual = round(compute_off_score(s["hb"], s["ret_pct"]), 1)
            print(
                f"  spot-check sample {s['id']}: hb={s['hb']}, ret_pct={s['ret_pct']} "
                f"-> off_score={manual} (stored={s['off_score']})"
            )

    return len(errors) == 0, errors


def write_json(path: Path, data: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def main() -> None:
    rng = Random(CONFIG["seed"])

    athletes = generate_athletes(rng)
    samples = generate_samples(rng, athletes)

    athletes_path = DATA_DIR / "athletes.json"
    samples_path = DATA_DIR / "samples.json"
    write_json(athletes_path, athletes)
    write_json(samples_path, samples)

    print(f"Wrote {len(athletes)} athletes -> {athletes_path}")
    print(f"Wrote {len(samples)} samples -> {samples_path}")

    passed, errors = validate(athletes, samples)
    if passed:
        print("VALIDATION: PASS")
    else:
        print("VALIDATION: FAIL")
        for err in errors:
            print(f"  - {err}")


if __name__ == "__main__":
    main()
