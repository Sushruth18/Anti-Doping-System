import pytest

from app.ml.budget_allocator import allocate_budget


def test_all_candidates_fit_within_budget_selected_in_ratio_order():
    # ratios: A = 0.6/5 = 0.12, B = 0.3/3 = 0.10, C = 0.9/10 = 0.09
    # total cost 5+3+10 = 18 <= budget 100, so everything fits -- this
    # only exercises the sort order, not the budget cutoff.
    candidates = [
        {"athlete_id": 1, "value_score": 0.6, "cost": 5},
        {"athlete_id": 2, "value_score": 0.3, "cost": 3},
        {"athlete_id": 3, "value_score": 0.9, "cost": 10},
    ]

    result = allocate_budget(candidates, budget=100)

    assert [item["athlete_id"] for item in result["selected"]] == [1, 2, 3]
    assert [item["cumulative_cost_after"] for item in result["selected"]] == [5, 8, 18]
    assert result["total_cost"] == 18
    assert result["total_value"] == pytest.approx(0.6 + 0.3 + 0.9)
    assert result["candidates_considered"] == 3
    assert result["candidates_selected"] == 3


def test_ratio_selection_diverges_from_raw_value_score_selection():
    # X: cost=5,  value_score=0.6 -> ratio 0.12
    # Y: cost=20, value_score=0.9 -> ratio 0.045   (highest raw value_score)
    # Z: cost=10, value_score=0.5 -> ratio 0.05
    # budget = 20
    #
    # Ratio-descending order: X (0.12), Z (0.05), Y (0.045).
    # Greedy walk: take X (cost 5, remaining 15), take Z (cost 10,
    # remaining 5), Y's cost 20 > remaining 5 -> skipped (not a break --
    # there's nothing smaller left to skip past here, but the allocator
    # doesn't stop at Y either way). Selected = [X, Z].
    #   total_cost = 15, total_value = 0.6 + 0.5 = 1.1
    #
    # What raw-value_score-descending selection would have picked instead
    # (NOT what this function returns -- documented here for contrast):
    # order would be Y (0.9), X (0.6), Z (0.5). Greedy walk: take Y (cost
    # 20, remaining 0), X's cost 5 > remaining 0 -> skipped, Z's cost 10 >
    # remaining 0 -> skipped. Selected = [Y] only.
    #   total_cost = 20, total_value = 0.9
    #
    # So for the identical budget, ratio-based selection (this function)
    # yields MORE total value (1.1 > 0.9) by preferring efficient actions
    # over the single highest-scoring-but-expensive one -- the concrete
    # case the module docstring describes.
    candidates = [
        {"athlete_id": 10, "value_score": 0.6, "cost": 5},  # X
        {"athlete_id": 20, "value_score": 0.9, "cost": 20},  # Y
        {"athlete_id": 30, "value_score": 0.5, "cost": 10},  # Z
    ]

    result = allocate_budget(candidates, budget=20)

    assert [item["athlete_id"] for item in result["selected"]] == [10, 30]
    assert [item["cumulative_cost_after"] for item in result["selected"]] == [5, 15]
    assert result["total_cost"] == 15
    assert result["total_value"] == pytest.approx(1.1)
    assert result["candidates_considered"] == 3
    assert result["candidates_selected"] == 2

    # The divergence, made explicit: raw-value selection would have beaten
    # neither total_cost nor total_value here.
    assert result["total_value"] > 0.9  # what raw-value selection alone (just Y) would total


def test_expensive_candidate_is_skipped_not_a_break_when_cheaper_one_still_fits():
    # Highest ratio candidate costs more than the whole budget; a lower-
    # ratio but affordable candidate further down the list must still be
    # picked up -- proves the allocator skips over what doesn't fit rather
    # than stopping at the first miss (first-fit would return nothing
    # here).
    candidates = [
        {"athlete_id": 1, "value_score": 5.0, "cost": 50},  # ratio 0.10, doesn't fit
        {"athlete_id": 2, "value_score": 0.4, "cost": 8},  # ratio 0.05, fits
    ]

    result = allocate_budget(candidates, budget=10)

    assert [item["athlete_id"] for item in result["selected"]] == [2]
    assert result["total_cost"] == 8
    assert result["total_value"] == pytest.approx(0.4)
    assert result["candidates_considered"] == 2
    assert result["candidates_selected"] == 1


def test_empty_candidates_returns_empty_allocation():
    result = allocate_budget([], budget=50)

    assert result == {
        "selected": [],
        "total_cost": 0,
        "total_value": 0,
        "candidates_considered": 0,
        "candidates_selected": 0,
    }


def test_zero_or_negative_cost_candidate_raises_value_error():
    candidates = [{"athlete_id": 1, "value_score": 0.5, "cost": 0}]

    with pytest.raises(ValueError):
        allocate_budget(candidates, budget=10)
