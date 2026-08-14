"""Throwaway visual sanity check for v0.5 autocorrelated Hb trajectories."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
PLOT_DIR = REPO_ROOT / "ml" / "plots"
OUTPUT_PATH = PLOT_DIR / "hb_check_v05.png"

# Plot first 3 athletes by id
ATHLETE_IDS = [1, 2, 3]


def main() -> None:
    with (DATA_DIR / "athletes.json").open(encoding="utf-8") as f:
        athletes = {a["id"]: a for a in json.load(f)}
    with (DATA_DIR / "samples.json").open(encoding="utf-8") as f:
        samples = json.load(f)

    by_athlete: dict[int, list[dict]] = defaultdict(list)
    for sample in samples:
        by_athlete[sample["athlete_id"]].append(sample)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for athlete_id in ATHLETE_IDS:
        rows = sorted(by_athlete[athlete_id], key=lambda s: s["date"])
        dates = [s["date"] for s in rows]
        hb = [s["hb"] for s in rows]
        name = athletes[athlete_id]["name"]
        ax.plot(dates, hb, marker="o", linewidth=2, label=f"{name} (id={athlete_id})")

    ax.set_title("Hb trajectories — v0.5 autocorrelated walk")
    ax.set_xlabel("Sample date")
    ax.set_ylabel("Hb (g/dL)")
    ax.set_ylim(11.5, 18.5)
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    plt.tight_layout()

    PLOT_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=120)
    plt.close(fig)
    print(f"Saved plot -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
