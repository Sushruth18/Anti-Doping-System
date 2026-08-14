"""Standalone Normal-Normal Bayesian baseline prototype.

Dev 2 validates conjugate update math here before Dev 1 ports
update_posterior() into backend/app/ml/baseline.py (copy-paste + unit test).
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PLOT_PATH = REPO_ROOT / "ml" / "plots" / "baseline_convergence_check.png"

# Fixed lab-measurement noise variance for Hb (g/dL)^2 at prototype stage.
DEFAULT_OBS_VAR = 0.25

# Athlete to demo — Alex Chen (id=1), Cycling, 5 Hb samples in v1 data.
DEMO_ATHLETE_ID = 1
DEMO_BIOMARKER = "hb"


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


def load_hb_series(athlete_id: int) -> tuple[list[float], dict]:
    with (DATA_DIR / "athletes.json").open(encoding="utf-8") as f:
        athletes = {a["id"]: a for a in json.load(f)}
    with (DATA_DIR / "samples.json").open(encoding="utf-8") as f:
        samples = [
            s
            for s in json.load(f)
            if s["athlete_id"] == athlete_id
        ]
    samples.sort(key=lambda s: s["date"])
    hb_values = [s["hb"] for s in samples]
    athlete = athletes[athlete_id]
    prior = json.loads(athlete["baseline_prior_json"])
    return hb_values, athlete | {"prior": prior}


def run_sequential_update(
    hb_series: list[float],
    prior_mean: float,
    prior_std: float,
    obs_var: float,
) -> list[dict]:
    """Apply update_posterior sequentially; each posterior becomes the next prior."""
    rows: list[dict] = []
    mean = prior_mean
    var = prior_std**2

    for i, obs in enumerate(hb_series, start=1):
        mean, var = update_posterior(mean, var, obs, obs_var)
        rows.append(
            {
                "sample": i,
                "observed_hb": obs,
                "posterior_mean": round(mean, 4),
                "posterior_var": round(var, 6),
            }
        )
    return rows


def validate_convergence(
    rows: list[dict],
    prior_mean: float,
    empirical_mean: float,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    variances = [r["posterior_var"] for r in rows]

    for i in range(1, len(variances)):
        if variances[i] > variances[i - 1] + 1e-12:
            errors.append(
                f"P0: posterior variance increased at sample {i + 1}: "
                f"{variances[i - 1]:.6f} -> {variances[i]:.6f}"
            )

    prior_distance = abs(prior_mean - empirical_mean)
    final_distance = abs(rows[-1]["posterior_mean"] - empirical_mean)
    if final_distance >= prior_distance - 1e-9:
        errors.append(
            f"P0: posterior mean did not move closer to empirical mean "
            f"(prior dist={prior_distance:.4f}, final dist={final_distance:.4f})"
        )

    return len(errors) == 0, errors


def save_convergence_plot(
    rows: list[dict],
    empirical_mean: float,
    athlete_name: str,
    out_path: Path,
) -> None:
    posterior_means = [r["posterior_mean"] for r in rows]
    posterior_vars = [r["posterior_var"] for r in rows]
    x = list(range(1, len(rows) + 1))
    obs = [r["observed_hb"] for r in rows]

    fig, (ax_mean, ax_var) = plt.subplots(2, 1, figsize=(8, 6), sharex=True)

    ax_mean.plot(x, obs, "o--", color="#888888", label="Observed Hb", alpha=0.8)
    ax_mean.plot(x, posterior_means, "o-", linewidth=2, label="Posterior mean")
    ax_mean.axhline(empirical_mean, color="#2ca02c", linestyle=":", linewidth=2, label="Empirical mean")
    ax_mean.set_ylabel("Hb (g/dL)")
    ax_mean.set_title(f"Baseline convergence — {athlete_name} (Hb)")
    ax_mean.legend()
    ax_mean.grid(True, alpha=0.3)

    ax_var.plot(x, posterior_vars, "s-", color="#d62728", linewidth=2, label="Posterior variance")
    ax_var.set_xlabel("Sample #")
    ax_var.set_ylabel("Posterior variance")
    ax_var.legend()
    ax_var.grid(True, alpha=0.3)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)


def main() -> None:
    hb_series, athlete = load_hb_series(DEMO_ATHLETE_ID)
    prior_entry = athlete["prior"][DEMO_BIOMARKER]
    prior_mean = prior_entry["mean"]
    prior_std = prior_entry["std"]
    empirical_mean = sum(hb_series) / len(hb_series)

    rows = run_sequential_update(hb_series, prior_mean, prior_std, DEFAULT_OBS_VAR)
    ok, errors = validate_convergence(rows, prior_mean, empirical_mean)

    print("=" * 72)
    print(f"Normal-Normal baseline prototype — athlete {DEMO_ATHLETE_ID} ({athlete['name']})")
    print(f"Sport prior: mean={prior_mean}, std={prior_std}  |  obs_var={DEFAULT_OBS_VAR}")
    print(f"Empirical Hb mean (all {len(hb_series)} samples): {empirical_mean:.4f}")
    print("=" * 72)
    print(f"{'Sample':>6} {'Observed':>10} {'Post. mean':>12} {'Post. var':>12}")
    print("-" * 72)
    for row in rows:
        print(
            f"{row['sample']:>6} {row['observed_hb']:>10.2f} "
            f"{row['posterior_mean']:>12.4f} {row['posterior_var']:>12.6f}"
        )

    print("-" * 72)
    print(f"Final posterior mean: {rows[-1]['posterior_mean']:.4f}")
    print(f"Final posterior var:  {rows[-1]['posterior_var']:.6f}")
    print(f"Variance monotonic:   {'PASS' if ok else 'FAIL'}")
    print(f"Mean toward empirical:{'PASS' if ok else 'FAIL'}")

    save_convergence_plot(rows, empirical_mean, athlete["name"], PLOT_PATH)
    print(f"\nPlot saved -> {PLOT_PATH}")

    if not ok:
        print("\nP0 BLOCKER — convergence validation failed:")
        for err in errors:
            print(f"  - {err}")
        raise SystemExit(1)

    print("\nVALIDATION: PASS")


if __name__ == "__main__":
    main()
