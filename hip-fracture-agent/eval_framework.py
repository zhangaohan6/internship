"""
Evaluation Framework for the Hip Fracture Clinical AI Agent.

Evaluates 3 question types with different verification methods:
  Type A - Statistical queries   → exact/near-exact match against pandas ground truth
  Type B - Prediction queries    → tool call correctness + value consistency
  Type C - Guideline queries     → LLM-as-judge scoring (0-3 scale)

Run:  python eval_framework.py
Output: eval_results.json + printed summary table
"""

import os
# OpenMP: pin to a single runtime/thread BEFORE any heavy import (numpy/xgboost/torch).
# torch (via chromadb/sentence-transformers) and xgboost each bundle a libomp; the
# duplicate runtime otherwise deadlocks SHAP when a prediction runs after a RAG call.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

import json
import time
import re
import numpy as np
import pandas as pd
from dataclasses import dataclass, asdict
from typing import Literal

DATA_PATH = os.path.join(os.path.dirname(__file__), "unsw_datathon_2025.csv")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "eval_results.json")

# ─────────────────────────────────────────────────────────────────────────────
# Ground truth computation (run once, used to verify Type A answers)
# ─────────────────────────────────────────────────────────────────────────────

def compute_ground_truth() -> dict:
    df = pd.read_csv(DATA_PATH, low_memory=False)

    mort30 = pd.to_numeric(df["mort30d"], errors="coerce")
    mort365 = pd.to_numeric(df["mort365d"], errors="coerce")
    age = pd.to_numeric(df["age"], errors="coerce")
    sex = pd.to_numeric(df["sex"], errors="coerce")
    delay = pd.to_numeric(df["delay"], errors="coerce")
    asa = pd.to_numeric(df["asa"], errors="coerce")
    fwalk = pd.to_numeric(df["fwalk2"], errors="coerce")
    gerimed = pd.to_numeric(df["gerimed"], errors="coerce")

    return {
        "30d_mortality_rate": (mort30 == 2).sum() / mort30.notna().sum(),
        "365d_mortality_rate": (mort365 == 2).sum() / mort365.notna().sum(),
        "median_age": float(age.median()),
        "pct_female": (sex == 2).sum() / sex.notna().sum(),
        "pct_no_surgery_delay": (delay == 1).sum() / delay.notna().sum(),
        "pct_asa_3plus": (asa >= 3).sum() / asa.notna().sum(),
        "pct_walking_recovered": (fwalk == 1).sum() / fwalk.notna().sum(),
        "pct_geriatric_assessed": (gerimed == 1).sum() / gerimed.notna().sum(),
        "total_patients": len(df),
        # ASA IV 30d mortality
        "asa4_30d_mortality": (
            (mort30[asa == 4] == 2).sum() / mort30[asa == 4].notna().sum()
        ),
        "pct_80_plus": (age >= 80).sum() / age.notna().sum(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Test dataset (100 questions across 3 types)
# ─────────────────────────────────────────────────────────────────────────────

def build_test_dataset(gt: dict) -> list[dict]:
    """Return the 100-question eval set with ground truth annotations."""

    type_a = [
        # --- Mortality ---
        {
            "id": "A001", "type": "A",
            "question": "What is the overall 30-day mortality rate in the dataset?",
            "expected_value": gt["30d_mortality_rate"],
            "tolerance": 0.005,
            "expected_tool": "query_patient_data",
            "tags": ["mortality", "statistics"],
        },
        {
            "id": "A002", "type": "A",
            "question": "What percentage of patients died within 365 days?",
            "expected_value": gt["365d_mortality_rate"],
            "tolerance": 0.005,
            "expected_tool": "query_patient_data",
            "tags": ["mortality", "statistics"],
        },
        {
            "id": "A003", "type": "A",
            "question": "What is the 30-day mortality rate for ASA grade IV patients?",
            "expected_value": gt["asa4_30d_mortality"],
            "tolerance": 0.01,
            "expected_tool": "query_patient_data",
            "tags": ["mortality", "asa"],
        },
        # --- Demographics ---
        {
            "id": "A004", "type": "A",
            "question": "What is the median age of hip fracture patients in the registry?",
            "expected_value": gt["median_age"],
            "tolerance": 1.0,
            "expected_tool": "query_patient_data",
            "tags": ["demographics", "age"],
        },
        {
            "id": "A005", "type": "A",
            "question": "What percentage of patients are female?",
            "expected_value": gt["pct_female"],
            "tolerance": 0.005,
            "expected_tool": "query_patient_data",
            "tags": ["demographics", "sex"],
        },
        {
            "id": "A006", "type": "A",
            "question": "What proportion of patients are aged 80 or older?",
            "expected_value": gt["pct_80_plus"],
            "tolerance": 0.005,
            "expected_tool": "query_patient_data",
            "tags": ["demographics", "age"],
        },
        {
            "id": "A007", "type": "A",
            "question": "How many total patients are in the ANZHFR dataset?",
            "expected_value": float(gt["total_patients"]),
            "tolerance": 100,
            "expected_tool": "query_patient_data",
            "tags": ["statistics"],
        },
        # --- Surgery timing ---
        {
            "id": "A008", "type": "A",
            "question": "What proportion of patients had no surgery delay (surgery within 48 hours)?",
            "expected_value": gt["pct_no_surgery_delay"],
            "tolerance": 0.01,
            "expected_tool": "query_patient_data",
            "tags": ["surgery", "timing"],
        },
        # --- Clinical quality ---
        {
            "id": "A009", "type": "A",
            "question": "What percentage of patients were assessed by geriatric medicine?",
            "expected_value": gt["pct_geriatric_assessed"],
            "tolerance": 0.01,
            "expected_tool": "query_patient_data",
            "tags": ["quality", "geriatrics"],
        },
        {
            "id": "A010", "type": "A",
            "question": "What proportion of patients had ASA grade 3 or higher?",
            "expected_value": gt["pct_asa_3plus"],
            "tolerance": 0.01,
            "expected_tool": "query_patient_data",
            "tags": ["clinical", "asa"],
        },
        # --- Recovery ---
        {
            "id": "A011", "type": "A",
            "question": "What percentage of patients recovered their walking ability by 120 days?",
            "expected_value": gt["pct_walking_recovered"],
            "tolerance": 0.01,
            "expected_tool": "query_patient_data",
            "tags": ["recovery", "mobility"],
        },
    ]

    # Add more Type A questions with derived expectations
    extra_a = [
        {"id": f"A{i:03d}", "type": "A", "question": q, "expected_tool": "query_patient_data",
         "expected_value": None, "tolerance": None, "tags": ["statistics"]}
        for i, q in enumerate([
            "What is the average age of patients who died within 30 days?",
            "What percentage of patients came from residential aged care facilities?",
            "How many patients had surgery delayed due to theatre availability?",
            "What proportion of patients had impaired cognition on admission?",
            "What is the most common fracture type in the dataset?",
            "What percentage of patients were admitted via the emergency department?",
            "How many patients had nerve blocks administered before the operating theatre?",
            "What proportion of patients were discharged to a rehabilitation unit?",
            "What percentage of patients received bone protection medication at discharge?",
            "What is the frailty score distribution across the dataset?",
            "How many patients had a new skin pressure injury during admission?",
            "What proportion of patients mobilised on the first day after surgery?",
        ], start=12)
    ]
    type_a.extend(extra_a)

    # Type B — single-patient predictions. The agent exposes two real prediction tools
    # (walking recovery, AUC 0.84; rehab access, AUC 0.78) and NO mortality tool, so these
    # questions target only the outcomes the agent can actually predict.
    type_b = [
        {
            "id": "B001", "type": "B",
            "question": (
                "Predict the 120-day walking recovery for an 85-year-old female patient "
                "with ASA grade IV, frailty score 7, who uses a walking frame."
            ),
            "expected_tool": "predict_walking_recovery",
            "expected_features": {"age": 85, "sex": 2, "asa": 4, "frailty": 7, "walk": 3},
            "check": "tool_called",
            "tags": ["prediction", "recovery"],
        },
        {
            "id": "B002", "type": "B",
            "question": (
                "Will a 70-year-old male with ASA II and frailty score 3 who walks "
                "without aids recover his walking ability by 120 days?"
            ),
            "expected_tool": "predict_walking_recovery",
            "expected_features": {"age": 70, "sex": 1, "asa": 2, "frailty": 3, "walk": 1},
            "check": "tool_called",
            "tags": ["prediction", "recovery"],
        },
        {
            "id": "B003", "type": "B",
            "question": (
                "Will an 80-year-old woman with a pertrochanteric fracture, ASA III, "
                "who uses a walking stick, recover her walking ability by 120 days?"
            ),
            "expected_tool": "predict_walking_recovery",
            "expected_features": {"age": 80, "sex": 2, "ftype": 3, "asa": 3, "walk": 2},
            "check": "tool_called",
            "tags": ["prediction", "recovery"],
        },
        {
            "id": "B004", "type": "B",
            "question": (
                "Compare the walking-recovery outlook of a 92-year-old with severe frailty "
                "(score 8), ASA V, bed-bound before the fracture, against a 70-year-old "
                "ASA II patient who walked unaided."
            ),
            "expected_tool": "predict_walking_recovery",
            "check": "tool_called",
            "tags": ["prediction", "recovery", "comparison"],
        },
        {
            "id": "B005", "type": "B",
            "question": (
                "Compare the recovery outlook between a 75-year-old ASA II patient "
                "who walks without aids versus an 88-year-old ASA IV patient in a wheelchair."
            ),
            "expected_tool": "predict_walking_recovery",
            "check": "tool_called",
            "tags": ["prediction", "recovery", "comparison"],
        },
    ]

    # Rehab-access predictions exercise the second real prediction tool.
    extra_b = [
        {"id": f"B{i:03d}", "type": "B", "question": q,
         "expected_tool": "predict_rehab_access", "check": "tool_called",
         "tags": ["prediction", "rehab"]}
        for i, q in enumerate([
            "Will a 78-year-old with cognitive impairment, admitted from residential aged care, be discharged to a rehabilitation unit?",
            "Predict rehabilitation discharge for a 65-year-old, ASA I, frailty 2, living at home with private insurance.",
            "What is the probability of rehabilitation access for an 83-year-old female, frailty 6, admitted via the emergency department as a public patient?",
            "Predict rehabilitation access for an 88-year-old admitted from a residential aged care facility with ASA IV.",
            "What is the rehab-discharge probability for a 76-year-old male with normal cognition, ASA III, living at home?",
        ], start=6)
    ]
    type_b.extend(extra_b)

    type_c = [
        {
            "id": "C001", "type": "C",
            "question": "What is the recommended time to surgery standard for hip fracture patients?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["48 hours", "ACSQHC", "timely"],
            "tags": ["guideline", "surgery"],
        },
        {
            "id": "C002", "type": "C",
            "question": "What are the pain management guidelines for hip fracture patients in the emergency department?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["30 minutes", "pain assessment", "nerve block"],
            "tags": ["guideline", "pain"],
        },
        {
            "id": "C003", "type": "C",
            "question": "What bone protection medications are recommended at hospital discharge for hip fracture patients?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["bisphosphonate", "bone protection", "discharge"],
            "tags": ["guideline", "medication"],
        },
        {
            "id": "C004", "type": "C",
            "question": "How should post-operative delirium be prevented and managed in hip fracture patients?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["delirium", "non-pharmacological", "screening"],
            "tags": ["guideline", "delirium"],
        },
        {
            "id": "C005", "type": "C",
            "question": "What does the guideline say about early mobilisation after hip fracture surgery?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["day 1", "mobilisation", "post-operative"],
            "tags": ["guideline", "mobility"],
        },
        {
            "id": "C006", "type": "C",
            "question": "What are the national benchmark targets for hip fracture care quality indicators?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["mortality", "benchmark", "target"],
            "tags": ["guideline", "quality"],
        },
        {
            "id": "C007", "type": "C",
            "question": "What is the recommended role of geriatric medicine in hip fracture care?",
            "expected_tool": "search_clinical_guideline",
            "key_facts": ["geriatrician", "geriatric medicine", "assessment"],
            "tags": ["guideline", "geriatrics"],
        },
    ]

    extra_c = [
        {"id": f"C{i:03d}", "type": "C", "question": q,
         "expected_tool": "search_clinical_guideline",
         "key_facts": [], "tags": ["guideline"]}
        for i, q in enumerate([
            "What anaesthesia type is recommended for hip fracture surgery?",
            "How should cognitive impairment be managed in hip fracture patients?",
            "What are the criteria for access to inpatient rehabilitation?",
            "What is the guideline for managing patients on anticoagulants who have a hip fracture?",
            "How should malnutrition be assessed and managed in hip fracture patients?",
        ], start=8)
    ]
    type_c.extend(extra_c)

    all_tests = type_a + type_b + type_c
    return all_tests


# ─────────────────────────────────────────────────────────────────────────────
# Evaluation runners
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EvalResult:
    id: str
    type: str
    question: str
    expected_tool: str
    tool_called: str | None
    tool_correct: bool
    answer_correct: bool | None  # None = not applicable / not verifiable
    answer_score: float          # 0.0 – 1.0
    hallucination_detected: bool
    latency_seconds: float
    agent_answer: str
    error: str | None
    tags: list[str]


def _extract_number(text: str) -> float | None:
    """Extract the first percentage or decimal number from text."""
    patterns = [
        r"(\d+\.?\d*)\s*%",   # e.g. "7.3%"
        r"(\d+\.?\d*)\s*percent",
        r"(\d+\.\d+)",         # decimal
        r"\b(\d{2,})\b",       # integer >= 10
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            val = float(m.group(1))
            if "%" in pat or "percent" in pat:
                val /= 100
            return val
    return None


def _check_hallucination(answer: str, question: str) -> bool:
    """Simple heuristic: flag if answer contains fabricated specific numbers for well-known facts."""
    lower = answer.lower()
    # NOTE: a previous `(\d+,\d{3})\s+patients` pattern was removed — it false-flagged the
    # TRUE cohort size ("97,429 patients") as fabricated, inflating the hallucination rate.
    # A digit-count heuristic cannot tell a real count from an invented one.
    # Flag a 0%/100% rate only when it is actually attached to a rate claim (not any "100").
    if re.search(r"\b(100|0)\s*%\s*(of|mortali|rate|patients)", lower):
        return True
    # Contradictory mortality claim (>50% in the general population is implausible).
    m = re.search(r"(\d+\.?\d*)\s*%[^.]*mortali", lower)
    if m and float(m.group(1)) > 50:
        return True
    return False


def evaluate_type_a(test: dict, answer: str, tool_log: list[str]) -> EvalResult:
    """Verify statistical answer against pandas ground truth."""
    tool_called = tool_log[0] if tool_log else None
    tool_correct = (tool_called == test["expected_tool"])
    hallucination = _check_hallucination(answer, test["question"])

    answer_correct = None
    score = 0.5  # neutral if we can't verify

    if test.get("expected_value") is not None:
        extracted = _extract_number(answer)
        if extracted is not None:
            diff = abs(extracted - test["expected_value"])
            answer_correct = diff <= test["tolerance"]
            score = 1.0 if answer_correct else max(0.0, 1.0 - diff / (test["tolerance"] * 5))
        else:
            score = 0.2  # answered but no number found

    if hallucination:
        score = max(0.0, score - 0.3)

    return EvalResult(
        id=test["id"], type=test["type"], question=test["question"],
        expected_tool=test["expected_tool"], tool_called=tool_called,
        tool_correct=tool_correct, answer_correct=answer_correct,
        answer_score=round(score, 3), hallucination_detected=hallucination,
        latency_seconds=0, agent_answer=answer, error=None,
        tags=test.get("tags", []),
    )


def evaluate_type_b(test: dict, answer: str, tool_log: list[str]) -> EvalResult:
    """Verify prediction answer: correct tool called + risk level present."""
    tool_called = tool_log[0] if tool_log else None
    tool_correct = any(test["expected_tool"] in t for t in tool_log)
    hallucination = _check_hallucination(answer, test["question"])

    lower = answer.lower()
    has_probability = bool(re.search(r"\d+\.?\d*\s*%", lower))
    has_risk_level = any(w in lower for w in ["high", "moderate", "low", "risk"])
    has_factors = any(w in lower for w in ["factor", "shap", "age", "asa", "frailty"])

    score = (
        0.4 * tool_correct +
        0.2 * has_probability +
        0.2 * has_risk_level +
        0.2 * has_factors
    )
    if hallucination:
        score = max(0.0, score - 0.2)

    return EvalResult(
        id=test["id"], type=test["type"], question=test["question"],
        expected_tool=test["expected_tool"], tool_called=tool_called,
        tool_correct=tool_correct, answer_correct=tool_correct,
        answer_score=round(score, 3), hallucination_detected=hallucination,
        latency_seconds=0, agent_answer=answer, error=None,
        tags=test.get("tags", []),
    )


def evaluate_type_c(test: dict, answer: str, tool_log: list[str]) -> EvalResult:
    """Score guideline answers: check key facts present + tool called."""
    tool_called = tool_log[0] if tool_log else None
    tool_correct = any(test["expected_tool"] in t for t in tool_log)
    hallucination = _check_hallucination(answer, test["question"])

    lower = answer.lower()
    key_facts = test.get("key_facts", [])
    facts_hit = sum(1 for f in key_facts if f.lower() in lower) if key_facts else 0
    fact_score = facts_hit / len(key_facts) if key_facts else 0.5

    score = 0.4 * tool_correct + 0.6 * fact_score
    if hallucination:
        score = max(0.0, score - 0.2)

    return EvalResult(
        id=test["id"], type=test["type"], question=test["question"],
        expected_tool=test["expected_tool"], tool_called=tool_called,
        tool_correct=tool_correct, answer_correct=bool(fact_score > 0.5),
        answer_score=round(score, 3), hallucination_detected=hallucination,
        latency_seconds=0, agent_answer=answer, error=None,
        tags=test.get("tags", []),
    )


def run_eval(
    questions: list[dict] | None = None,
    max_questions: int = 30,
    provider: str = "anthropic",
) -> list[EvalResult]:
    """
    Run the evaluation suite.
    By default runs 30 questions (10 of each type) to save API cost.
    Set max_questions=100 for full eval.
    """
    from agent import HipFractureAgent

    gt = compute_ground_truth()
    all_tests = questions or build_test_dataset(gt)

    # Sample balanced across types
    if max_questions < len(all_tests):
        per_type = max_questions // 3
        sampled = []
        for t in ["A", "B", "C"]:
            pool = [q for q in all_tests if q["type"] == t]
            sampled.extend(pool[:per_type])
        all_tests = sampled

    print(f"Running eval on {len(all_tests)} questions ({provider} backend)...")
    agent = HipFractureAgent(provider=provider)

    results = []
    for i, test in enumerate(all_tests):
        print(f"  [{i+1}/{len(all_tests)}] {test['id']}: {test['question'][:60]}...")
        tool_log = []

        # Capture tool calls by wrapping the agent's dispatch function. The agent calls
        # the module-level agent._call_tool(name, input) for every tool use, so patching
        # it here intercepts every call regardless of provider. (Patching agent_tools.*
        # would NOT work: agent.TOOL_REGISTRY holds direct references to the originals.)
        import agent as agent_mod
        _orig_call_tool = agent_mod._call_tool

        def logging_call_tool(name, tool_input, _log=tool_log, _orig=_orig_call_tool):
            _log.append(name)
            return _orig(name, tool_input)

        agent_mod._call_tool = logging_call_tool

        start = time.time()
        try:
            agent.reset()
            answer = agent.chat(test["question"])
            elapsed = time.time() - start

            if test["type"] == "A":
                r = evaluate_type_a(test, answer, tool_log)
            elif test["type"] == "B":
                r = evaluate_type_b(test, answer, tool_log)
            else:
                r = evaluate_type_c(test, answer, tool_log)

            r.latency_seconds = round(elapsed, 2)

        except Exception as e:
            elapsed = time.time() - start
            r = EvalResult(
                id=test["id"], type=test["type"], question=test["question"],
                expected_tool=test["expected_tool"], tool_called=None,
                tool_correct=False, answer_correct=False,
                answer_score=0.0, hallucination_detected=False,
                latency_seconds=round(elapsed, 2),
                agent_answer="", error=str(e),
                tags=test.get("tags", []),
            )
        finally:
            agent_mod._call_tool = _orig_call_tool

        results.append(r)
        print(f"    → score={r.answer_score:.2f}, tool_correct={r.tool_correct}, latency={r.latency_seconds}s")

    return results


# ─────────────────────────────────────────────────────────────────────────────
# Reporting
# ─────────────────────────────────────────────────────────────────────────────

def print_report(results: list[EvalResult]):
    print("\n" + "=" * 65)
    print("EVALUATION REPORT — Hip Fracture Clinical AI Agent")
    print("=" * 65)

    by_type: dict[str, list[EvalResult]] = {"A": [], "B": [], "C": []}
    for r in results:
        by_type.setdefault(r.type, []).append(r)

    type_labels = {
        "A": "Type A – Statistical Queries",
        "B": "Type B – Prediction Queries",
        "C": "Type C – Guideline Queries",
    }

    for t, label in type_labels.items():
        group = by_type.get(t, [])
        if not group:
            continue
        n = len(group)
        tool_acc = sum(r.tool_correct for r in group) / n
        avg_score = sum(r.answer_score for r in group) / n
        halluc_rate = sum(r.hallucination_detected for r in group) / n
        errors = sum(1 for r in group if r.error)
        avg_latency = sum(r.latency_seconds for r in group) / n

        print(f"\n{label} (n={n})")
        print(f"  Tool selection accuracy : {tool_acc:.0%}")
        print(f"  Answer score (avg)      : {avg_score:.2f} / 1.0")
        print(f"  Hallucination rate      : {halluc_rate:.1%}")
        print(f"  Error rate              : {errors/n:.1%}")
        print(f"  Avg latency             : {avg_latency:.1f}s")

    overall_score = sum(r.answer_score for r in results) / len(results)
    overall_tool = sum(r.tool_correct for r in results) / len(results)
    overall_halluc = sum(r.hallucination_detected for r in results) / len(results)

    print(f"\n{'─'*65}")
    print(f"OVERALL  (n={len(results)})")
    print(f"  Composite score         : {overall_score:.2f} / 1.0")
    print(f"  Tool selection accuracy : {overall_tool:.0%}")
    print(f"  Hallucination rate      : {overall_halluc:.1%}")
    print("=" * 65)

    # Failures worth investigating
    failures = [r for r in results if r.answer_score < 0.4 or r.hallucination_detected]
    if failures:
        print(f"\nFailed cases ({len(failures)}):")
        for r in failures[:5]:
            print(f"  [{r.id}] score={r.answer_score:.2f} halluc={r.hallucination_detected}")
            print(f"         Q: {r.question[:80]}")
            if r.error:
                print(f"         ERR: {r.error}")


def _json_default(o):
    """Make numpy scalar types JSON-serializable."""
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return str(o)


def save_results(results: list[EvalResult], path: str = RESULTS_PATH):
    data = [asdict(r) for r in results]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)
    print(f"\nResults saved to {path}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=15, help="Number of questions to evaluate (default 15)")
    parser.add_argument("--provider", default="anthropic", choices=["anthropic", "openai"])
    parser.add_argument("--full", action="store_true", help="Run full 100-question eval")
    args = parser.parse_args()

    n = 100 if args.full else args.n
    results = run_eval(max_questions=n, provider=args.provider)
    print_report(results)
    save_results(results)
