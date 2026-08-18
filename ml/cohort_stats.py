"""
cohort_stats.py — Standalone script (not imported by the backend).

Computes population mean and std for each (sport, biomarker) pair from
data/samples.json, excluding any athlete flagged as a synthetic anomaly
in data/ground_truth.json.

Writes results to data/cohort_stats.json.
Field names match the `cohort_stats` table spec in docs/schema.md:
  sport, biomarker, population_mean, population_std

Run:
    python ml/cohort_stats.py
"""

from __future__ import annotations

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

# ---------------------------------------------------------------------------
# Paths — all relative to the repo root so the script works from any cwd
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

ATHLETES_PATH = DATA_DIR / "athletes.json"
SAMPLES_PATH = DATA_DIR / "samples.json"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"
OUTPUT_PATH = DATA_DIR / "cohort_stats.json"

BIOMARKERS: List[str] = ["hb", "hct", "ret_pct", "off_score", "te_ratio"]

# Physiological plausibility ranges for adult athletes (used for flagging only)
PLAUSIBILITY_RANGES: Dict[str, tuple] = {
    "hb":        (13.0, 17.0),    # g/dL
    "hct":       (40.0, 52.0),    # %
    "ret_pct":   (0.5,  2.5),     # %
    "te_ratio":  (1.0,  4.0),     # dimensionless
    "off_score": (60.0, 100.0),   # derived score
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> list | dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def population_std(values: List[float]) -> float:
    """True population std-dev (ddof=0) without numpy dependency."""
    n = len(values)
    if n == 0:
        return 0.0
    mean = sum(values) / n
    variance = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(variance)


def population_mean(values: List[float]) -> float:
    n = len(values)
    if n == 0:
        return 0.0
    return sum(values) / n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ── 1. Load data ────────────────────────────────────────────────────────
    print("Loading data files …")
    athletes_raw: List[dict] = load_json(ATHLETES_PATH)
    samples_raw:  List[dict] = load_json(SAMPLES_PATH)
    ground_truth_raw: List[dict] = load_json(GROUND_TRUTH_PATH)

    # ── 2. Build set of anomalous athlete IDs (ground_truth, internal only) ─
    anomalous_ids: Set[int] = {
        row["athlete_id"]
        for row in ground_truth_raw
        if row.get("is_synthetic_anomaly") is True
    }
    print(f"\nSynthetic anomaly athletes excluded from cohort: "
          f"{len(anomalous_ids)} athlete(s) (IDs not printed for privacy).")

    # ── 3. Build athlete_id → sport map (clean athletes only) ───────────────
    id_to_sport: Dict[int, str] = {}
    for a in athletes_raw:
        if a["id"] not in anomalous_ids:
            id_to_sport[a["id"]] = a["sport"]

    # Discover distinct sports (from the full athletes list, not filtered —
    # so we report every sport that exists in the dataset)
    all_sports_in_dataset = sorted({a["sport"] for a in athletes_raw})
    print(f"\nDistinct sports found in athletes.json ({len(all_sports_in_dataset)}):")
    for s in all_sports_in_dataset:
        print(f"  • {s}")

    # ── 4. Bucket sample values by (sport, biomarker) ───────────────────────
    # Only include samples whose athlete is NOT anomalous
    buckets: Dict[tuple, List[float]] = defaultdict(list)

    skipped_samples = 0
    for sample in samples_raw:
        aid = sample["athlete_id"]
        if aid not in id_to_sport:
            # athlete is either anomalous or not in athletes.json — skip
            skipped_samples += 1
            continue
        sport = id_to_sport[aid]
        for biomarker in BIOMARKERS:
            value = sample.get(biomarker)
            if value is not None:
                buckets[(sport, biomarker)].append(float(value))

    print(f"\nSamples skipped (from anomalous or unknown athletes): {skipped_samples}")

    # ── 5. Compute stats ─────────────────────────────────────────────────────
    results: List[dict] = []
    for sport in all_sports_in_dataset:
        for biomarker in BIOMARKERS:
            values = buckets[(sport, biomarker)]
            mean  = population_mean(values)
            std   = population_std(values)
            results.append({
                "sport":           sport,
                "biomarker":       biomarker,
                "population_mean": round(mean, 6),
                "population_std":  round(std, 6),
            })

    # ── 6. Write output ──────────────────────────────────────────────────────
    with open(OUTPUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"\nWrote {len(results)} rows → {OUTPUT_PATH.relative_to(REPO_ROOT)}")

    # ── 7. Print full table with plausibility flags ───────────────────────────
    col_sport     = max(len(r["sport"])    for r in results)
    col_biomarker = max(len(r["biomarker"]) for r in results)

    header = (
        f"{'Sport':<{col_sport}}  "
        f"{'Biomarker':<{col_biomarker}}  "
        f"{'Mean':>10}  "
        f"{'Std':>10}  "
        f"{'n_samples':>9}  "
        f"Flag"
    )
    separator = "-" * len(header)

    print(f"\n{'─'*len(header)}")
    print("COHORT STATS — full (sport × biomarker) table")
    print(f"{'─'*len(header)}")
    print(header)
    print(separator)

    warnings_issued: List[str] = []

    for r in results:
        sport     = r["sport"]
        biomarker = r["biomarker"]
        mean_val  = r["population_mean"]
        std_val   = r["population_std"]
        n         = len(buckets[(sport, biomarker)])

        lo, hi = PLAUSIBILITY_RANGES.get(biomarker, (None, None))
        flag = ""
        if lo is not None and not (lo <= mean_val <= hi):
            flag = "⚠️  OUT-OF-RANGE"
            warnings_issued.append(
                f"  [{sport}] {biomarker}: mean={mean_val:.4f} "
                f"(expected {lo}–{hi})"
            )

        print(
            f"{sport:<{col_sport}}  "
            f"{biomarker:<{col_biomarker}}  "
            f"{mean_val:>10.4f}  "
            f"{std_val:>10.4f}  "
            f"{n:>9}  "
            f"{flag}"
        )

    print(separator)

    if warnings_issued:
        print("\n⚠️  PLAUSIBILITY WARNINGS — review before committing:")
        for w in warnings_issued:
            print(w)
    else:
        print("\n✅  All (sport, biomarker) means fall within physiological "
              "plausibility ranges.")

    print("\nDone.")


if __name__ == "__main__":
    main()
