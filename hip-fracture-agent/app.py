"""
Streamlit demo for the Hip Fracture Clinical AI Agent.
Run: streamlit run app.py
"""

import os
# Pin OpenMP before heavy imports (xgboost/torch duplicate libomp deadlocks SHAP).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import sys
import hashlib
from agent import AgentConfig
from answer_contract import AnswerContract
import json
import streamlit as st
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="Hip Fracture Clinical AI Agent",
    page_icon="🦴",
    layout="wide",
)

# ── Sidebar: API key + provider ──────────────────────────────────────────────
with st.sidebar:
    st.title("Configuration")
    provider = st.selectbox("LLM Provider", ["anthropic", "openai"])
    api_key = st.text_input(
        "API Key", type="password", key=f"api_{provider}",
        value=os.environ.get("ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY", ""),
    )
    model = st.text_input("Model", key=f"model_{provider}", value=os.environ.get(
        "ANTHROPIC_MODEL" if provider == "anthropic" else "OPENAI_MODEL",
        "claude-sonnet-4-6" if provider == "anthropic" else "gpt-4o"))
    base_url = st.text_input("API base URL (optional)", key=f"base_{provider}", value=os.environ.get(
        "ANTHROPIC_BASE_URL" if provider == "anthropic" else "OPENAI_BASE_URL", ""))
    agent_config = AgentConfig(provider=provider, model=model or None, base_url=base_url or None)
    verified_numeric = st.checkbox('Require a source-linked numeric answer', value=False)
    include_citation = st.checkbox('Include a guideline excerpt', value=False, disabled=not verified_numeric)
    if verified_numeric:
        st.caption('For a single statistic, prediction or comparison. Unsupported answers are withheld.')
    identity = (provider, model, base_url, hashlib.sha256(api_key.encode()).hexdigest())
    if st.session_state.get("agent_identity") != identity:
        st.session_state.agent_identity = identity
        st.session_state.agent = None
        st.session_state.messages = []
    # Credentials stay inside this Streamlit session; never change process-wide env.

    st.divider()
    st.markdown("**Synthetic Datathon dataset**")
    st.metric("Patients", "97,429")
    st.metric("Variables", "76")
    st.metric("Years", "2016 – 2024")

    st.divider()
    st.markdown("**Tools Available**")
    st.markdown("""
- `compare_evidence` — dependent comparisons from source results
- `query_patient_data` — population stats
- `predict_walking_recovery` — 120-day walking (AUC 0.84)
- `predict_rehab_access` — rehab discharge (AUC 0.78)
- `search_clinical_guideline` — ACSQHC standards
    """)

    if st.button("Clear conversation"):
        st.session_state.messages = []
        st.session_state.agent = None
        st.rerun()

# ── Page header ───────────────────────────────────────────────────────────────
st.title("Hip Fracture Clinical AI Agent")
st.caption("Synthetic Datathon data · Original-PDF citations · Research demonstration")
st.info("Research demonstration only. The synthetic-data models are not clinically validated.")

tabs = st.tabs(["Chat", "Eval Dashboard", "About"])

# ── Tab 1: Chat ───────────────────────────────────────────────────────────────
with tabs[0]:
    # Example prompts
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("30-day mortality rate?"):
            st.session_state.next_input = "What is the overall 30-day mortality rate in the ANZHFR dataset?"
    with col2:
        if st.button("Predict walking recovery"):
            st.session_state.next_input = (
                "Predict the 120-day walking recovery for an 87-year-old female, "
                "ASA IV, frailty score 8, who uses a wheelchair."
            )
    with col3:
        if st.button("Surgery timing guideline"):
            st.session_state.next_input = "What is the recommended time to surgery standard?"

    st.divider()

    # Conversation history
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "agent" not in st.session_state:
        st.session_state.agent = None

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
            if msg.get("trace"):
                with st.expander("Tool execution trace"):
                    st.json(msg["run"])
                    st.dataframe(pd.DataFrame(msg["trace"]), hide_index=True)

    # Input
    prefill = st.session_state.pop("next_input", "")
    user_input = st.chat_input("Ask about hip fracture patients, risk prediction, or clinical guidelines...") or prefill

    if user_input:
        if not api_key:
            st.error("Please enter an API key in the sidebar.")
            st.stop()

        st.session_state.messages.append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    if st.session_state.agent is None:
                        from agent import HipFractureAgent
                        st.session_state.agent = HipFractureAgent(config=agent_config, api_key=api_key)
                    contract = AnswerContract(require_citation=include_citation) if verified_numeric else None
                    answer = st.session_state.agent.chat(user_input, answer_contract=contract)
                    st.markdown(answer)
                    trace = list(st.session_state.agent.trace)
                    run = dict(st.session_state.agent.last_run)
                    st.session_state.messages.append({"role": "assistant", "content": answer, "trace": trace, "run": run})
                    with st.expander("Tool execution trace", expanded=True):
                        st.json(run)
                        st.dataframe(pd.DataFrame(trace), hide_index=True)
                except Exception as e:
                    err = f"Error: {str(e)}"
                    st.error(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})

