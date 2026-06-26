"""
Streamlit demo for the Hip Fracture Clinical AI Agent.
Run: streamlit run app.py
"""

import os
# Pin OpenMP before heavy imports (xgboost/torch duplicate libomp deadlocks SHAP).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import sys
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
        "API Key",
        type="password",
        placeholder="sk-ant-... or sk-...",
    )
    if api_key:
        if provider == "anthropic":
            os.environ["ANTHROPIC_API_KEY"] = api_key
        else:
            os.environ["OPENAI_API_KEY"] = api_key

    st.divider()
    st.markdown("**Dataset**")
    st.metric("Patients", "97,429")
    st.metric("Variables", "76")
    st.metric("Years", "2016 – 2024")

    st.divider()
    st.markdown("**Tools Available**")
    st.markdown("""
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
st.caption("ANZHFR dataset · ACSQHC Clinical Care Standards · XGBoost risk models")

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
                        st.session_state.agent = HipFractureAgent(provider=provider)
                    answer = st.session_state.agent.chat(user_input)
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                except Exception as e:
                    err = f"Error: {str(e)}"
                    st.error(err)
                    st.session_state.messages.append({"role": "assistant", "content": err})

# ── Tab 2: Eval Dashboard ─────────────────────────────────────────────────────
with tabs[1]:
    st.subheader("Agent Evaluation Dashboard")
    st.caption("Quantified accuracy across 3 question categories")

    results_path = os.path.join(os.path.dirname(__file__), "eval_results.json")

    col_run, col_info = st.columns([1, 3])
    with col_run:
        n_questions = st.number_input("Questions to evaluate", min_value=9, max_value=100, value=15, step=3)
        if st.button("Run Evaluation", type="primary"):
            if not api_key:
                st.error("API key required")
            else:
                with st.spinner(f"Running {n_questions} eval questions..."):
                    try:
                        from eval_framework import run_eval, save_results
                        results = run_eval(max_questions=n_questions, provider=provider)
                        save_results(results, results_path)
                        st.success(f"Evaluation complete: {n_questions} questions")
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
        m4.metric("Hallucination Rate", f"{df['hallucination_detected'].mean():.1%}")

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
                    st.metric("Hallucination", f"{sub['hallucination_detected'].mean():.1%}")

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
            display.style.applymap(_color_score, subset=["answer_score"]),
            use_container_width=True,
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
- **Source**: Australian and New Zealand Hip Fracture Registry (ANZHFR)
- **Size**: 97,429 patients, 76 variables (2016–2024)
- **Domain**: Hip fracture epidemiology, surgical outcomes, care quality

#### Agent Architecture
```
User Query
    └── Native tool-use agent (Claude / GPT-4o)
            ├── query_patient_data       → pandas over 97k rows
            ├── predict_walking_recovery → XGBoost + SHAP (120-day recovery, AUC 0.84)
            ├── predict_rehab_access     → XGBoost + SHAP (rehab discharge, AUC 0.78)
            └── search_clinical_guideline → ChromaDB RAG (ACSQHC guidelines)
```

#### ML Models
| Model | Target | Method | Test AUC |
|-------|--------|--------|---------|
| `fwalk2_model` | 120-day walking recovery | XGBoost + SHAP | 0.84 |
| `rehab_model`  | rehabilitation access | XGBoost + SHAP | 0.78 |

Features: age, sex, ASA grade, frailty scale, fracture type, cognitive status,
pre-admission mobility, surgery timing, anaesthesia type, geriatric assessment.

#### Evaluation Framework
45-question test suite across:
- **Type A** (statistics): exact-match against pandas ground truth
- **Type B** (prediction): tool-call correctness + output validity
- **Type C** (guidelines): key-fact coverage scoring

Metrics: composite answer score, tool selection accuracy, hallucination rate, latency.

#### Clinical Guidelines
RAG-indexed ACSQHC Hip Fracture Clinical Care Standards (2016 & 2023 editions).
    """)
