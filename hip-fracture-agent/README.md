# Hip Fracture Research Agent

A Python tool-use Agent developed from the UNSW HDS Datathon project, with subsequent
independent engineering work. It combines aggregate queries over the **synthetic ANZHFR
Datathon dataset**, two local XGBoost prediction tools, session-bound evidence comparisons, original-PDF retrieval and a
Streamlit interface. It is a research demonstration, not a clinically validated system.

**Published evidence:** [live evaluation report](reports/2026-11-15-deepseek/README.md) · [all 300 redacted trial records](reports/2026-11-15-deepseek/trials.json) · [scoring and limitations](EVALUATION.md)

## Multi-step evaluation update 2026-11-15

The Agent assigns session-bound evidence IDs to tool results. `compare_evidence` performs
checked arithmetic using results the model has already observed, rejecting guessed IDs in
the same batch, expired references, incompatible units and zero denominators. Provider
failures roll back evidence and history together. Tool timeouts have a bounded retry allowance.

**Real API evaluation completed:** 150 self-authored reserved tasks × 2 repeats = 300 trials.
The requested model was `deepseek-chat` at `api.deepseek.com/v1`; every observed response
reported `deepseek-flash`. This is a provider alias, not an immutable model-weight snapshot.

| Result | Observed |
|---|---|
| Strict task-contract passes | 281/300 (93.7%) |
| Tasks passing both repeats | 135/150 (90.0%) |
| Statistical query trials | 184/192 |
| Multi-step, multi-turn, fault and retrieval trials | 97/108 |
| Trials with real model responses / provider errors | 300 / 0 |
| Runtime-enforced / model-reported abstentions | 16 / 5 |
| Task latency P50 / P95, local 3-worker run | 3.73s / 6.13s |

A pass requires the specified query/tool path, numeric output, JSON contract and applicable
evidence dependencies/citations. Equivalent answers produced by a different tool path may
fail this strict contract. Not every failure is a hallucination. Correct handling of an
unavailable source counts as success in fault tasks; runtime abstentions are separate from
model-authored abstentions. The benchmark does not establish clinical efficacy.

The 144-case statistics bank has 48 development and 96 reserved queries split by query
family. The 72-case workflow bank has 18 development and 54 reserved variants across 9
families; those families occur in both splits. Development runs were 17/18 before a JSON
format instruction fix, then 61/66 (including 18/18 workflows). They are not pooled with the
reserved results. The formal run used lexical PDF retrieval; hybrid RRF passed separate
local functional checks. Local regression tests: **61 passed**; tool-only cases: **144/144**.

```bash
# Configure a local .env.local (ignored) with your own existing OpenAI-compatible API config.
.venv/bin/python run_live_suite.py --provider openai --model deepseek-chat --env-file .env.local --suite all --split dev --output-dir eval_runs/dev
# Freeze code and prompts before the reserved-set run. Repeats are not new independent tasks.
.venv/bin/python run_live_suite.py --provider openai --model deepseek-chat --env-file .env.local --suite all --split holdout --repeats 2 --workers 3 --output-dir eval_runs/formal
```

`--resume` requires identical source, data, task and model configuration. It fills unfinished
trials or retries provider errors, not failed task answers. Private ignored audit directories
contain frozen source, task specifications, input-artifact hashes and all trial records.
No failed reserved task was selectively rerun or used to modify this evaluated version.
See [EVALUATION.md](EVALUATION.md) for scoring limits and failure interpretation.

## Agent engineering upgrade

- **Structured tool contracts:** Pydantic validates tool names, fields, numeric codes,
  patient feature ranges and cohort filters before execution. No generated code or raw
  patient-row query interface is exposed.
- **Correct cohort queries:** counts, means, medians, proportions and distributions use
  explicit filters. Proportions return numerator, non-missing denominator and cohort size.
  An ASA IV query no longer silently receives the overall mortality rate.
- **Bounded native tool loop:** configurable model/provider, request timeout and retries,
  per-turn step/tool budgets, successful-call deduplication and bounded conversation history.
  The full tool-result transcript is retained. Failed provider requests do not commit a
  partial turn. Invalid tool JSON is returned as a recoverable error.
- **Observable execution:** each turn reports model steps, token counts, tool status,
  durations and cache hits. Traces exclude prompts, arguments, results and API keys.
  Streamlit credentials are per-session, with no process-wide environment mutation.
- **Source-based retrieval:** only PDFs in the configured directory are searched. Results
  carry document, PDF page, SHA-256 and retrieval mode. Missing evidence produces an
  explicit error. There are no invented fallback guideline summaries or recursive scans
  of unrelated directories. Superseded PDFs require an explicit historical query.
- **Hybrid retrieval:** optional Chroma semantic search plus lexical search, fused with
  reciprocal rank fusion (RRF). Lexical mode works locally without a model download.

## Data governance

The Datathon dataset remains subject to its Data Use Agreement even though it is synthetic.
CSV files, model pickles, vector indexes, local guideline PDFs, secrets and raw evaluation dumps
are excluded from version control. Only allowlisted evaluation metadata is published under `reports/`. Existing model pickles contain sample rows; do not
publish them. Obtain the dataset through the authorised Datathon process. Original ACSQHC
PDFs must be obtained separately and placed in `guidelines/`, or selected with
`HIP_GUIDELINES_DIR`.

The 2026-11-15 local setup reuses the user's authorised dataset and model files and copies
the two already-available guideline PDFs into the ignored `guidelines/` directory. No
registry records or model artifacts are added to Git.

