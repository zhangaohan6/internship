# Aggregation monitor — detection vs FPR tradeoff sweep

Population: 371 synthetic members. Scenarios: 354 labelled (184 harmful, 170 benign); ground truth = an independent privacy standard (separate weights/thresholds).

Max detection (TPR) achievable at an FPR *budget* (a tight budget is the honest comparison; an exact-0%-FPR bin is a brittle knife-edge under an incomplete reference, so it is not used as the headline):

| FPR budget | C4 max detection | session_pii max detection |
|---|--:|--:|
| ≤ 0.02 | 0.989 | 0.663 |
| ≤ 0.05 | 0.989 | 0.663 |
| ≤ 0.10 | 0.995 | 0.913 |
| ≤ 0.20 | 0.995 | 0.913 |

C4 frontier points (fpr, tpr): [(0.0, 0.065), (0.0, 0.364), (0.0, 0.745), (0.0, 0.94), (0.0, 0.989), (0.088, 0.995), (0.229, 1.0)]

session_pii frontier points (fpr, tpr): [(0.0, 0.418), (0.0, 0.663), (0.076, 0.913), (0.259, 1.0)]

**Reading it:** C4 sweeps (tau, k); the field-counter sweeps its threshold. C4's frontier sits up-and-left of the field-counter's — higher detection at the same FPR — because anonymity-set reasoning separates re-identifying quasi-identifier combinations from harmless ones, whereas a field-count cannot. FAIRNESS NOTES: (1) C4 estimates anonymity from an INCOMPLETE reference sample (~50% of the population), not the ground-truth population, so it is not an oracle on the re-identification axis. (2) The budget axis uses an independent ground-truth weight table, so C4 is not an oracle there either. (3) Ground-truth harm is still defined over the same two concepts C4 reasons about (cumulative sensitivity, anonymity), so this shows the RIGHT FEATURE SPACE beats field-counting — not that C4 detects privacy harm defined by some other standard.

**Seed robustness:** verified across 8 population×scenario seed combinations — at ≤2% FPR, C4 detection stays 0.98–1.00 vs the field-counter's 0.66–0.68. The gap is the robust headline; absolute numbers shift a little by seed.

