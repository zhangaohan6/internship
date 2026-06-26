# Hip Fracture Clinical AI Agent — UNSW HDS Datathon 2025

A clinical decision-support agent over the **Australian & New Zealand Hip Fracture
Registry (ANZHFR)** dataset (97,429 patients). It combines **XGBoost outcome-prediction
models**, a **RAG retriever** over the ACSQHC Hip Fracture Clinical Care Standards, and a
**tool-using LLM agent**, with a **Streamlit** UI and a **reproducible evaluation harness**.

## Data availability & governance

The ANZHFR registry data used here is provided under the **UNSW HDS Datathon Data Use
Agreement** and **is not redistributed in this repository**. The committed code is shared;
**no patient-level data, data dictionary, or trained model artifacts are included** —
the saved model pickles embed held-out patient sample rows, so they are excluded too
(see `.gitignore`). To run the project you must obtain the dataset through the datathon
organisers and place `unsw_datathon_2025.csv` in this directory, then train the models
locally with `python train_model.py`. The ACSQHC Clinical Care Standards used for RAG are
publicly available documents.

## What it does

The agent answers three kinds of clinical question, each routed to a dedicated tool:

| Tool | Purpose | Backing |
|---|---|---|
| `query_patient_data` | population statistics (rates, proportions, comparisons) | pandas over the registry |
| `predict_walking_recovery` | P(recover walking by 120 days) for one patient | XGBoost, **AUC 0.84** |
| `predict_rehab_access` | P(discharge to a rehabilitation unit) | XGBoost, **AUC 0.78** |
| `search_clinical_guideline` | evidence-based care standards | RAG (Chroma + sentence-transformers) |

The agent uses **native tool-use** (Anthropic Claude or OpenAI) — no LangChain agent loop —
and is explicitly prompted to cite sources, state model limitations, and defer to clinicians.

## Models (measured AUCs)

Trained on pre-admission features only (time-zero = admission) to avoid leakage; median
imputation; class-weighting; Youden-J operating point; SHAP explanations saved per model.

| Model | Outcome | Test AUC |
|---|---|--:|
| `fwalk2_model` | walking recovery at 120 days | **0.839** |
| `rehab_model` | rehabilitation access at discharge | **0.777** |
| `mort30d_model` / `mort365d_model` | 30-/365-day mortality | **~0.52 / ~0.50** |

> **Honest note on mortality.** The mortality outcomes carry **no learnable signal in this
> (synthetic) dataset** — AUC ≈ chance. The agent therefore exposes **no mortality-prediction
> tool**; only the two outcomes with preserved real-world relationships (walking recovery,
> rehab access) are offered. The mortality `.pkl`s are kept only for reference.

## Layout

```
train_model.py        # train fwalk2 + rehab XGBoost models (+ SHAP), save to models/
data_perprocessing.py # data prep
agent.py              # HipFractureAgent: native tool-use loop (Anthropic/OpenAI)
agent_tools.py        # the 4 tools
rag_pipeline.py       # build/query the Chroma vector store over care standards
eval_framework.py     # Type A/B/C evaluation harness with pandas ground truth
app.py                # Streamlit UI
models/               # saved model artifacts (.pkl)
chroma_db/            # persisted vector store
unsw_datathon_2025.csv            # registry data (97,429 × 76)
unsw_datathon_2025_data_dict.csv  # data dictionary
```

## Setup

**Requires Python 3.11** — the saved model pickles (which embed SHAP explainers) were
created under 3.11 and will not unpickle under 3.9/3.10. `pyarrow` is required to load them.

```bash
python3.11 -m venv .venv && source .venv/bin/activate    # or: uv venv .venv --python 3.11
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...        # or OPENAI_API_KEY
```

## Run

```bash
python train_model.py            # (re)train models — offline, no API
streamlit run app.py             # the UI
python eval_framework.py --n 15  # evaluation (needs an API key; --full for 100 Q)
```

## Evaluation harness

`eval_framework.py` scores the agent on three question types, each with its own
verification:

- **Type A — statistical:** answer checked against pandas ground truth (tolerance-based).
- **Type B — prediction:** correct tool called + risk level / probability / factors present.
- **Type C — guideline:** key-fact coverage + correct tool called.

It reports tool-selection accuracy, a composite answer score, hallucination rate, and
latency. Tool calls are captured by wrapping `agent._call_tool`.

## Known limitations / TODO

- The dataset is synthetic; mortality outcomes were randomly assigned (hence AUC ≈ 0.5).
- `build_test_dataset` currently yields 45 questions (23 A / 10 B / 12 C), not the 100 the
  docstring mentions; expand the bank for a fuller eval.
- Type B is now aligned to the agent's two real prediction tools (5 walking-recovery +
  5 rehab-access); end-to-end Type-B numbers still need an API run to populate.