## Setup and run

Python **3.11** is required for the existing saved model artifacts. Direct dependency
versions in `requirements.txt` are the versions exercised in the local upgrade checks.

```bash
python3.11 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python train_model.py       # only when models need to be rebuilt
.venv/bin/streamlit run app.py
```

Choose provider, model, API base URL and API key in the sidebar. OpenAI-compatible
providers can be configured without changing source code. CLI runs read:

- `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_BASE_URL`
- `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `ANTHROPIC_BASE_URL`
- `HIP_DATA_PATH`: local CSV, default `unsw_datathon_2025.csv`
- `HIP_GUIDELINES_DIR`: explicit PDF directory, default `guidelines/`
- `HIP_RAG_MODE`: `lexical` (default) or `hybrid`
- `HIP_CHROMA_DIR`: semantic index directory, default `chroma_db/`
- `HIP_MAX_STEPS`: model turns per user message, default 10

`.env.example` documents these names; it is not loaded automatically. Do not place secrets
in source code. The first hybrid request may download the public embedding model.

## Verification

Check the published trial counts and evaluated source fingerprint without data or API access:

```bash
python3 scripts/verify_public_report.py
```


```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python eval_v2.py --mode tools --split all --output eval_results_v2_tools.json
.venv/bin/python rag_pipeline.py --query 'time to surgery'
HIP_RAG_MODE=hybrid .venv/bin/python rag_pipeline.py --query 'time to surgery'
```

Local verification on 2026-11-15:

| Check | Observed result | Scope |
|---|---|---|
| Automated tests | 61 passed | Runtime, schemas, cohort calculations, retrieval, scorer and Streamlit session isolation |
| Structured statistical cases | 144/144 passed | Tool execution against an independent pandas oracle; **no LLM calls** |
| Existing prediction artifacts | Both tools passed | Valid probability output for fictional input; no new model-quality claim |
| PDF retrieval | Lexical and hybrid passed | Original local PDFs with page/source metadata; not clinical answer validation |
| Real end-to-end benchmark | **281/300 trials passed** | 150 self-authored tasks, 2 repeats; strict task contract, not clinical accuracy |

The 144 cases comprise **12 query families × 12 cohort conditions**. They are correlated
queries, not 144 independent clinical scenarios. See [EVALUATION.md](EVALUATION.md).

## Live model evaluation

Real model calls are opt-in and require appropriate provider/data-use arrangements:

```bash
# First validate provider configuration with a small DEVELOPMENT-set run.
.venv/bin/python eval_v2.py --mode live --split dev --limit 3 --provider openai
# Freeze source/prompt/config before the reserved-set run. Repeats are not new questions.
.venv/bin/python eval_v2.py --mode live --split holdout --repeats 3 --provider openai
```

Reports separate tool selection, query-plan correctness, answer-format validity, numeric
answer correctness and end-to-end correctness. They include case-manifest, source and
input-file hashes, model/provider, run counts and family-level results. No raw answers,
patient features, tool arguments or dataset aggregates are written into v2 reports.

The reserved set is **self-authored**, not independently validated or third-party blind.
Nominal Wilson intervals assume independent cases; correlated query families limit their
interpretation. Clinical prediction quality and guideline-answer entailment require
separate labelled evaluation and expert review.

## Historical results and limitations

The former 45-question evaluation (23 statistical, 10 prediction, 12 guideline questions)
is retained in `eval_framework.py` for exploratory comparison. It included questions
without numerical ground truth, keyword-based prediction/guideline scores and a heuristic
flagger previously labelled "hallucination detection". Its old composite and flag rates
must **not** be treated as established end-to-end accuracy or a clinical hallucination rate.

The old RAG ablation used a different retrieval pipeline, potentially including manually
written fallback summaries. Its numbers do not validate the new original-PDF retriever.
No historical result files were overwritten by the upgrade.

Historical model test AUCs (~0.839 walking recovery, ~0.777 rehabilitation access) are
synthetic-data experiment results only. Mortality prediction remains unexposed because
those outcomes showed no useful learned signal. Unspecified prediction inputs are imputed
from training medians; users must not interpret them as known patient observations.

The runtime does not prove every generated sentence is supported. It rejects an answer
when all attempted tools failed; mixed-success turns still rely on model instruction and
require review. API timeout/retry settings bound provider requests, not arbitrary local
model execution. This project does not provide clinical decision automation.

## Source map

| File | Role |
|---|---|
| `agent.py` | Provider adapters, bounded execution, history, traces |
| `tool_contracts.py` | Provider-independent Pydantic schemas |
| `statistics_query.py` | Deterministic cohort aggregates |
| `agent_tools.py` | Four source tools and explicit error results |
| `evidence.py` | Session-local references and checked dependent arithmetic |
| `eval_tasks.py` | Multi-step, multi-turn and fault-injection task definitions |
| `run_live_suite.py` | Real-API runner, preflight, checkpointing and frozen-run metadata |
| `rag_pipeline.py` | PDF provenance, lexical and optional hybrid retrieval |
| `eval_v2.py` | Versioned statistical benchmark and separate metrics |
| `eval_framework.py` | Legacy exploratory bank, clearly labelled heuristics |
| `app.py` | Streamlit chat, per-session configuration and trace display |
| `tests/` | Offline regression tests, including UI integration |
| `train_model.py` | Existing local training and inference code |
