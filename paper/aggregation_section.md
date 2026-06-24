# Aggregation-Aware Monitoring

## 3. Method

Existing guardrails for LLM agents reason about individual messages or actions.
Input/output text filters scan each tool result for injection or policy-violating
content, and architectural defenses such as CaMeL [2] and task-alignment monitors such
as Task Shield [3] constrain how untrusted data flows into privileged actions. None of
these mechanisms maintains a session-level account of *how much* an agent has cumulatively
revealed about a given data subject. This leaves a class of attacks unaddressed: a
sequence of tool calls in which every individual step is innocuous, yet the aggregate
disclosure either crosses a sensitivity threshold or, by combining quasi-identifiers,
re-identifies an individual. This pattern is the agent-trace analogue of the inference and
aggregation problems long studied in statistical databases [4, 5, 6]. AggreGuard's
aggregation monitor closes this gap by scoring cumulative disclosure per data subject
across the agent's execution trace.

The monitor maintains a disclosure ledger keyed by the pair (session, data subject). A
disclosure is recorded only when data linkable to a subject flows to an *untrusted* sink,
that is, an action that leaves the trust boundary such as sending an email, posting
externally, or writing to an attacker-controllable channel; reads to internal sinks are
not scored. This sink gating is essential to keeping false positives low, because it
allows an agent to process a single subject in depth internally without ever accumulating
risk. Disclosures are further scoped to individual subjects, so a bulk-but-shallow
workflow that touches many subjects with one harmless field each never concentrates risk
on any one of them.

The monitor applies two complementary escalation criteria. The first is a cumulative
sensitivity budget. Each attribute *a* carries a weight *w(a)* reflecting how sensitive
it is, and the monitor tracks the running sum *S(subject) = Σ w(a)* over the distinct
facts disclosed externally about that subject; the same fact disclosed twice is counted
once. When *S* reaches a threshold *τ*, the monitor escalates. This budget formalizes the
"death by a thousand cuts" intuition in the spirit of a privacy budget [6], and by default
the budget does not decay over time, because a fact, once leaked, remains leaked—decaying
the budget would let a patient adversary defeat the mechanism simply by spacing
disclosures out. The second criterion targets re-identification directly. The monitor
maintains the set of quasi-identifiers disclosed about a subject and estimates the
subject's anonymity set against a reference population, namely the number of population
members consistent with all disclosed quasi-identifier values. Following the k-anonymity
principle [4, 5], it escalates when the anonymity set falls below *k*. Crucially, an
anonymity set of zero is treated as "the subject is not a member of the reference
population"—the least re-identifiable case rather than the most—so the monitor escalates
only when the set is small but non-empty (0 < anon < *k*).

When either criterion fires, the monitor raises a human-in-the-loop (HITL) escalation
rather than a hard block. Because re-identifiability and cumulative sensitivity are
properties of the data flow and not of the user's intent, a legitimate task may
legitimately need to disclose identifying information to an authorized party; converting
such cases into a single confirmation prompt, rather than an outright denial, keeps the
mechanism usable while preserving its protective value. The thresholds *τ* and *k*, the
attribute weights *w(a)*, and the quasi-identifier set are the monitor's tunable
parameters and define its operating point.

## 4. Evaluation

### 4.1 Setup

Because no existing agent benchmark exercises multi-step aggregation, we constructed an
aggregation-inference attack suite. Each scenario is a sequence of disclosure events,
labelled as either harmful or benign, in which every individual step is innocuous. The
harmful scenarios comprise slow sensitivity leaks (e.g., disclosing a subject's salary and
then their medical condition to an external sink) and quasi-identifier re-identifications
(disclosing a zip code, gender, and birth year whose combination is unique in the
population). The benign scenarios are deliberately chosen to stress false positives: deep
multi-field processing routed only to an internal sink, single-attribute disclosures, bulk
shipping updates spanning many subjects, and—most importantly—legitimate disclosures of
multiple quasi-identifiers about one subject whose combination does *not* re-identify them.

We compare the monitor against two baselines. The first is a stateless prompt-injection
text filter, included to show that an injection detector is simply the wrong tool for this
threat: it inspects one message at a time for override phrasing and has no notion of
cumulative PII disclosure. The second is a deliberately fair, non-novel baseline: a
stateful, egress-mounted PII field-counter that, per subject, counts the distinct
sensitive fields disclosed externally and escalates once that count reaches a threshold.
This baseline captures the obvious "just add session memory" objection to the aggregation
monitor, and it matches the monitor on raw detection; the question the evaluation answers
is whether the monitor's principled scoring yields a better detection/false-positive
trade-off than counting fields.

