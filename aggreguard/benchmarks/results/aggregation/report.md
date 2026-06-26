# Aggregation-inference suite — C4 vs fair baselines

Config: shipped `DEFAULT_CONFIG` (tau=1.0, k=2, decay off). Population: 21 synthetic members.

## Summary

| defense | attack detection rate ↑ | benign FPR ↓ |
|---|--:|--:|
| injection_filter | 0.0 | 0.0 |
| session_pii_filter | 1.0 | 0.4 |
| aggreguard_c4 | 1.0 | 0.0 |

## Per-scenario

| scenario | kind | injection_filter | session_pii_filter | C4 | C4 reason |
|---|---|:--:|:--:|:--:|---|
| budget_slow_leak | attack | · | ✓ | ✓ | step 'medical_condition': sensitivity budget S=1.10 >= tau=1.0 |
| reidentification_unique | attack | · | ✓ | ✓ | step 'gender': anonymity set 1 < k=2 (re-identifiable) |
| benign_nonreidentifying_qids | benign | · | ✓ | · | no escalation |
| benign_out_of_population_qids | benign | · | ✓ | · | no escalation |
| benign_internal_multistep | benign | · | · | · | no escalation |
| benign_single_attribute | benign | · | · | · | no escalation |
| benign_bulk_shallow | benign | · | · | · | no escalation |

**Reading it:** the injection filter is the wrong tool (detects nothing). The fair session-PII filter matches C4 on detection but false-positives on legitimate multi-quasi-identifier disclosures that do not re-identify. C4 matches detection at lower FPR by reasoning about re-identifiability (anon < k).

