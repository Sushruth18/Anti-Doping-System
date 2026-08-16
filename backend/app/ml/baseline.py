"""Ported from ml/prototype_baseline.py::update_posterior (Dev 2, validated
via that script's validate_convergence() — see CLAUDE.md's app/ml/ vs /ml
note: this is a copy of the validated math, not a live import from /ml).
"""

from __future__ import annotations

import json
from typing import Any, Iterable, Iterator, Mapping

from sqlalchemy.orm import Session

from app.db.models import Athlete, Sample

BIOMARKERS = ("hb", "hct", "ret_pct", "off_score", "te_ratio")

# Per-biomarker analytical measurement-noise CV (coefficient of variation),
# used by `compute_obs_var` below as `obs_var = (CV * prior_mean) ** 2`.
# Replaces the old single fixed-fraction-of-prior-std placeholder
# (`OBS_VAR_STD_FRACTION = 0.25`), which made every biomarker's obs_var a
# fixed multiple of its own prior variance regardless of actual assay
# precision — that shape is also what made `ml.uncertainty`'s
# posterior_var/prior_var ratio degenerate to a single constant across the
# whole seeded cohort (see that module's docstring).
#
# `off_score` deliberately has NO entry here: it isn't an independently
# measured biomarker, it's mathematically derived from `hb` and `ret_pct`
# (`off_score = hb_g_dL*10 - 60*sqrt(ret_pct)`, see CLAUDE.md's locked
# formula), so its measurement noise is derived via error propagation from
# hb's and ret_pct's own CVs instead of an independent CV constant — see
# `compute_obs_var`.
#
# Sources:
#   hb=0.018, hct=0.017: Westgard QC / Ricos et al. Biological Variation
#     Database — desirable analytical CV for hemoglobin (1.84%, 13 pooled
#     studies) and hematocrit (1.74%, 11 pooled studies).
#     https://www.westgard.com/biodatabase2.htm
#   ret_pct=0.12: no single desirable-BV-database figure found; grounded
#     instead in automated hematology analyzer reticulocyte-percentage
#     precision literature — Sysmex RAM-1 <5% CV, Sysmex XN-9000 <10% CV
#     acceptance criterion, Sysmex XR9000 study showing CV climbing toward
#     ~20% at low reticulocyte concentrations. This dataset's ret_pct values
#     (0.8-2.5%) sit at the low end of physiological range, where the
#     literature shows CV trending toward the higher end of that band, so
#     12% is a middle-to-upper estimate rather than the optimistic <10%
#     figure.
#   te_ratio=0.18: not one published number — combined via error
#     propagation of two individual analyte uncertainties. BIPM CCQM-K69 key
#     comparison reports ~7.0% measurement uncertainty for testosterone
#     glucuronide in urine; PATH consensus (Vesper et al., Clin Chem 2012)
#     recommends 5.3% desirable analytical CV for testosterone by
#     immunoassay. Epitestosterone typically carries higher relative
#     uncertainty than testosterone (lower, more variable urinary
#     concentration) with no clean published figure, so it's treated as
#     somewhat noisier than T; combining via CV_ratio ~= sqrt(CV_T**2 +
#     CV_E**2) lands around 18%.
#
# Known limitation: like the placeholder it replaces, these are still
# reasonable estimates from general analytical-chemistry literature, not
# values validated against this project's own assay data or WADA's
# unpublished internal ABP operating-guideline specifications (which aren't
# public). Revisit if/when real lab-specific CVs become available.
BIOMARKER_CV: dict[str, float] = {
    "hb": 0.018,
    "hct": 0.017,
    "ret_pct": 0.12,
    "te_ratio": 0.18,
}


def compute_obs_var(biomarker: str, baseline_data: Mapping[str, Mapping[str, float]]) -> float:
    """Measurement-noise variance for `biomarker`, from CV and prior mean.

    For every biomarker except `off_score`: `obs_var = (CV * prior_mean) ** 2`,
    where `CV` comes from `BIOMARKER_CV` and `prior_mean` is that biomarker's
    own `baseline_data[biomarker]["mean"]`.

    For `off_score`, derived via error propagation instead (delta method,
    treating hb's and ret_pct's measurement noise as independent), from
    `off_score = hb_g_dL*10 - 60*sqrt(ret_pct)`:

        d(off_score)/d(hb)      = 10
        d(off_score)/d(ret_pct) = -60 / (2*sqrt(ret_pct)) = -30/sqrt(ret_pct)

        Var(off_score) = 10**2 * Var(hb) + (30/sqrt(ret_pct))**2 * Var(ret_pct)
                        = 100 * Var(hb) + (900 / ret_pct) * Var(ret_pct)

    evaluated at this athlete's own prior means for hb and ret_pct.

    Args:
        biomarker: one of `BIOMARKERS`.
        baseline_data: the full parsed `Athlete.baseline_prior_json` —
            `{biomarker: {"mean": float, "std": float}}` for every biomarker
            in `BIOMARKERS`. `off_score` needs `hb`'s and `ret_pct`'s entries
            in addition to its own, so the full mapping is required rather
            than just this biomarker's own prior entry.

    Returns:
        The measurement-noise variance, in that biomarker's own squared
        units.
    """
    if biomarker == "off_score":
        ret_pct_mean = baseline_data["ret_pct"]["mean"]
        var_hb = compute_obs_var("hb", baseline_data)
        var_ret_pct = compute_obs_var("ret_pct", baseline_data)
        return 100 * var_hb + (900 / ret_pct_mean) * var_ret_pct

    cv = BIOMARKER_CV[biomarker]
    prior_mean = baseline_data[biomarker]["mean"]
    return (cv * prior_mean) ** 2