To measure that trade-off without a single hand-tuned operating point, we ran a parameter
sweep over a grid of thresholds (*τ*, *k*) for the monitor and over its threshold for the
field-counter, on a larger generated benchmark of 354 labelled scenarios (184 harmful, 170
benign) drawn from a 371-member synthetic population with varied cell multiplicities so
that anonymity-set sizes span the full range from unique to common. Three measures guard
against an over-favorable result. First, ground-truth harm is defined by an *independent*
privacy standard—its own weight table and thresholds, distinct from those the monitor
uses—and ambiguous scenarios are dropped to avoid label noise. Second, the monitor
estimates anonymity from an *incomplete* reference sample comprising roughly half the
population, mirroring the fact that real k-anonymity is computed against an external
reference rather than the true population, so the monitor is not an oracle on the
re-identification axis. Third, the monitor's attribute weights differ from the
ground-truth weights, so it is not an oracle on the budget axis either.

### 4.2 Results

On the core suite under the system's shipped configuration, the prompt-injection filter
detected none of the aggregation attacks, confirming that it is the wrong instrument for
this threat. The field-counter and the aggregation monitor both detected every attack, but
they differed sharply on false positives: the field-counter flagged 40% of the benign
scenarios, whereas the monitor flagged none. The two scenarios that separate them are
exactly the legitimate multi-quasi-identifier disclosures—cases in which several
identifying fields are shared for a benign reason but their combination does not
re-identify the subject. The field-counter, which only counts fields, cannot distinguish
these from an attack; the monitor, which reasons about the resulting anonymity set,
correctly allows them.

The parameter sweep generalizes this finding into a detection–false-positive trade-off
curve (Figure 1). Across the grid, the monitor's achievable frontier lies above and to the
left of the field-counter's at every operating point. At a tight false-positive budget of
2%, the monitor attains a detection rate of 0.989 against the field-counter's 0.663; the
field-counter must be loosened to roughly a 25% false-positive rate before it matches the
monitor's detection. Because an exact-zero-false-positive operating point is a brittle
knife-edge under an incomplete reference, we report detection at small false-positive
budgets rather than at exactly zero, and we verified that the advantage is stable: across
eight population-by-scenario seed combinations, the monitor's detection at a 2% budget
remains in the range 0.98–1.00 while the field-counter's stays at 0.66–0.68.

![Figure 1: Detection versus false-positive trade-off. Each point is one (τ, k) operating
point for the aggregation monitor (circles) or one threshold for the stateful PII
field-counter (squares); solid and dashed lines trace each method's achievable frontier.
The monitor's frontier dominates, achieving higher detection at every false-positive
level.](../benchmarks/results/aggregation/tradeoff_curve.png)

*Figure 1. Detection versus false-positive trade-off on the 354-scenario benchmark. The
aggregation monitor (blue) is swept over (τ, k); the stateful PII field-counter (orange) is
swept over its count threshold. The monitor's frontier dominates the field-counter's,
indicating higher detection at any fixed false-positive rate.*

The interpretation is specific and we state it precisely: the result demonstrates that the
*right feature space*—weighted cumulative sensitivity together with an anonymity-set
estimate—dominates field-counting for this trade-off, not that the monitor detects privacy
harm defined by some arbitrary external standard.

### 4.3 Limitations

Several limitations bound these claims. The attack suite is small and synthetic; it
demonstrates the mechanism and its trade-off but is not a large-scale benchmark, and the
synthetic population, while varied, does not capture the heavy-tailed cell-size
distributions of real microdata. The re-identification branch matches quasi-identifiers by
canonicalized attribute name, so an adversarial tool that relabels a field with an
unrecognized synonym can evade the anonymity-set check; this is a known weakness shared
with keyword-based defenses and motivates value-level rather than name-level matching in
future work. Finally, the ground-truth privacy standard in the sweep, although independent
of the monitor's parameters, is necessarily defined over the same two concepts the monitor
reasons about—cumulative sensitivity and anonymity—so the experiment establishes the
superiority of these features over field-counting rather than absolute detection of harm
under an unrelated definition. We regard calibrating *τ* and *k* on held-out benign
traffic, and validating against attacks that do not share the monitor's feature space, as
the central items for a full evaluation.

## References

> Note: arXiv identifiers below are the verifiable anchors; confirm full author lists and
> publication venues against the source before submission.

[1] AgentDojo: A Dynamic Environment to Evaluate Prompt Injection Attacks and Defenses for
LLM Agents. arXiv:2406.13352, 2024.

[2] Defeating Prompt Injections by Design (CaMeL). arXiv:2503.18813, 2025.

[3] Task Shield: Enforcing Task Alignment to Defend Against Indirect Prompt Injection in
LLM Agents. arXiv:2412.16682, 2024.

[4] L. Sweeney. k-Anonymity: A Model for Protecting Privacy. International Journal of
Uncertainty, Fuzziness and Knowledge-Based Systems, 10(5):557–570, 2002.

[5] P. Samarati and L. Sweeney. Protecting Privacy when Disclosing Information:
k-Anonymity and Its Enforcement through Generalization and Suppression. SRI Technical
Report, 1998.

[6] C. Dwork. Differential Privacy. In Proc. ICALP, 2006.
