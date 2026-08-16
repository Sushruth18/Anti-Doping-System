"""One-off local dev-DB repair: wipe all `Anomaly` rows and re-run
`backfill_anomalies()` from scratch so every athlete gets freshly scored
via `get_anomaly_score()` against the current `baseline.py` math.

Why this is needed: `backfill_anomalies()` dedupes on `sample_id`, so an
athlete whose latest sample was already scored under an older version of
the posterior math (e.g. before the `BIOMARKER_CV`-based `obs_var` fix)
never gets rescored by a normal pass -- it's still "already scored" by
`sample_id`, just with a stale `mahalanobis_distance`.
`rescore_all_anomalies()`'s `--force` mode doesn't help either: it only
reapplies the current `ANOMALY_SCORE_SCALE` to each row's already-persisted
`mahalanobis_distance`, it does not recompute that distance. Deleting the
rows and re-running the normal (non-force) `backfill_anomalies()` against
an empty table is the only path that forces a real recompute.

This mirrors what happens naturally on every Render boot (render.yaml's
startCommand chains `seed.py` -> `backfill_anomalies.py` fresh every
time), for a local `app.db` that's fallen out of sync between boots.
Local-only tool, not part of any deploy/startup path itself.

Does not modify `backfill_anomalies.py` -- `backfill_anomalies()` and
`rescore_all_anomalies()` are both correct for their own intended purposes
(fresh-sample scoring and scale-constant-only rescoring, respectively) and
are used here as-is, not changed.
"""

from __future__ import annotations

import os
import sys

# Allow running as a plain script (`python rescore_from_scratch.py`) as
# well as a module (`python -m app.db.rescore_from_scratch`), same
# approach as seed.py, init_db.py, and backfill_anomalies.py.
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _BACKEND_DIR)

from app.db.backfill_anomalies import backfill_anomalies  # noqa: E402
from app.db.models import Anomaly, Athlete  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402

_REPORT_ATHLETE_IDS = (4, 44, 65)


def _print_report_athletes(db, label: str) -> None:
    for athlete_id in _REPORT_ATHLETE_IDS:
        athlete = db.query(Athlete).filter(Athlete.id == athlete_id).first()
        name = athlete.name if athlete else f"athlete {athlete_id}"
        row = (
            db.query(Anomaly)
            .filter(Anomaly.athlete_id == athlete_id)
            .order_by(Anomaly.created_at.desc(), Anomaly.id.desc())
            .first()
        )
        if row is None:
            print(f"  [{label}] {name} (id={athlete_id}): no Anomaly row")
        else:
            print(
                f"  [{label}] {name} (id={athlete_id}): "
                f"mahalanobis_distance={row.mahalanobis_distance!r} "
                f"anomaly_score={row.anomaly_score!r}"
            )


def run() -> None:
    db = SessionLocal()
    try:
        before_count = db.query(Anomaly).count()
        print(f"[rescore_from_scratch] before: {before_count} Anomaly rows")
        _print_report_athletes(db, "before")

        deleted = db.query(Anomaly).delete()
        db.commit()
        print(f"[rescore_from_scratch] deleted {deleted} Anomaly rows")

        summary = backfill_anomalies(db)
        print(f"[rescore_from_scratch] backfill_anomalies: {summary}")

        after_count = db.query(Anomaly).count()
        print(f"[rescore_from_scratch] after: {after_count} Anomaly rows")
        _print_report_athletes(db, "after")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
