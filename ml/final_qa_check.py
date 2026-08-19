"""
final_qa_check.py — Standalone pre-demo dataset health check.

Runs a comprehensive set of validations on the frozen dataset files and
prints a clear PASS/FAIL summary.  Read-only: this script never modifies
any data file.

Checks performed
----------------
1. Null / NaN detection in all required numeric fields.
2. Physiological range validation for each biomarker.
3. off_score formula recomputation and drift detection.
4. Athlete count (must be exactly 80) and FK integrity.
5. Anomaly archetype distinguishability (visual trend summary).
6. Injected anomaly rate (~18.8 %, 15/80).

Run:
    python3 ml/final_qa_check.py
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

ATHLETES_PATH    = DATA_DIR / "athletes.json"
SAMPLES_PATH     = DATA_DIR / "samples.json"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SAMPLE_BIOMARKERS = ["hb", "hct", "ret_pct", "off_score", "te_ratio"]

PLAUSIBILITY_RANGES: Dict[str, Tuple[float, float]] = {
    "hb":        (10.0, 20.0),
    "hct":       (35.0, 55.0),
    "ret_pct":   (0.2,  4.0),
    "te_ratio":  (0.5,  6.0),
}

# Tolerance for off_score formula comparison (floating-point rounding)
OFF_SCORE_TOLERANCE = 0.5   # absolute difference allowed

# Expected dataset properties
EXPECTED_ATHLETE_COUNT = 80
EXPECTED_ANOMALY_COUNT = 15
EXPECTED_ANOMALY_RATE  = EXPECTED_ANOMALY_COUNT / EXPECTED_ATHLETE_COUNT  # 0.1875

EXPECTED_PATTERN_TYPES = {"transfusion", "epo_micro_dosing", "steroid_micro_dosing"}

# ---------------------------------------------------------------------------
# Result accumulator
# ---------------------------------------------------------------------------
class CheckResult:
    def __init__(self, name: str):
        self.name    = name
        self.passed  = True
        self.details: List[str] = []

    def fail(self, msg: str) -> None:
        self.passed = False
        self.details.append(f"  ✗ {msg}")

    def info(self, msg: str) -> None:
        self.details.append(f"    {msg}")

    def ok(self, msg: str) -> None:
        self.details.append(f"  ✓ {msg}")

    def print(self) -> None:
        status = "PASS" if self.passed else "FAIL"
        icon   = "✅" if self.passed else "❌"
        print(f"\n{icon} Check {self.name}: {status}")
        for d in self.details:
            print(d)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path) -> list | dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def is_null_or_nan(v) -> bool:
    if v is None:
        return True
    try:
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False


def compute_off_score(hb: float, ret_pct: float) -> float:
    """
    off_score = (hb [g/dL] × 10) − 60 × sqrt(ret_pct [%])

    This is the canonical formula as stated in the task spec.
    """
    return (hb * 10.0) - (60.0 * math.sqrt(ret_pct))


def trend_summary(values: List[float], label: str, n_head: int = 5) -> str:
    """Return a compact trend description for a list of chronological values."""
    if not values:
        return f"{label}: no data"
    lo, hi = min(values), max(values)
    first_mean = sum(values[:n_head]) / len(values[:n_head])
    last_mean  = sum(values[-n_head:]) / len(values[-n_head:])
    direction  = "↑" if last_mean > first_mean + 0.05 else ("↓" if last_mean < first_mean - 0.05 else "→")
    return (
        f"{label}: range=[{lo:.3f}, {hi:.3f}]  "
        f"first{n_head}_avg={first_mean:.3f}  last{n_head}_avg={last_mean:.3f}  trend={direction}"
    )


# ---------------------------------------------------------------------------
# Check 1 — Null / NaN detection
# ---------------------------------------------------------------------------

def check_nulls(
    athletes: List[dict],
    samples:  List[dict],
    ground_truth: List[dict],
) -> CheckResult:
    r = CheckResult("1 [Null/NaN Detection]")

    # athletes.json numeric fields
    ath_numeric = ["id", "age"]
    null_count = 0
    for a in athletes:
        for field in ath_numeric:
            v = a.get(field)
            if is_null_or_nan(v):
                r.fail(f"athletes.json id={a.get('id')} field='{field}' is null/NaN")
                null_count += 1

    # samples.json required numeric fields
    for s in samples:
        for field in SAMPLE_BIOMARKERS:
            v = s.get(field)
            if is_null_or_nan(v):
                r.fail(
                    f"samples.json id={s.get('id')} athlete_id={s.get('athlete_id')} "
                    f"date={s.get('date')} field='{field}' is null/NaN"
                )
                null_count += 1

    # ground_truth.json
    for g in ground_truth:
        v = g.get("is_synthetic_anomaly")
        if is_null_or_nan(v) or v is None:
            r.fail(
                f"ground_truth.json athlete_id={g.get('athlete_id')} "
                f"field='is_synthetic_anomaly' is null/NaN"
            )
            null_count += 1

    if null_count == 0:
        r.ok(f"No null/NaN values found across all three files.")
    else:
        r.info(f"Total null/NaN occurrences: {null_count}")

    return r


# ---------------------------------------------------------------------------
# Check 2 — Physiological range validation
# ---------------------------------------------------------------------------

def check_ranges(samples: List[dict]) -> CheckResult:
    r = CheckResult("2 [Physiological Range Validation]")
    violation_count = 0

    for s in samples:
        sid  = s.get("id")
        aid  = s.get("athlete_id")
        date = s.get("date")
        for biomarker, (lo, hi) in PLAUSIBILITY_RANGES.items():
            v = s.get(biomarker)
            if v is None:
                continue
            fv = float(v)
            if not (lo <= fv <= hi):
                r.fail(
                    f"samples id={sid} athlete_id={aid} date={date} "
                    f"{biomarker}={fv:.4f} outside [{lo}, {hi}]"
                )
                violation_count += 1

    if violation_count == 0:
        r.ok(f"All sample biomarker values within physiological ranges.")
    else:
        r.info(f"Total range violations: {violation_count}")

    return r


# ---------------------------------------------------------------------------
# Check 3 — off_score formula recomputation
# ---------------------------------------------------------------------------

def check_off_score_formula(samples: List[dict]) -> CheckResult:
    r = CheckResult("3 [off_score Formula Verification]")
    mismatch_count = 0
    checked = 0

    for s in samples:
        hb      = s.get("hb")
        ret_pct = s.get("ret_pct")
        stored  = s.get("off_score")

        if any(v is None for v in [hb, ret_pct, stored]):
            continue  # already caught by check 1

        try:
            expected = compute_off_score(float(hb), float(ret_pct))
        except (ValueError, ZeroDivisionError):
            r.fail(
                f"samples id={s.get('id')} could not recompute off_score "
                f"(hb={hb}, ret_pct={ret_pct})"
            )
            mismatch_count += 1
            continue

        diff = abs(float(stored) - expected)
        checked += 1
        if diff > OFF_SCORE_TOLERANCE:
            r.fail(
                f"samples id={s.get('id')} athlete_id={s.get('athlete_id')} "
                f"date={s.get('date')}: "
                f"stored={float(stored):.4f}  recomputed={expected:.4f}  "
                f"diff={diff:.4f} > tol={OFF_SCORE_TOLERANCE}"
            )
            mismatch_count += 1

    if mismatch_count == 0:
        r.ok(
            f"All {checked} off_score values match formula "
            f"(hb×10 − 60×√ret_pct) within ±{OFF_SCORE_TOLERANCE}."
        )
    else:
        r.info(f"Formula: off_score = (hb × 10) − (60 × √ret_pct)")
        r.info(f"Tolerance: ±{OFF_SCORE_TOLERANCE}")
        r.info(f"Total mismatches: {mismatch_count} / {checked} checked")

    return r


# ---------------------------------------------------------------------------
# Check 4 — Athlete count and FK integrity
# ---------------------------------------------------------------------------

def check_fk_integrity(
    athletes:     List[dict],
    samples:      List[dict],
    ground_truth: List[dict],
) -> CheckResult:
    r = CheckResult("4 [Athlete Count & FK Integrity]")

    athlete_ids: Set[int] = {a["id"] for a in athletes}
    n_athletes = len(athletes)

    # Athlete count
    if n_athletes == EXPECTED_ATHLETE_COUNT:
        r.ok(f"Athlete count = {n_athletes} (expected {EXPECTED_ATHLETE_COUNT}) ✓")
    else:
        r.fail(
            f"Athlete count = {n_athletes}, expected {EXPECTED_ATHLETE_COUNT}"
        )

    # Duplicate athlete IDs
    id_list = [a["id"] for a in athletes]
    if len(id_list) != len(set(id_list)):
        from collections import Counter
        dupes = [k for k, v in Counter(id_list).items() if v > 1]
        r.fail(f"Duplicate athlete IDs in athletes.json: {dupes}")
    else:
        r.ok("No duplicate athlete IDs.")

    # samples.json FK
    orphan_sample_ids: List[int] = [
        s["id"] for s in samples if s.get("athlete_id") not in athlete_ids
    ]
    if orphan_sample_ids:
        r.fail(
            f"samples.json: {len(orphan_sample_ids)} orphaned athlete_id(s) "
            f"not in athletes.json — sample IDs: {orphan_sample_ids[:20]}"
            + (" …" if len(orphan_sample_ids) > 20 else "")
        )
    else:
        r.ok(f"All {len(samples)} sample rows reference valid athlete IDs.")

    # ground_truth.json FK
    orphan_gt_ids: List[int] = [
        g["athlete_id"] for g in ground_truth if g.get("athlete_id") not in athlete_ids
    ]
    if orphan_gt_ids:
        r.fail(
            f"ground_truth.json: {len(orphan_gt_ids)} orphaned athlete_id(s) "
            f"not in athletes.json: {orphan_gt_ids}"
        )
    else:
        r.ok(f"All {len(ground_truth)} ground_truth rows reference valid athlete IDs.")

    # Every athlete must appear in ground_truth
    gt_athlete_ids = {g["athlete_id"] for g in ground_truth}
    missing_from_gt = athlete_ids - gt_athlete_ids
    if missing_from_gt:
        r.fail(
            f"{len(missing_from_gt)} athlete(s) have no ground_truth row: "
            f"{sorted(missing_from_gt)}"
        )
    else:
        r.ok("Every athlete has a ground_truth entry.")

    return r


# ---------------------------------------------------------------------------
# Check 5 — Anomaly archetype distinguishability
# ---------------------------------------------------------------------------

def check_archetype_distinguishability(
    athletes:     List[dict],
    samples:      List[dict],
    ground_truth: List[dict],
) -> CheckResult:
    r = CheckResult("5 [Anomaly Archetype Distinguishability]")

    # Build id→sport map
    id_to_sport: Dict[int, str] = {a["id"]: a["sport"] for a in athletes}

    # Build athlete_id → sorted (by date) samples list
    athlete_samples: Dict[int, List[dict]] = defaultdict(list)
    for s in samples:
        athlete_samples[s["athlete_id"]].append(s)
    for aid in athlete_samples:
        athlete_samples[aid].sort(key=lambda x: x["date"])

    # Group anomalous athletes by pattern_type
    pattern_athletes: Dict[str, List[int]] = defaultdict(list)
    for g in ground_truth:
        if g.get("is_synthetic_anomaly") and g.get("pattern_type"):
            pattern_athletes[g["pattern_type"]].append(g["athlete_id"])

    found_patterns = set(pattern_athletes.keys())
    r.info(f"Pattern types found in ground_truth: {sorted(found_patterns)}")

    # Check that expected archetypes are present
    # (be flexible: accept partial name matches in case naming differs slightly)
    def _find_key(target_substr: str) -> Optional[str]:
        for k in found_patterns:
            if target_substr in k.lower():
                return k
        return None

    transfusion_key = _find_key("transfusion")
    epo_key         = _find_key("epo") or _find_key("micro_dos")
    steroid_key     = _find_key("steroid")

    # ── Transfusion: expect Hb step-up then RET% suppression ───────────────
    print()
    print("  ── Transfusion archetype ──────────────────────────────────────")
    if transfusion_key is None:
        r.fail("No 'transfusion' pattern found in ground_truth.json.")
    else:
        ids = pattern_athletes[transfusion_key]
        r.info(f"Flagged athletes ({len(ids)}): IDs hidden; printing biomarker trends.")
        distinguishable = 0
        for aid in ids:
            slist = athlete_samples[aid]
            if not slist:
                r.fail(f"  athlete_id={aid}: no samples found.")
                continue
            hb_vals      = [s["hb"]      for s in slist]
            ret_vals     = [s["ret_pct"] for s in slist]
            hb_max       = max(hb_vals)
            hb_min       = min(hb_vals)
            hb_step      = hb_max - hb_min
            ret_min      = min(ret_vals)
            ret_after_hb_peak = ret_vals[hb_vals.index(hb_max):]  # ret_pct from peak onward
            ret_after_min = min(ret_after_hb_peak) if ret_after_hb_peak else ret_min
            sport        = id_to_sport.get(aid, "?")
            hb_trend     = trend_summary(hb_vals, "hb")
            ret_trend    = trend_summary(ret_vals, "ret_pct")
            print(f"    [{sport}] {hb_trend}")
            print(f"    [{sport}] {ret_trend}")
            print(f"    [{sport}] hb_step_range={hb_step:.3f}  ret_pct_post_peak_min={ret_after_min:.3f}")
            if hb_step >= 0.3 or ret_after_min < 0.9:
                distinguishable += 1
        if distinguishable == len(ids):
            r.ok(f"Transfusion pattern distinguishable in all {len(ids)} flagged athlete(s).")
        elif distinguishable > 0:
            r.fail(
                f"Transfusion pattern distinguishable in only {distinguishable}/{len(ids)} "
                "flagged athlete(s). Review others."
            )
        else:
            r.fail("Transfusion pattern NOT clearly distinguishable in any flagged athlete.")

    # ── EPO micro-dosing: small sustained Hb/HCT upward drift ──────────────
    print()
    print("  ── EPO micro-dosing archetype ─────────────────────────────────")
    if epo_key is None:
        r.fail("No EPO micro-dosing pattern found in ground_truth.json.")
    else:
        ids = pattern_athletes[epo_key]
        r.info(f"Flagged athletes ({len(ids)}): printing biomarker trends.")
        distinguishable = 0
        for aid in ids:
            slist = athlete_samples[aid]
            if not slist:
                r.fail(f"  athlete_id={aid}: no samples found.")
                continue
            hb_vals  = [s["hb"]  for s in slist]
            hct_vals = [s["hct"] for s in slist]
            ret_vals = [s["ret_pct"] for s in slist]
            sport    = id_to_sport.get(aid, "?")
            n = max(5, len(hb_vals) // 4)
            hb_drift  = (sum(hb_vals[-n:]) / n) - (sum(hb_vals[:n]) / n)
            hct_drift = (sum(hct_vals[-n:]) / n) - (sum(hct_vals[:n]) / n)
            print(f"    [{sport}] {trend_summary(hb_vals,  'hb')}")
            print(f"    [{sport}] {trend_summary(hct_vals, 'hct')}")
            print(f"    [{sport}] {trend_summary(ret_vals, 'ret_pct')}")
            print(f"    [{sport}] hb_drift(last_q - first_q)={hb_drift:+.3f}  "
                  f"hct_drift={hct_drift:+.3f}")
            if hb_drift > 0.1 or hct_drift > 0.3:
                distinguishable += 1
        if distinguishable == len(ids):
            r.ok(f"EPO micro-dosing pattern distinguishable in all {len(ids)} flagged athlete(s).")
        elif distinguishable > 0:
            r.fail(
                f"EPO micro-dosing pattern distinguishable in only {distinguishable}/{len(ids)} "
                "flagged athlete(s). Review others."
            )
        else:
            r.fail("EPO micro-dosing pattern NOT clearly distinguishable in any flagged athlete.")

    # ── Steroid micro-dosing: gradual te_ratio drift ────────────────────────
    print()
    print("  ── Steroid micro-dosing archetype ─────────────────────────────")
    if steroid_key is None:
        r.fail("No steroid micro-dosing pattern found in ground_truth.json.")
    else:
        ids = pattern_athletes[steroid_key]
        r.info(f"Flagged athletes ({len(ids)}): printing biomarker trends.")
        distinguishable = 0
        for aid in ids:
            slist = athlete_samples[aid]
            if not slist:
                r.fail(f"  athlete_id={aid}: no samples found.")
                continue
            te_vals  = [s["te_ratio"] for s in slist]
            hb_vals  = [s["hb"]      for s in slist]
            sport    = id_to_sport.get(aid, "?")
            n = max(5, len(te_vals) // 4)
            te_drift = (sum(te_vals[-n:]) / n) - (sum(te_vals[:n]) / n)
            print(f"    [{sport}] {trend_summary(te_vals, 'te_ratio')}")
            print(f"    [{sport}] {trend_summary(hb_vals, 'hb')}")
            print(f"    [{sport}] te_ratio_drift(last_q - first_q)={te_drift:+.3f}")
            if te_drift > 0.05:
                distinguishable += 1
        if distinguishable == len(ids):
            r.ok(f"Steroid micro-dosing pattern distinguishable in all {len(ids)} flagged athlete(s).")
        elif distinguishable > 0:
            r.fail(
                f"Steroid micro-dosing pattern distinguishable in only {distinguishable}/{len(ids)} "
                "flagged athlete(s). Review others."
            )
        else:
            r.fail("Steroid micro-dosing pattern NOT clearly distinguishable in any flagged athlete.")

    return r


# ---------------------------------------------------------------------------
# Check 6 — Anomaly rate
# ---------------------------------------------------------------------------

def check_anomaly_rate(
    athletes:     List[dict],
    ground_truth: List[dict],
) -> CheckResult:
    r = CheckResult("6 [Injected Anomaly Rate]")

    n_athletes = len(athletes)
    n_anomalies = sum(1 for g in ground_truth if g.get("is_synthetic_anomaly") is True)
    rate = n_anomalies / n_athletes if n_athletes > 0 else 0.0

    r.info(f"Total athletes      : {n_athletes}")
    r.info(f"Anomalous athletes  : {n_anomalies}")
    r.info(f"Anomaly rate        : {n_anomalies}/{n_athletes} = {rate*100:.2f}%")
    r.info(f"Expected            : {EXPECTED_ANOMALY_COUNT}/{EXPECTED_ATHLETE_COUNT} "
           f"= {EXPECTED_ANOMALY_RATE*100:.2f}%")

    count_ok = n_anomalies == EXPECTED_ANOMALY_COUNT
    rate_ok  = abs(rate - EXPECTED_ANOMALY_RATE) < 0.001

    if count_ok and rate_ok:
        r.ok(
            f"Anomaly rate {n_anomalies}/{n_athletes} = {rate*100:.2f}% "
            f"matches spec ({EXPECTED_ANOMALY_RATE*100:.2f}%)."
        )
    else:
        if not count_ok:
            r.fail(
                f"Anomaly count {n_anomalies} ≠ expected {EXPECTED_ANOMALY_COUNT}."
            )
        if not rate_ok:
            r.fail(
                f"Anomaly rate {rate*100:.2f}% deviates from expected "
                f"{EXPECTED_ANOMALY_RATE*100:.2f}%."
            )

    return r


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    sep = "═" * 70

    print(sep)
    print("FINAL QA CHECK — Adaptive Anti-Doping Defense Engine")
    print("Pre-demo dataset health check (read-only)")
    print(sep)

    # ── Load ───────────────────────────────────────────────────────────────
    print("\nLoading data files …")
    athletes     = load_json(ATHLETES_PATH)
    samples      = load_json(SAMPLES_PATH)
    ground_truth = load_json(GROUND_TRUTH_PATH)
    print(f"  athletes.json    : {len(athletes)} records")
    print(f"  samples.json     : {len(samples)} records")
    print(f"  ground_truth.json: {len(ground_truth)} records")

    # ── Run checks ─────────────────────────────────────────────────────────
    results = [
        check_nulls(athletes, samples, ground_truth),
        check_ranges(samples),
        check_off_score_formula(samples),
        check_fk_integrity(athletes, samples, ground_truth),
        check_archetype_distinguishability(athletes, samples, ground_truth),
        check_anomaly_rate(athletes, ground_truth),
    ]

    # ── Print individual results ────────────────────────────────────────────
    for res in results:
        res.print()

    # ── Final PASS/FAIL summary ─────────────────────────────────────────────
    all_passed = all(r.passed for r in results)

    print(f"\n{sep}")
    print("FINAL SUMMARY")
    print(sep)
    for res in results:
        icon   = "✅ PASS" if res.passed else "❌ FAIL"
        print(f"  {icon}  {res.name}")

    print()
    if all_passed:
        print("🏆  OVERALL: PASS — dataset is clean and ready for demo.")
    else:
        failed = [r.name for r in results if not r.passed]
        print(f"🚨  OVERALL: FAIL — {len(failed)} check(s) failed:")
        for name in failed:
            print(f"    • {name}")
        print("\nDo NOT modify any data file based on this output.")
        print("Report findings to Dev 1 and decide together whether each")
        print("failure is a real issue or an acceptable rounding artifact.")

    print(sep)


if __name__ == "__main__":
    main()
