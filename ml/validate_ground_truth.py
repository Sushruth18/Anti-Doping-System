"""
validate_ground_truth.py -- Day 4
==================================
Validates data/ground_truth.json against the ground_truth table spec in
docs/schema.md.

Schema spec (docs/schema.md lines 169-173):
  Column                 Type      Nullable
  athlete_id             Integer   No        PK, FK -> athletes.id
  is_synthetic_anomaly   Boolean   No
  pattern_type           String    Yes       Null when is_synthetic_anomaly=False

Checks performed:
  1. Top-level structure is a list (not a dict keyed by pattern_type)
  2. Every row has exactly the three required fields -- no extras, no missing
  3. Field types match schema spec (int / bool / str-or-None)
  4. athlete_id values are unique (PK constraint)
  5. Every athlete_id exists in data/athletes.json (FK constraint)
  6. pattern_type is None when is_synthetic_anomaly=False,
     and a non-empty string when is_synthetic_anomaly=True

Run from repo root:
    python3 ml/validate_ground_truth.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT     = Path(__file__).resolve().parent.parent
GT_PATH       = REPO_ROOT / "data" / "ground_truth.json"
ATHLETES_PATH = REPO_ROOT / "data" / "athletes.json"

REQUIRED_FIELDS = {"athlete_id", "is_synthetic_anomaly", "pattern_type"}


def load_json(path: Path) -> object:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate() -> tuple[bool, list[str]]:
    errors: list[str] = []

    raw_gt   = load_json(GT_PATH)
    athletes = load_json(ATHLETES_PATH)
    valid_athlete_ids: set[int] = {a["id"] for a in athletes}

    # Check 1: top-level must be a list
    if not isinstance(raw_gt, list):
        errors.append(
            "SHAPE REGRESSION: ground_truth.json must be a list of row objects, "
            "got {!r}. (Was it accidentally keyed by pattern_type?)".format(
                type(raw_gt).__name__
            )
        )
        return False, errors

    if len(raw_gt) == 0:
        errors.append("ground_truth.json is an empty list -- expected >= 1 rows.")
        return False, errors

    seen_ids: dict[int, int] = {}  # athlete_id -> first row index

    for i, row in enumerate(raw_gt):
        if not isinstance(row, dict):
            errors.append(
                "Row {}: expected a dict object, got {!r}.".format(i, type(row).__name__)
            )
            continue

        actual_fields = set(row.keys())

        # Check 2a: missing fields
        missing = REQUIRED_FIELDS - actual_fields
        if missing:
            errors.append("Row {}: missing fields {}.".format(i, sorted(missing)))

        # Check 2b: extra fields
        extra = actual_fields - REQUIRED_FIELDS
        if extra:
            errors.append("Row {}: unexpected extra fields {}.".format(i, sorted(extra)))

        present = actual_fields & REQUIRED_FIELDS

        # Check 3a: athlete_id must be int (not bool, which is int subclass in Python)
        if "athlete_id" in present:
            aid = row["athlete_id"]
            if not isinstance(aid, int) or isinstance(aid, bool):
                errors.append(
                    "Row {}: athlete_id must be Integer, got {!r} = {!r}.".format(
                        i, type(aid).__name__, aid
                    )
                )
            else:
                # Check 4: PK uniqueness
                if aid in seen_ids:
                    errors.append(
                        "Row {}: duplicate athlete_id={} (first seen at row {}).".format(
                            i, aid, seen_ids[aid]
                        )
                    )
                else:
                    seen_ids[aid] = i

                # Check 5: FK -> athletes.id
                if aid not in valid_athlete_ids:
                    errors.append(
                        "Row {}: athlete_id={} does not exist in athletes.json.".format(
                            i, aid
                        )
                    )

        # Check 3b: is_synthetic_anomaly must be bool
        if "is_synthetic_anomaly" in present:
            isa = row["is_synthetic_anomaly"]
            if not isinstance(isa, bool):
                errors.append(
                    "Row {}: is_synthetic_anomaly must be Boolean, "
                    "got {!r} = {!r}.".format(i, type(isa).__name__, isa)
                )

        # Check 3c + 6: pattern_type type and consistency
        if "pattern_type" in present and "is_synthetic_anomaly" in present:
            pt  = row["pattern_type"]
            isa = row.get("is_synthetic_anomaly")

            if not isinstance(isa, bool):
                pass  # type error already reported above
            elif isa is False:
                if pt is not None:
                    errors.append(
                        "Row {} (athlete_id={}): is_synthetic_anomaly=False "
                        "but pattern_type={!r} (expected null).".format(
                            i, row.get("athlete_id"), pt
                        )
                    )
            else:
                if pt is None:
                    errors.append(
                        "Row {} (athlete_id={}): is_synthetic_anomaly=True "
                        "but pattern_type is null (expected a non-empty string).".format(
                            i, row.get("athlete_id")
                        )
                    )
                elif not isinstance(pt, str):
                    errors.append(
                        "Row {} (athlete_id={}): pattern_type must be String or null, "
                        "got {!r} = {!r}.".format(
                            i, row.get("athlete_id"), type(pt).__name__, pt
                        )
                    )
                elif pt.strip() == "":
                    errors.append(
                        "Row {} (athlete_id={}): pattern_type is empty string "
                        "(expected non-empty or null).".format(i, row.get("athlete_id"))
                    )

    return (len(errors) == 0), errors


def main() -> None:
    print("=" * 60)
    print("validate_ground_truth.py -- Day 4")
    print("  GT file      : {}".format(GT_PATH.relative_to(REPO_ROOT)))
    print("  Athletes file: {}".format(ATHLETES_PATH.relative_to(REPO_ROOT)))
    print("=" * 60)

    passed, errors = validate()

    raw_gt = load_json(GT_PATH)
    if isinstance(raw_gt, list) and raw_gt:
        n_total   = len(raw_gt)
        n_anomaly = sum(
            1 for r in raw_gt
            if isinstance(r, dict) and r.get("is_synthetic_anomaly") is True
        )
        n_clean = n_total - n_anomaly
        print("\nRows       : {}".format(n_total))
        print("  anomalous: {}".format(n_anomaly))
        print("  clean    : {}".format(n_clean))

    print()
    if passed:
        print("RESULT: PASS")
        print("  All rows conform to schema.md ground_truth spec.")
    else:
        print("RESULT: FAIL  ({} error(s))".format(len(errors)))
        print()
        for err in errors:
            print("  ERROR: {}".format(err))

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
