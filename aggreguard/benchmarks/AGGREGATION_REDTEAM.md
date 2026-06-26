# Aggregation moat (C4) — red-team and what changed

The first version of the C4 demo claimed "C4 catches aggregation attacks that I/O filters
miss, at 0% FPR" with a 0.00-vs-1.00 table. A 4-critic adversarial red-team (each running
the live code to build counterexamples) found that headline **overstated on every
quantitative leg**, while the underlying concept was sound. Findings and fixes:

## What was wrong

1. **Strawman baseline (high).** The "io_filter" was the prompt-injection keyword detector
   — it has *zero* PII capability (scores 0.00 even on a single-message full PII dump), yet
   was labelled a stand-in for Lakera / LLM Guard. The 0.00 detection was a category error.
   A ~15-line stateful PII field-counter ties C4 on the old suite.
2. **0% FPR was an artifact (high).** Only 3 benign probes, each hand-built to dodge both
   branches. Realistic benign external disclosures (recruiter EEO fields; HR payroll
   onboarding) escalated identically to attacks. The old population had 10 all-unique
   cells, so *any* 3-QID disclosure re-identified — a benign multi-QID pass was impossible
   by construction.
3. **anon == 0 logic bug (high).** Out-of-population QID values gave anon=0, and `anon < k`
   escalated — but anon=0 means "subject not in the reference population", the *least*
   re-identifiable case. Any real-world value absent from the toy population false-positived.
4. **Eval-only config (high).** The flagship budget attack was *missed* under the shipped
   `DEFAULT_CONFIG` (salary/medical weights existed only in a bespoke eval config).
5. **Budget vs decay / double-count (medium).** Time-decay let a patient attacker defeat a
   "slow leak" by spacing it out; identical repeated facts were double-counted.
6. **Attribute-name string match (medium).** Re-identification keyed on exact attr names, so
   `postal_code`/`sex`/`yob` synonyms fully evaded it — the same brittleness C4 claimed to beat.

## What changed

- `config.py`: one realistic **shipped** config drives both monitor and eval (no eval-only
  tuning); decay off by default (a leaked fact stays leaked); QID/weight vocabulary
  reconciled; attribute aliases added.
- `aggregation.py`: escalate only when `0 < anon < k` (anon==0 fix); dedup the budget by
  `(attr, value)`; canonicalize attribute synonyms; skip None-valued QIDs; decay gated by a
  config flag. Prose softened from "structurally cannot see" to the accurate claim.
- `eval/baselines.py`: a **fair** session-aware PII field-counter added as a real comparator.
- `aggregation_suite.py`: 21-member population with **varied** cell sizes; discriminating
  benign scenarios (non-re-identifying multi-QID; out-of-population) that exercise C4's edge.

## Honest result

| defense | attack detection | benign FPR |
|---|--:|--:|
| injection_filter | 0.00 | 0.00 |
| session_pii_filter (fair) | 1.00 | 0.40 |
| aggreguard_c4 | 1.00 | **0.00** |

C4 **matches** a fair stateful baseline on detection but at **lower false positives**,
because it reasons about re-identifiability (k-anonymity) instead of counting fields. This
is a mechanism demonstration on a small hand-built suite — not a large-scale benchmark, and
the synonym/name-matching and population-realism limitations remain documented open items.
