import pytest

from app.ml.explain import explain_recommendation


def test_explain_taylor_gomez_no_action_does_not_name_a_biomarker():
    # Real Taylor Gomez (athlete 4) contributing_biomarkers: all z² under
    # 0.72, no_action tier. Must return the honest "nothing found"
    # sentence, not force a confident-sounding flag out of noise.
    contributing_biomarkers = [
        {"biomarker": "hb", "z_score_squared": 0.7195150687656361, "deviation_direction": "below"},
        {"biomarker": "off_score", "z_score_squared": 0.5017471629737311, "deviation_direction": "below"},
        {"biomarker": "hct", "z_score_squared": 0.419447665501568, "deviation_direction": "below"},
        {"biomarker": "ret_pct", "z_score_squared": 0.0558862433862454, "deviation_direction": "above"},
        {"biomarker": "te_ratio", "z_score_squared": 0.014569948349709634, "deviation_direction": "below"},
    ]

    result = explain_recommendation("no_action", contributing_biomarkers)

    assert result == "No significant deviation detected across monitored biomarkers."
    assert "hb" not in result and "hemoglobin" not in result
    assert "hct" not in result and "hematocrit" not in result


def test_explain_weak_top_driver_falls_back_even_if_action_type_is_not_no_action():
    # Safety net independent of action_type: a top z² of 2.0 is below
    # NO_CLEAR_DRIVER_Z2_THRESHOLD (4.0) even though this hypothetical
    # action_type is scored. Doesn't happen for any real athlete in the
    # seeded cohort (every scored-tier athlete's top z² is >= 6.36), but
    # the guard should still fire if it ever did.
    contributing_biomarkers = [
        {"biomarker": "hb", "z_score_squared": 2.0, "deviation_direction": "above"},
        {"biomarker": "hct", "z_score_squared": 1.8, "deviation_direction": "above"},
        {"biomarker": "ret_pct", "z_score_squared": 1.5, "deviation_direction": "below"},
        {"biomarker": "off_score", "z_score_squared": 1.0, "deviation_direction": "above"},
        {"biomarker": "te_ratio", "z_score_squared": 0.5, "deviation_direction": "below"},
    ]

    result = explain_recommendation("increase_monitoring", contributing_biomarkers)

    assert result == "No significant deviation detected across monitored biomarkers."


def test_explain_logan_rossi_increase_monitoring_names_two_biomarkers():
    # Real Logan Rossi (athlete 44): ret_pct (below, dominant) and
    # off_score (above, close second, ratio 0.831 to top) both clear
    # RELATIVE_CONTRIBUTION_FLOOR; hct (ratio 0.402) does not.
    contributing_biomarkers = [
        {"biomarker": "ret_pct", "z_score_squared": 6.435267857142819, "deviation_direction": "below"},
        {"biomarker": "off_score", "z_score_squared": 5.348459887193541, "deviation_direction": "above"},
        {"biomarker": "hct", "z_score_squared": 2.587586420961053, "deviation_direction": "above"},
        {"biomarker": "te_ratio", "z_score_squared": 1.0024628788964882, "deviation_direction": "below"},
        {"biomarker": "hb", "z_score_squared": 0.19388649238621725, "deviation_direction": "above"},
    ]

    result = explain_recommendation("increase_monitoring", contributing_biomarkers)

    assert result == (
        "Suppressed reticulocyte percentage and elevated OFF-score relative to "
        "this athlete's established baseline. Recommended action: increased monitoring."
    )
    # hct is the 3rd-ranked biomarker but below the relative-contribution
    # floor -- must not be named.
    assert "hematocrit" not in result


def test_explain_indigo_berg_biological_passport_review_names_three_biomarkers():
    # Real Indigo Berg (athlete 65): hb, hct, and off_score are all
    # "above" and all clear the relative-contribution floor (off_score's
    # ratio to top is 0.476, just above the 0.45 floor); ret_pct and
    # te_ratio are far too small to be considered (not even in the top 3).
    contributing_biomarkers = [
        {"biomarker": "hb", "z_score_squared": 119.71065738041449, "deviation_direction": "above"},
        {"biomarker": "hct", "z_score_squared": 110.65027693384904, "deviation_direction": "above"},
        {"biomarker": "off_score", "z_score_squared": 56.96623080606069, "deviation_direction": "above"},
        {"biomarker": "ret_pct", "z_score_squared": 2.3028218759459103, "deviation_direction": "below"},
        {"biomarker": "te_ratio", "z_score_squared": 0.42920608033172103, "deviation_direction": "above"},
    ]

    result = explain_recommendation("biological_passport_review", contributing_biomarkers)

    assert result == (
        "Elevated hemoglobin, hematocrit, and OFF-score relative to this athlete's "
        "established baseline. Recommended action: biological passport review."
    )
    assert "reticulocyte" not in result
    assert "T/E ratio" not in result


@pytest.mark.parametrize(
    "action_type,expected_phrase",
    [
        ("increase_monitoring", "Recommended action: increased monitoring."),
        ("target_test", "Recommended action: a targeted test."),
        ("biological_passport_review", "Recommended action: biological passport review."),
        ("open_case", "Recommended action: opening a case."),
    ],
)
def test_explain_action_type_display_names(action_type, expected_phrase):
    contributing_biomarkers = [
        {"biomarker": "hb", "z_score_squared": 20.0, "deviation_direction": "above"},
        {"biomarker": "hct", "z_score_squared": 1.0, "deviation_direction": "above"},
        {"biomarker": "ret_pct", "z_score_squared": 0.5, "deviation_direction": "below"},
        {"biomarker": "off_score", "z_score_squared": 0.2, "deviation_direction": "above"},
        {"biomarker": "te_ratio", "z_score_squared": 0.1, "deviation_direction": "below"},
    ]

    result = explain_recommendation(action_type, contributing_biomarkers)

    assert result.endswith(expected_phrase)
    assert result.startswith("Elevated hemoglobin relative to")
