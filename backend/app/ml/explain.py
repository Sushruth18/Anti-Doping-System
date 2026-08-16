"""Template-based (no-LLM) natural-language explanation for a
Recommendation, from the same contributing-biomarker data
`app.ml.action_engine.compute_recommendation` already computes.

Deterministic and rule-based by design -- same explainability requirement
as the rest of `app.ml`. No LLM call, no free-form generation: every
sentence is one of a small number of fixed template shapes, filled in
from the athlete's own `rank_contributing_biomarkers` output.
"""

from __future__ import annotations

from typing import Literal, Sequence, TypedDict

ActionType = Literal[
    "no_action",
    "increase_monitoring",
    "target_test",
    "biological_passport_review",
    "open_case",
]


class ContributingBiomarker(TypedDict):
    biomarker: str
    z_score_squared: float
    deviation_direction: Literal["above", "below"]


# A biomarker's z_score_squared has to clear this bar to be named as a
# contributing driver at all, independent of `action_type`. Chosen from
# the actual z² distribution across the seeded 80-athlete cohort, not
# guessed: every athlete whose action_type tier is above `no_action` has
# a top z_score_squared of at least 6.36, while `no_action`-tier athletes
# range from 0.40 up to 8.28 (the two groups overlap slightly, since
# `action_type` is driven by the aggregate anomaly_score across all 5
# biomarkers, not any single one -- see docs/known-limitations.md's
# biomarker-independence note). 4.0 sits comfortably below that 6.36
# floor, so it never contradicts `action_type` for this cohort, and also
# sits close to the chi-square(1 df) 95% critical value (~3.84) -- the
# conventional "individually notable at 2-sigma" bar for a single squared
# z-score -- giving it a statistical grounding independent of this
# specific dataset too.
NO_CLEAR_DRIVER_Z2_THRESHOLD = 4.0

# Among the top-3 z_score_squared values, the 2nd/3rd must be at least
# this fraction of the top one to get named alongside it -- otherwise
# it's "negligible relative to the top" and dropped. 0.45 is the value
# that separates two real cases from the seeded cohort the way a human
# would read them: Logan Rossi's #3 biomarker (hct, ratio 0.402 to top)
# reads as clearly secondary and is dropped, while Indigo Berg's #3
# (off_score, ratio 0.476 to top) reads as still worth naming and is
# kept. Any value in (0.402, 0.476] draws the same line for those two
# cases; 0.45 was picked as the round number in that range.
RELATIVE_CONTRIBUTION_FLOOR = 0.45

# Deliberately not naming a biomarker just because it happened to rank
# first among five noisy values -- see Taylor Gomez's case (no_action
# tier, top z_score_squared 0.72): a template that always names "the top
# biomarker" would read as a confident flag even when nothing is actually
# unusual.
_NO_DEVIATION_SENTENCE = "No significant deviation detected across monitored biomarkers."

_BIOMARKER_DISPLAY_NAMES: dict[str, str] = {
    "hb": "hemoglobin",
    "hct": "hematocrit",
    "ret_pct": "reticulocyte percentage",
    "off_score": "OFF-score",
    "te_ratio": "T/E ratio",
}

_ACTION_TYPE_DISPLAY_NAMES: dict[str, str] = {
    "no_action": "no action",
    "increase_monitoring": "increased monitoring",
    "target_test": "a targeted test",
    "biological_passport_review": "biological passport review",
    "open_case": "opening a case",
}


def _join_with_and(items: Sequence[str]) -> str:
    """Natural-language list join: "X" / "X and Y" / "X, Y, and Z"."""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return f"{', '.join(items[:-1])}, and {items[-1]}"


def _select_named_biomarkers(
    contributing_biomarkers: Sequence[ContributingBiomarker],
) -> list[ContributingBiomarker]:
    """Top 1-3 contributing biomarkers, dropping any whose
    `z_score_squared` is negligible relative to the top one (see
    `RELATIVE_CONTRIBUTION_FLOOR`).

    Args:
        contributing_biomarkers: assumed already sorted descending by
            `z_score_squared`, same as
            `app.ml.anomaly.rank_contributing_biomarkers`'s output.
    """
    top = contributing_biomarkers[0]
    selected = [top]
    for entry in contributing_biomarkers[1:3]:
        if entry["z_score_squared"] >= RELATIVE_CONTRIBUTION_FLOOR * top["z_score_squared"]:
            selected.append(entry)
    return selected


def explain_recommendation(
    action_type: ActionType,
    contributing_biomarkers: Sequence[ContributingBiomarker],
) -> str:
    """Deterministic, template-based explanation sentence for a
    Recommendation.

    Args:
        action_type: the tier `app.ml.action_engine.select_action_tier`
            picked (or `"no_action"`).
        contributing_biomarkers: `rank_contributing_biomarkers`-shaped
            list (e.g. `get_anomaly_score()["contributing_biomarkers"]`),
            sorted descending by `z_score_squared`. Must be non-empty.

    Returns:
        `_NO_DEVIATION_SENTENCE` if `action_type == "no_action"` OR the
        top biomarker's `z_score_squared` doesn't clear
        `NO_CLEAR_DRIVER_Z2_THRESHOLD` (the second condition is a
        safety net independent of `action_type` -- see that constant's
        comment). Otherwise, a sentence naming the top 1-3 contributing
        biomarkers by `z_score_squared` (via `_select_named_biomarkers`),
        grouped by deviation direction, followed by the recommended
        action, e.g. "Elevated hemoglobin, hematocrit, and OFF-score
        relative to this athlete's established baseline. Recommended
        action: biological passport review."
    """
    top_z2 = contributing_biomarkers[0]["z_score_squared"]
    if action_type == "no_action" or top_z2 < NO_CLEAR_DRIVER_Z2_THRESHOLD:
        return _NO_DEVIATION_SENTENCE

    named = _select_named_biomarkers(contributing_biomarkers)
    above_names = [
        _BIOMARKER_DISPLAY_NAMES[entry["biomarker"]]
        for entry in named
        if entry["deviation_direction"] == "above"
    ]
    below_names = [
        _BIOMARKER_DISPLAY_NAMES[entry["biomarker"]]
        for entry in named
        if entry["deviation_direction"] == "below"
    ]

    clauses = []
    if below_names:
        clauses.append(f"suppressed {_join_with_and(below_names)}")
    if above_names:
        clauses.append(f"elevated {_join_with_and(above_names)}")
    body = " and ".join(clauses)
    body = body[0].upper() + body[1:]

    action_display = _ACTION_TYPE_DISPLAY_NAMES[action_type]
    return f"{body} relative to this athlete's established baseline. Recommended action: {action_display}."
