"""Cumulative sum (CUSUM) control chart detector.

Complements the single-sample Mahalanobis distance in `app.ml.anomaly`,
which only looks at the athlete's *latest* sample against their posterior
baseline. That check has a blind spot: a slow, sustained drift (e.g. a
small dose of EPO nudging Hb up by a fraction of a std-dev every sample)
never produces a single observation extreme enough to cross a z-score
threshold, even though the cumulative deviation is real and directional.

CUSUM tracks two running sums per biomarker, standardized against a fixed
baseline mean/std:

    C+_i = max(0, C+_{i-1} + (x_i - mean)/std - k)
    C-_i = max(0, C-_{i-1} - (x_i - mean)/std - k)

with C+_0 = C-_0 = 0. `k` (the slack) is subtracted every step, so small
noise-level deviations decay back toward 0 instead of accumulating; only a
sustained drift larger than `k` std-devs per step builds up over time. A
flag fires the first time either sum exceeds `h` (the decision threshold).

Both `k` and `h` are expressed in std-dev units, following this module's
convention of standardizing against `baseline_std` before accumulating.
"""

from __future__ import annotations


def compute_cusum(
    observations: list[float],
    baseline_mean: float,
    baseline_std: float,
    k: float = 0.5,
    h: float = 5.0,
) -> dict:
    """Two-sided CUSUM over `observations` against a fixed baseline.

    Args:
        observations: ordered sequence of observed values (e.g. ascending
            by date), standardized internally against `baseline_mean` and
            `baseline_std`.
        baseline_mean: fixed reference mean (e.g. the athlete's prior or
            posterior mean for this biomarker).
        baseline_std: fixed reference std-dev. Must be positive.
        k: slack parameter in std-dev units — the per-step drift tolerated
            before it starts accumulating.
        h: decision threshold in std-dev units — a cumulative sum
            exceeding this triggers a flag.

    Returns:
        {
            "cusum_upper": list[float],   # C+_i for each i, same length as observations
            "cusum_lower": list[float],   # C-_i for each i, same length as observations
            "flagged": bool,              # True if either sum ever exceeded h
            "flagged_at_index": int | None,  # index of first crossing, else None
            "threshold": float,           # echoes h
        }
    """
    if baseline_std <= 0:
        raise ValueError("baseline_std must be positive")

    cusum_upper: list[float] = []
    cusum_lower: list[float] = []
    flagged_at_index: int | None = None

    upper = 0.0
    lower = 0.0
    for i, x in enumerate(observations):
        z = (x - baseline_mean) / baseline_std
        upper = max(0.0, upper + z - k)
        lower = max(0.0, lower - z - k)
        cusum_upper.append(upper)
        cusum_lower.append(lower)

        if flagged_at_index is None and (upper > h or lower > h):
            flagged_at_index = i

    return {
        "cusum_upper": cusum_upper,
        "cusum_lower": cusum_lower,
        "flagged": flagged_at_index is not None,
        "flagged_at_index": flagged_at_index,
        "threshold": h,
    }
