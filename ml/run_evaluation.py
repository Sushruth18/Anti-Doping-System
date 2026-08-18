"""
run_evaluation.py — Standalone evaluation script for the Anti-Doping Defense Engine.
Replaces (and supersedes) the Day-4 notebook for all quantitative eval work.

Usage:
    python3 ml/run_evaluation.py

Inputs  (read-only):
    data/exported_anomaly_scores.json   — live backend anomaly scores
    data/ground_truth.json              — internal ground-truth labels

Outputs:
    • Console: distribution summary, precision/recall/FPR table,
               per-pattern recall breakdown, before/after vs Day-4,
               known-limitation confirmation, staleness warning.
    • data/evaluation_results.json      — machine-readable results snapshot

Do NOT modify any data file.
Do NOT touch docs/, /backend, or /frontend.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT  = Path(__file__).resolve().parent.parent
DATA_DIR   = REPO_ROOT / "data"

SCORES_PATH      = DATA_DIR / "exported_anomaly_scores.json"
GT_PATH          = DATA_DIR / "ground_truth.json"
RESULTS_OUT_PATH = DATA_DIR / "evaluation_results.json"

# ---------------------------------------------------------------------------
# Day-4 baseline numbers (from last committed notebook output, pre-recalibrations)
# Kept here for before/after comparison only; never used for logic.
# ---------------------------------------------------------------------------
DAY4_BASELINE = {
    "note": "Day-4 notebook — transfusion-heuristic labels, pre-noise-model upgrade",
    "thresholds": {
        0.50: {"precision": None, "recall": None, "fpr": None},
        0.55: {"precision": None, "recall": None, "fpr": None},
        0.70: {"precision": None, "recall": None, "fpr": None},
        0.85: {"precision": None, "recall": None, "fpr": None},
    },
    "recall_by_pattern": {
        "transfusion":           None,
        "epo":                   None,
        "steroid":               None,
    },
}
# NOTE: Day-4 numbers were never persisted to a JSON file (notebook only),
# so we mark them None and report "N/A — no saved baseline found".

# ---------------------------------------------------------------------------
# Staleness reference values (what Dev 2 knows the CURRENT backend produces)
# ---------------------------------------------------------------------------
CURRENT_REF = {
    "median": 0.34,
    "mean":   0.37,
    "moderate_count": 11,   # scores >= 0.55
    "elevated_count":  4,   # scores >= 0.70
    "n_athletes":     80,
}

THRESHOLDS = [0.50, 0.55, 0.70, 0.85]

SEP = "═" * 70
SEP2 = "─" * 70


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def round4(v: float) -> float:
    return round(v, 4)


def pct(v: float) -> str:
    return f"{v * 100:.1f}%"


def find_pattern_key(pattern_athletes: Dict[str, list], substr: str) -> Optional[str]:
    for k in pattern_athletes:
        if substr in k.lower():
            return k
    return None


# ---------------------------------------------------------------------------
# Staleness check
# ---------------------------------------------------------------------------

def check_staleness(scores: List[float], n: int) -> bool:
    """
    Returns True if the export looks current (matches CURRENT_REF).
    Prints a warning and returns False if it looks stale.
    """
    med     = statistics.median(scores)
    mean    = statistics.mean(scores)
    mod_cnt = sum(1 for s in scores if s >= 0.55)
    ele_cnt = sum(1 for s in scores if s >= 0.70)

    ref = CURRENT_REF
    stale_flags = []

    if abs(med  - ref["median"])        > 0.02:  stale_flags.append(f"median {med:.4f} vs ref {ref['median']}")
    if abs(mean - ref["mean"])          > 0.02:  stale_flags.append(f"mean {mean:.4f} vs ref {ref['mean']}")
    if abs(mod_cnt - ref["moderate_count"]) > 1: stale_flags.append(f"moderate_count {mod_cnt} vs ref {ref['moderate_count']}")
    if abs(ele_cnt - ref["elevated_count"]) > 1: stale_flags.append(f"elevated_count {ele_cnt} vs ref {ref['elevated_count']}")

    if stale_flags:
        print("\n⚠️  STALENESS WARNING — exported_anomaly_scores.json does NOT match")
        print("   the reference values Dev 2 confirmed are current:")
        for f in stale_flags:
            print(f"     • {f}")
        print()
        print("   Dev 2's reference: median=0.34  mean=0.37  moderate=11/80  elevated=4/80")
        print("   This file:         "
              f"median={med:.4f}  mean={mean:.4f}  "
              f"moderate={mod_cnt}/{n}  elevated={ele_cnt}/{n}")
        print()
        print("   ⛔  Re-export a fresh copy from the live Render URL before")
        print("       relying on the precision/recall numbers below.")
        print()
        return False

    print("\n✅ Staleness check PASSED — export matches Dev 2's reference values.")
    return True


# ---------------------------------------------------------------------------
# Distribution summary
# ---------------------------------------------------------------------------

def print_distribution(scores: List[float], n: int) -> None:
    med     = statistics.median(scores)
    mean    = statistics.mean(scores)
    std     = statistics.stdev(scores) if len(scores) > 1 else 0.0
    lo, hi  = min(scores), max(scores)
    mod_cnt = sum(1 for s in scores if s >= 0.55)
    ele_cnt = sum(1 for s in scores if s >= 0.70)

    print(f"\n{'─'*70}")
    print("SCORE DISTRIBUTION SUMMARY")
    print(f"{'─'*70}")
    print(f"  Athletes scored : {n}")
    print(f"  Min / Max       : {lo:.4f} / {hi:.4f}")
    print(f"  Mean ± Std      : {mean:.4f} ± {std:.4f}")
    print(f"  Median          : {med:.4f}")
    print(f"  Moderate ≥0.55  : {mod_cnt}/{n}  ({pct(mod_cnt/n)})")
    print(f"  Elevated  ≥0.70 : {ele_cnt}/{n}  ({pct(ele_cnt/n)})")


# ---------------------------------------------------------------------------
# Precision / Recall / FPR table
# ---------------------------------------------------------------------------

def compute_metrics(
    scores_by_id: Dict[int, float],
    gt_anomalous: set,
    all_ids: set,
    threshold: float,
) -> Dict[str, float]:
    predicted_pos = {aid for aid, s in scores_by_id.items() if s >= threshold}
    actual_pos    = gt_anomalous

    tp = len(predicted_pos & actual_pos)
    fp = len(predicted_pos - actual_pos)
    fn = len(actual_pos - predicted_pos)
    tn = len((all_ids - predicted_pos) - actual_pos)

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr       = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)

    return {
        "threshold": threshold,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        "precision": round4(precision),
        "recall":    round4(recall),
        "fpr":       round4(fpr),
        "f1":        round4(f1),
    }


def print_metrics_table(rows: List[Dict]) -> None:
    print(f"\n{'─'*70}")
    print("PRECISION / RECALL / FPR  (at four thresholds)")
    print(f"{'─'*70}")
    hdr = (f"{'Threshold':>10}  {'Precision':>10}  {'Recall':>7}  "
           f"{'FPR':>7}  {'F1':>7}  {'TP':>4}  {'FP':>4}  {'FN':>4}  {'TN':>4}")
    print(hdr)
    print("─" * len(hdr))
    for r in rows:
        print(
            f"{r['threshold']:>10.2f}  "
            f"{pct(r['precision']):>10}  "
            f"{pct(r['recall']):>7}  "
            f"{pct(r['fpr']):>7}  "
            f"{pct(r['f1']):>7}  "
            f"{r['tp']:>4}  {r['fp']:>4}  {r['fn']:>4}  {r['tn']:>4}"
        )


# ---------------------------------------------------------------------------
# Per-pattern recall breakdown
# ---------------------------------------------------------------------------

def print_pattern_recall(
    pattern_athletes: Dict[str, List[int]],
    scores_by_id: Dict[int, float],
    threshold: float = 0.50,
) -> Dict[str, Dict]:
    print(f"\n{'─'*70}")
    print(f"RECALL BY ANOMALY PATTERN  (threshold = {threshold})")
    print(f"{'─'*70}")

    results = {}
    for pattern, ids in sorted(pattern_athletes.items()):
        if not ids:
            continue
        caught   = [aid for aid in ids if scores_by_id.get(aid, 0.0) >= threshold]
        recall   = len(caught) / len(ids) if ids else 0.0
        avg_score = (sum(scores_by_id.get(a, 0.0) for a in ids) / len(ids)) if ids else 0.0

        print(f"\n  Pattern: {pattern}")
        print(f"    flagged athletes : {len(ids)}")
        print(f"    caught at ≥{threshold} : {len(caught)}/{len(ids)}  recall={pct(recall)}")
        print(f"    avg anomaly score: {avg_score:.4f}")

        score_pairs = [(aid, round4(scores_by_id.get(aid, 0.0))) for aid in ids]
        score_pairs.sort(key=lambda x: -x[1])
        print(f"    scores (athlete_id → score): {score_pairs}")

        results[pattern] = {
            "n_flagged":  len(ids),
            "n_caught":   len(caught),
            "recall":     round4(recall),
            "avg_score":  round4(avg_score),
        }

    return results


# ---------------------------------------------------------------------------
# Known-limitation check
# ---------------------------------------------------------------------------

def check_known_limitations(pattern_recall: Dict[str, Dict]) -> None:
    print(f"\n{'─'*70}")
    print("KNOWN-LIMITATION CONFIRMATION")
    print(f"{'─'*70}")
    print("  Expected framing: transfusion = reliably caught;")
    print("                    EPO / steroid micro-dosing = under-detected.")
    print()

    transfusion_key = None
    epo_key = None
    steroid_key = None
    for k in pattern_recall:
        kl = k.lower()
        if "transfusion" in kl: transfusion_key = k
        if "epo"         in kl: epo_key = k
        if "steroid"     in kl: steroid_key = k

    def _report(label: str, key: Optional[str], expect_high: bool) -> bool:
        if key is None:
            print(f"  ⚠️  Pattern '{label}' not found in ground_truth — skipping.")
            return True
        r = pattern_recall[key]
        recall = r["recall"]
        if expect_high:
            ok = recall >= 0.60
            icon = "✅" if ok else "❌"
            note = "reliably caught" if ok else "LOWER THAN EXPECTED — investigate"
        else:
            ok = recall <= 0.50
            icon = "✅" if ok else "⚠️ "
            note = "under-detected (expected)" if ok else "HIGHER THAN EXPECTED — something may have shifted"
        print(f"  {icon} {label:30s}  recall={pct(recall):>7}  → {note}")
        return ok

    t_ok = _report("transfusion",           transfusion_key, expect_high=True)
    e_ok = _report("epo micro-dosing",       epo_key,         expect_high=False)
    s_ok = _report("steroid micro-dosing",   steroid_key,     expect_high=False)

    overall = t_ok and e_ok and s_ok
    print()
    if overall:
        print("  ✅ Known-limitation framing HOLDS — no unexpected pattern shifts.")
    else:
        print("  ⚠️  One or more pattern recalls deviated from expected framing.")
        print("       Flag this to Dev 1 before committing.")


# ---------------------------------------------------------------------------
# Before / After comparison
# ---------------------------------------------------------------------------

def print_before_after(current_rows: List[Dict]) -> None:
    print(f"\n{'─'*70}")
    print("BEFORE / AFTER COMPARISON  (Day-4 baseline vs current)")
    print(f"{'─'*70}")

    has_baseline = any(
        v["precision"] is not None
        for v in DAY4_BASELINE["thresholds"].values()
    )

    if not has_baseline:
        print("  ⚠️  No saved Day-4 baseline found (notebook output was never persisted")
        print("      to a JSON file).  Cannot produce numeric before/after deltas.")
        print()
        print("  Current numbers (for future reference):")
        for r in current_rows:
            print(
                f"    threshold={r['threshold']:.2f}  "
                f"precision={pct(r['precision'])}  "
                f"recall={pct(r['recall'])}  "
                f"fpr={pct(r['fpr'])}"
            )
    else:
        hdr = f"  {'Threshold':>10}  {'Δ Precision':>12}  {'Δ Recall':>9}  {'Δ FPR':>9}"
        print(hdr)
        print("  " + "─" * (len(hdr) - 2))
        for r in current_rows:
            t   = r["threshold"]
            bl  = DAY4_BASELINE["thresholds"].get(t, {})
            d_p = (r["precision"] - bl["precision"]) if bl.get("precision") is not None else None
            d_r = (r["recall"]    - bl["recall"])    if bl.get("recall")    is not None else None
            d_f = (r["fpr"]       - bl["fpr"])       if bl.get("fpr")       is not None else None
            fmt = lambda v: (f"{v:+.1%}" if v is not None else "   N/A")
            print(f"  {t:>10.2f}  {fmt(d_p):>12}  {fmt(d_r):>9}  {fmt(d_f):>9}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(SEP)
    print("EVALUATION — Adaptive Anti-Doping Defense Engine")
    print("Precision / Recall / Pattern Breakdown against ground_truth.json")
    print(SEP)

    # ── Load ──────────────────────────────────────────────────────────────
    scores_raw: List[dict] = load_json(SCORES_PATH)
    gt_raw:     List[dict] = load_json(GT_PATH)

    # ── Build lookup structures ────────────────────────────────────────────
    scores_by_id: Dict[int, float] = {
        row["id"]: row["latest_anomaly_score"]
        for row in scores_raw
        if row.get("scored") and row.get("latest_anomaly_score") is not None
    }

    gt_anomalous: set = {
        row["athlete_id"]
        for row in gt_raw
        if row.get("is_synthetic_anomaly") is True
    }

    pattern_athletes: Dict[str, List[int]] = {}
    for row in gt_raw:
        if row.get("is_synthetic_anomaly") is True and row.get("pattern_type"):
            pattern_athletes.setdefault(row["pattern_type"], []).append(row["athlete_id"])

    all_ids = {row["id"] for row in scores_raw}

    n      = len(scores_raw)
    scores = [scores_by_id[aid] for aid in scores_by_id]

    # ── Staleness check ────────────────────────────────────────────────────
    is_current = check_staleness(scores, n)

    # ── Distribution ──────────────────────────────────────────────────────
    print_distribution(scores, n)

    # ── Metrics table ─────────────────────────────────────────────────────
    metric_rows = [
        compute_metrics(scores_by_id, gt_anomalous, all_ids, t)
        for t in THRESHOLDS
    ]
    print_metrics_table(metric_rows)

    # ── Per-pattern recall ─────────────────────────────────────────────────
    pattern_recall = print_pattern_recall(pattern_athletes, scores_by_id, threshold=0.50)

    # ── Known-limitation check ─────────────────────────────────────────────
    check_known_limitations(pattern_recall)

    # ── Before / After ────────────────────────────────────────────────────
    print_before_after(metric_rows)

    # ── Save results snapshot ─────────────────────────────────────────────
    snapshot = {
        "staleness_check_passed": is_current,
        "n_athletes": n,
        "metrics_by_threshold": metric_rows,
        "pattern_recall": pattern_recall,
    }
    with open(RESULTS_OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(snapshot, fh, indent=2)

    print(f"\n{'─'*70}")
    print(f"Results snapshot → {RESULTS_OUT_PATH.relative_to(REPO_ROOT)}")
    print()
    if not is_current:
        print("🚨  OVERALL VERDICT: STALE DATA — re-export before committing.")
    else:
        print("✅  OVERALL VERDICT: Data is current. Review metrics above.")
    print(SEP)


if __name__ == "__main__":
    main()