# ── Tab 2: Eval Dashboard ─────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Legacy exploratory evaluation")
    st.warning("These v1 scores are heuristic diagnostics. They do not establish general answer accuracy or a clinical hallucination rate. Use eval_v2.py for separately scored statistical queries.")
    st.caption("Heuristic scores across 3 question categories; historical results are not revalidation of this version.")

    results_path = os.path.join(os.path.dirname(__file__), "eval_results.json")

    col_run, col_info = st.columns([1, 3])
    with col_run:
        n_questions = st.number_input("Questions to evaluate", min_value=9, max_value=45, value=15, step=3)
        if st.button("Run Evaluation", type="primary"):
            if not api_key:
                st.error("API key required")
            else:
                with st.spinner(f"Running {n_questions} eval questions..."):
                    try:
                        from eval_framework import run_eval, save_results
                        results = run_eval(max_questions=n_questions, provider=provider, agent_config=agent_config, api_key=api_key)
                        save_results(results, results_path)
                        st.success(f"Evaluation complete: {len(results)} questions")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

    with col_info:
        st.info("Evaluation runs automatically scored questions across Type A (stats), Type B (prediction), and Type C (guidelines).")

    if os.path.exists(results_path):
        with open(results_path) as f:
            data = json.load(f)
        df = pd.DataFrame(data)

        # Summary metrics
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Questions Run", len(df))
        m2.metric("Composite Score", f"{df['answer_score'].mean():.2f} / 1.0")
        m3.metric("Tool Accuracy", f"{df['tool_correct'].mean():.0%}")
        m4.metric("Heuristic flag rate", f"{df['hallucination_detected'].mean():.1%}")

        st.divider()

        # Per-type breakdown
        col_a, col_b, col_c = st.columns(3)
        for col, t, label in [
            (col_a, "A", "Type A — Statistics"),
            (col_b, "B", "Type B — Prediction"),
            (col_c, "C", "Type C — Guidelines"),
        ]:
            sub = df[df["type"] == t]
            if len(sub):
                with col:
                    st.markdown(f"**{label}** (n={len(sub)})")
                    st.metric("Avg Score", f"{sub['answer_score'].mean():.2f}")
                    st.metric("Tool Correct", f"{sub['tool_correct'].mean():.0%}")
                    st.metric("Heuristic flags", f"{sub['hallucination_detected'].mean():.1%}")

        st.divider()

        # Detailed results table
        st.markdown("**Detailed Results**")
        display = df[["id", "type", "question", "tool_called", "tool_correct",
                       "answer_score", "hallucination_detected", "latency_seconds"]].copy()
        display["question"] = display["question"].str[:70] + "..."
        display["answer_score"] = display["answer_score"].round(2)

        def _color_score(val):
            if isinstance(val, float):
                color = "#2ecc71" if val >= 0.7 else "#f39c12" if val >= 0.4 else "#e74c3c"
                return f"background-color: {color}22"
            return ""

        st.dataframe(
            display.style.map(_color_score, subset=["answer_score"]),
            width='stretch',
            height=400,
        )

        # Failure analysis
        failures = df[(df["answer_score"] < 0.4) | (df["hallucination_detected"])]
        if len(failures):
            with st.expander(f"Failed cases ({len(failures)}) — click to expand"):
                for _, row in failures.iterrows():
                    st.markdown(f"**[{row['id']}]** {row['question'][:100]}")
                    st.markdown(f"Score: `{row['answer_score']}` | Tool: `{row['tool_called']}` | Hallucination: `{row['hallucination_detected']}`")
                    if row.get("error"):
                        st.code(row["error"])
                    st.divider()
    else:
        st.info("No eval results yet. Run an evaluation above.")

# ── Tab 3: About ──────────────────────────────────────────────────────────────
with tabs[2]:
    st.subheader("Project Architecture")
    st.markdown("""
### Hip Fracture Clinical AI Agent

Built for the **UNSW Health Data Science Datathon 2025** (Task 4: Predictive Models).

#### Data
- **Source**: Synthetic ANZHFR Datathon dataset (restricted local files)
- **Size**: 97,429 patients, 76 variables (2016–2024)
- **Domain**: Hip fracture epidemiology, surgical outcomes, care quality

#### Agent Architecture
```
User Query
    └── Bounded native tool-use runtime (configurable provider/model)
            ├── query_patient_data       → validated cohort filters + aggregate calculations
            ├── predict_walking_recovery → XGBoost + SHAP (120-day recovery, AUC 0.84)
            ├── predict_rehab_access     → XGBoost + SHAP (rehab discharge, AUC 0.78)
            └── search_clinical_guideline → original PDF + page citations + optional hybrid retrieval
```

#### ML Models
| Model | Target | Method | Test AUC |
|-------|--------|--------|---------|
| `fwalk2_model` | 120-day walking recovery | XGBoost + SHAP | 0.84 |
| `rehab_model`  | rehabilitation access | XGBoost + SHAP | 0.78 |

Prediction inputs are validated. Unspecified model features use training-time median imputation.
Historical AUCs above describe the synthetic-data experiment, not clinical validation.

#### Evaluation Framework
45-question test suite across:
- **Type A** (statistics): exact-match against pandas ground truth
- **Type B** (prediction): tool-call correctness + output validity
- **Type C** (guidelines): key-fact coverage scoring

Metrics: composite answer score, tool selection accuracy, hallucination rate, latency.

#### Clinical Guidelines
Only PDFs in the configured guideline directory are searched. Superseded documents are excluded unless explicitly requested.
Each retrieved passage includes document name, page, source hash and retrieval mode.
Missing sources produce an explicit evidence-unavailable response.
    """)
