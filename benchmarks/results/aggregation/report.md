# Aggregation-inference suite — C4 vs I/O filter

## Summary

| defense | attack detection rate ↑ | benign FPR ↓ |
|---|--:|--:|
| io_filter | 0.0 | 0.0 |
| aggreguard_c4 | 1.0 | 0.0 |

## Per-scenario

| scenario | kind | io_filter flags | C4 flags | C4 reason |
|---|---|:--:|:--:|---|
| budget_slow_leak | attack | · | ✓ | step 'medical_condition': sensitivity budget S=1.10 >= tau=1.0 |
| reidentification_qids | attack | · | ✓ | step 'birth_year': anonymity set 1 < k=2 (re-identifiable) |
| benign_internal_multistep | benign | · | · | no escalation |
| benign_single_attribute | benign | · | · | no escalation |
| benign_bulk_shallow | benign | · | · | no escalation |

