import math

import pytest

from app.ml.anomaly import mahalanobis_distance


def test_mahalanobis_distance_hand_computable_case():
    # Per-biomarker (mean, var) posterior and a sample chosen so each term
    # (observed - mean)^2 / var comes out to a round number:
    #   hb:        (15.0 - 14.0)^2 / 0.25 = 1.00 / 0.25 =  4
    #   hct:       (44.0 - 42.0)^2 / 4.00 = 4.00 / 4.00 =  1
    #   ret_pct:   (1.2  - 1.0 )^2 / 0.01 = 0.04 / 0.01 =  4
    #   off_score: (88.0 - 80.0)^2 / 16.0 = 64.0 / 16.0 =  4
    #   te_ratio:  (1.6  - 1.3 )^2 / 0.09 = 0.09 / 0.09 =  1
    # sum = 14 -> distance = sqrt(14)
    posterior = {
        "hb": (14.0, 0.25),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {
        "hb": 15.0,
        "hct": 44.0,
        "ret_pct": 1.2,
        "off_score": 88.0,
        "te_ratio": 1.6,
    }

    distance = mahalanobis_distance(posterior, sample)

    assert distance == pytest.approx(math.sqrt(14))


def test_mahalanobis_distance_zero_when_sample_matches_mean():
    posterior = {
        "hb": (14.0, 0.25),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {biomarker: mean for biomarker, (mean, _var) in posterior.items()}

    assert mahalanobis_distance(posterior, sample) == pytest.approx(0.0)


def test_mahalanobis_distance_raises_on_nonpositive_variance():
    posterior = {
        "hb": (14.0, 0.0),
        "hct": (42.0, 4.0),
        "ret_pct": (1.0, 0.01),
        "off_score": (80.0, 16.0),
        "te_ratio": (1.3, 0.09),
    }
    sample = {
        "hb": 14.0,
        "hct": 42.0,
        "ret_pct": 1.0,
        "off_score": 80.0,
        "te_ratio": 1.3,
    }

    with pytest.raises(ValueError):
        mahalanobis_distance(posterior, sample)
