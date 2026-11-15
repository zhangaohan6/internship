# Evidence-linked analytical answers

This iteration adds an optional output contract to the existing native tool loop.
It addresses a specific failure mode: successful tool execution followed by an
incorrect number, unit, reference ID, or PDF quote in the final response.

## Flow

User question → validated source tools → session evidence ledger → model draft →
`AnswerContract.check` → answer, bounded repair, or runtime abstention.

Validation uses only the returned tool evidence. It has no access to benchmark
expected answers. A successful numeric response must identify a real evidence entry,
match its finite scalar (absolute tolerance 0.0001), and use a compatible unit.
A requested citation must match the returned document, page and an exact excerpt of
40–220 characters after whitespace normalisation. This is citation consistency,
not a medical entailment or treatment-safety check.

Errors are passed to the model as fixed error codes. At most two repair requests
are allowed, sharing the existing ten-model-step budget. Exhaustion returns a
structured abstention with status `answer_rejected`. `no_evidence` and
`budget_exhausted` also withhold numeric claims. These are application fallbacks,
not proof that the model chose to abstain. Traces record validation status and
repair counts without answers, input values or API credentials.

```python
from agent import HipFractureAgent
from answer_contract import AnswerContract

agent = HipFractureAgent('openai')
answer = agent.chat(
    'Count all synthetic dataset records and return the source evidence ID.',
    answer_contract=AnswerContract(unit='records'),
)
```

In Streamlit, enable **Require a source-linked numeric answer** for a single
statistic, prediction or comparison. **Include a guideline excerpt** adds an
original-passage citation. Conversational mode remains available for clarification
and open-ended discussion; it does not run the structured output validator.

`export_evidence=False` is an adapter for the legacy three-field statistics API:
the model still supplies an evidence ID and it is checked before the final
projection removes it. `numeric` is accepted only for mean/median statistics in
that API; default user-facing units are physical units such as `years`.

## Tool repair

Tool schemas now explain count filters versus proportion events, ASA Roman-numeral
codes and mobility codes. Invalid inputs return declared field paths and error
types, never raw Pydantic input/context or arbitrary exception messages. The model
can repair a bad call without receiving unrelated local information.

## Evaluation boundaries

The first 300-trial report remains immutable at commit
`acb3cfa991b9d5047f2bf90772a16e8ba9f749f8`. Its source fingerprint is checked against
that commit, not against this upgraded working tree. Later executions of those
inspected tasks are **regression runs**, not a new blind holdout. Failed trials
are kept. Repeated runs are not additional independent tasks.

Grounding does not establish that the selected cohort, conditional branch or
model is semantically correct. These are still checked separately by the task
scorer. A quote can occur in a source without entailing the requested conclusion.
The synthetic dataset and model artifacts do not establish clinical validity.

## References used in design

- [Pydantic AI](https://github.com/pydantic/pydantic-ai): typed outputs and validation
  as part of an agent loop. This implementation uses the existing Pydantic/native
  provider runtime; it does not add Pydantic AI as a dependency.
- [Open Deep Research](https://github.com/langchain-ai/open_deep_research): separate
  configurable research stages and versioned evaluation results. No leaderboard
  numbers or implementation code from that project are claimed as this project's.
- [LangGraph](https://github.com/langchain-ai/langgraph): explicit state and failure
  recovery. The UNSW runtime remains a small native loop; persistent graph state is
  being implemented in the separate TrustQuery LangGraph project.