def update_posterior(
    prior_mean: float,
    prior_var: float,
    obs: float,
    obs_var: float,
) -> tuple[float, float]:
    """Normal-Normal conjugate update for a single scalar observation.

    Given prior N(prior_mean, prior_var) and observation N(obs, obs_var):

        posterior_precision = 1/prior_var + 1/obs_var
        posterior_var     = 1 / posterior_precision
        posterior_mean      = posterior_var * (prior_mean/prior_var + obs/obs_var)

    Equivalently, posterior_mean is the precision-weighted average of
    prior_mean and obs.

    Returns:
        (posterior_mean, posterior_var)
    """
    if prior_var <= 0 or obs_var <= 0:
        raise ValueError("prior_var and obs_var must be positive")

    prior_precision = 1.0 / prior_var
    obs_precision = 1.0 / obs_var
    posterior_precision = prior_precision + obs_precision
    posterior_var = 1.0 / posterior_precision
    posterior_mean = posterior_var * (
        (prior_mean * prior_precision) + (obs * obs_precision)
    )
    return posterior_mean, posterior_var


def fold_biomarker_posterior(
    prior_mean: float,
    prior_var: float,
    samples_for_biomarker: Iterable[tuple[Any, float]],
    obs_var: float,
) -> Iterator[tuple[Any, float, float]]:
    """Fold a single biomarker's samples through `update_posterior` in order.

    `samples_for_biomarker` is an iterable of `(label, observed_value)`
    pairs, already ordered the way the caller wants folded (e.g. ascending
    by date). `label` is opaque to this function — not interpreted, just
    echoed back in each yielded tuple so a caller that discards its own
    sample list can still re-associate a fold step with whatever it used to
    order the samples. This function does not know about `Athlete`/`Sample`
    ORM models or `BIOMARKERS`/`BIOMARKER_CV` — plain values in, plain
    values out, no DB dependency.

    Yields:
        `(label, mean, var)` after each fold step, one per item in
        `samples_for_biomarker`, in order. The raw prior itself is never
        yielded — only post-update states.
    """
    mean, var = prior_mean, prior_var
    for label, observed in samples_for_biomarker:
        mean, var = update_posterior(mean, var, observed, obs_var)
        yield label, mean, var


def compute_current_posterior(
    athlete_id: int, db_session: Session
) -> dict[str, tuple[float, float]]:
    """Current per-biomarker posterior for an athlete.

    Starts from `Athlete.baseline_prior_json` as the prior for each
    biomarker in `BIOMARKERS`, then folds every `Sample` row (ordered by
    date ascending) through `fold_biomarker_posterior`, keeping only the
    final `(mean, var)` per biomarker after all samples — not the
    intermediate per-sample values.

    Raises:
        ValueError: if the athlete doesn't exist or has no
            `baseline_prior_json`.

    Returns:
        `biomarker -> (posterior_mean, posterior_var)`, one entry per
        `BIOMARKERS`.
    """
    athlete = db_session.query(Athlete).filter(Athlete.id == athlete_id).first()
    if athlete is None or not athlete.baseline_prior_json:
        raise ValueError(
            f"athlete {athlete_id} not found or has no baseline_prior_json"
        )

    baseline_data = json.loads(athlete.baseline_prior_json)
    samples = (
        db_session.query(Sample)
        .filter(Sample.athlete_id == athlete_id)
        .order_by(Sample.date.asc())
        .all()
    )

    result: dict[str, tuple[float, float]] = {}
    for biomarker in BIOMARKERS:
        prior_entry = baseline_data[biomarker]
        prior_std = prior_entry["std"]
        obs_var = compute_obs_var(biomarker, baseline_data)
        mean, var = prior_entry["mean"], prior_std**2

        samples_for_biomarker = (
            (None, getattr(sample, biomarker)) for sample in samples
        )
        for _label, mean, var in fold_biomarker_posterior(
            mean, var, samples_for_biomarker, obs_var
        ):
            pass  # only the final (mean, var) matters here

        result[biomarker] = (mean, var)

    return result
