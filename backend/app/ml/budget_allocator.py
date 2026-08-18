"""Greedy budget allocator over `app.ml.action_engine.compute_recommendation`
candidates.

Given a cohort's worth of `{athlete_id, value_score, cost, ...}` candidates
(one per athlete, `value_score`/`cost` as computed by
`action_engine.compute_value_score`) and a fixed investigation budget,
picks which athletes to actually act on.

This is a **greedy value/cost-ratio approximation of 0/1 knapsack**, not an
exact solve (e.g. via dynamic programming). That's a deliberate tradeoff,
not a shortcut taken for lack of time:

- **Explainability**: "we funded the highest bang-per-budget-unit actions
  first, in order, until the budget ran out" is a one-sentence
  justification an investigator/auditor can verify by eye against the
  sorted list. An exact DP knapsack solve produces a selected *set* with no
  equivalently simple "why this one and not that one" story -- it's a
  global optimization, not a ranking, so justifying any single inclusion
  or exclusion means re-deriving the whole table.
- **Speed**: this greedy approach is O(n log n) (the sort dominates).
  Exact 0/1 knapsack is pseudo-polynomial (O(n * budget) via DP), which
  is fine for a one-off batch job but is a worse fit for something that
  can be recomputed on demand as new anomaly scores/candidates come in.
- **Marginal optimality gain**: the ratio-greedy solution is provably
  close to the fractional-relaxation optimum (which upper-bounds the true
  0/1 optimum), and in practice differs from the exact solution only when
  a large single item's cost is a big fraction of the whole budget and
  its value doesn't decompose into smaller, similarly-efficient chunks.
  For a triage tool selecting many small-relative-to-budget investigation
  actions, that gap is usually negligible next to the interpretability
  this buys.

**Why sort by `value_score / cost` and not raw `value_score`**: raw
`value_score` ranks by "how good is this action," ignoring how much of the
budget it consumes. That can crowd out several cheap, nearly-as-valuable
actions in favor of one expensive one. Concrete divergence:

    Action A: cost=5,  value_score=0.6  -> ratio = 0.12
    Action B: cost=20, value_score=0.9  -> ratio = 0.045

Raw-value sorting puts B first (0.9 > 0.6). Ratio sorting puts A first
(0.12 > 0.045). With a budget of 20: raw-value selection spends the whole
budget on B alone for a total value of 0.9. Ratio selection buys A (cost
5, value 0.6) and can still afford ~15 more budget's worth of other
efficient actions -- see `backend/tests/test_budget_allocator.py`'s
divergence test for a worked cohort where ratio selection ends up with
strictly more total value than raw-value selection would have, for the
same budget.
"""

from __future__ import annotations


def allocate_budget(candidates: list[dict], budget: int) -> dict:
    """Greedy knapsack-style allocation: select candidates in descending
    `value_score / cost` order, taking each one that still fits in the
    remaining budget.

    Candidates whose `cost` alone exceeds the *remaining* budget are
    skipped, not treated as a stopping point -- a later, cheaper candidate
    further down the ratio-sorted list may still fit. This is standard
    greedy-knapsack behavior (as opposed to first-fit, which would stop at
    the first candidate that doesn't fit).

    Args:
        candidates: each a dict with at least `athlete_id` (int),
            `value_score` (float), `cost` (int). Every `cost` must be
            strictly positive -- a zero/negative cost makes the value/cost
            ratio undefined (or nonsensical for "how much budget does this
            spend").
        budget: total budget available to spend, in the same units as
            each candidate's `cost`.

    Returns:
        {
            "selected": list[dict],       # {athlete_id, value_score, cost, cumulative_cost_after}, in selection order
            "total_cost": int,            # sum of selected candidates' cost
            "total_value": float,         # sum of selected candidates' value_score
            "candidates_considered": int, # len(candidates)
            "candidates_selected": int,   # len(selected)
        }

    Raises:
        ValueError: if any candidate's `cost` is <= 0.
    """
    for candidate in candidates:
        if candidate["cost"] <= 0:
            raise ValueError(
                f"candidate athlete_id={candidate.get('athlete_id')!r} has non-positive "
                f"cost {candidate['cost']!r}; value/cost ratio is undefined"
            )

    ranked = sorted(
        candidates, key=lambda candidate: candidate["value_score"] / candidate["cost"], reverse=True
    )

    selected: list[dict] = []
    cumulative_cost = 0
    remaining_budget = budget

    for candidate in ranked:
        cost = candidate["cost"]
        if cost > remaining_budget:
            continue

        cumulative_cost += cost
        remaining_budget -= cost
        selected.append(
            {
                "athlete_id": candidate["athlete_id"],
                "value_score": candidate["value_score"],
                "cost": cost,
                "cumulative_cost_after": cumulative_cost,
            }
        )

    return {
        "selected": selected,
        "total_cost": cumulative_cost,
        "total_value": sum(item["value_score"] for item in selected),
        "candidates_considered": len(candidates),
        "candidates_selected": len(selected),
    }
