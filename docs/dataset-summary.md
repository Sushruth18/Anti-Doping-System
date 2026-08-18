# Dataset Summary

## Frozen dataset stats — v1.2 (Day 4)

| Metric | Value |
|---|---|
| **Total athletes** | 80 |
| **Total samples** | 400 (5 per athlete × 80 athletes) |
| **Sports** | Cycling: 16, Rowing: 16, Running: 16, Swimming: 16, Triathlon: 16 |
| **Synthetic anomalies** | 15 / 80 athletes (18.8%) |
| **Anomaly archetypes** | transfusion: 5 (6.2%), EPO micro-dosing: 5 (6.2%), steroid micro-dosing: 5 (6.2%) |
| **Frozen data files** | `data/athletes.json`, `data/samples.json` |

## Known limitations

### Anomaly scoring independence assumption

The Mahalanobis distance in `backend/app/ml/anomaly.py` sums squared
z-scores across biomarkers assuming they're independent. In practice
`hb`, `hct`, and `off_score` are correlated (`off_score` is
mathematically derived from `hb` and `ret_pct`), so a single underlying
physiological shift can inflate the raw distance by being counted 2-3
times across correlated biomarkers.

This is a known limitation, not fixed for the hackathon MVP — a full
covariance-matrix-based Mahalanobis distance is the correct future fix.
Current `ANOMALY_SCORE_SCALE=10.0` was calibrated against distances
that include this inflation, so any future covariance fix should be
re-paired with a scale recalibration.
