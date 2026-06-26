"""
Tool definitions for the Hip Fracture Clinical AI Agent.
Each tool is a standalone Python function wrapped for LangChain tool use.

Tools:
  1. query_patient_data   - natural language → pandas query over 97k patients
  2. predict_mortality    - XGBoost 30-day mortality risk for a given patient
  3. predict_recovery     - XGBoost 120-day walking recovery prediction
  4. search_guideline     - RAG retrieval over AQSQHC clinical care standards
"""

import json
import os
import re
import numpy as np
import pandas as pd
from langchain.tools import tool

DATA_PATH = os.path.join(os.path.dirname(__file__), "unsw_datathon_2025.csv")

# Lazy-loaded singleton so we don't read 97k rows on every tool call
_df_cache: pd.DataFrame | None = None

LABEL_MAPS = {
    "sex":        {1: "Male", 2: "Female", 3: "Intersex"},
    "uresidence": {1: "Private residence", 2: "Aged care facility", 3: "Other"},
    "walk":       {1: "No aids", 2: "Stick/crutch", 3: "Frame/two aids", 4: "Wheelchair/bed"},
    "cogstat":    {1: "Normal cognition", 2: "Impaired/dementia"},
    "asa":        {1: "ASA I", 2: "ASA II", 3: "ASA III", 4: "ASA IV", 5: "ASA V"},
    "mort30d":    {1: "Alive", 2: "Deceased"},
    "mort365d":   {1: "Alive", 2: "Deceased"},
    "wdest":      {1: "Home", 2: "Aged care", 3: "Public rehab", 4: "Private rehab", 5: "Other hospital", 6: "Deceased"},
    "fwalk2":     {1: "Yes", 2: "No"},
    "delay":      {1: "No delay (<48h)", 2: "Medically unfit", 3: "Anticoagulation", 4: "Theatre availability", 5: "Surgeon availability", 6: "Delayed diagnosis", 7: "Other"},
    "ftype":      {1: "Intracapsular undisplaced", 2: "Intracapsular displaced", 3: "Per/intertrochanteric", 4: "Subtrochanteric"},
    "gerimed":    {0: "No", 1: "Yes", 8: "No service available", 9: "Not known"},
    "anaesth":    {1: "General", 2: "Spinal", 3: "General+Spinal", 4: "Spinal/regional", 5: "General+regional", 6: "Other"},
}


def _get_df() -> pd.DataFrame:
    global _df_cache
    if _df_cache is None:
        _df_cache = pd.read_csv(DATA_PATH, low_memory=False)
        # Compute surgery timing feature
        _df_cache["time_to_surgery_hours"] = (
            pd.to_numeric(_df_cache.get("sdatetime_datediff"), errors="coerce") -
            pd.to_numeric(_df_cache.get("arrdatetime_datediff"), errors="coerce")
        ) * 24
        _df_cache.loc[_df_cache["time_to_surgery_hours"] < 0, "time_to_surgery_hours"] = np.nan
    return _df_cache


# ---------------------------------------------------------------------------
# Tool 1: Statistical data query
# ---------------------------------------------------------------------------

@tool
def query_patient_data(question: str) -> str:
    """
    Query the ANZHFR hip fracture dataset (97,429 patients) to answer statistical
    questions. Use this tool for questions about counts, proportions, averages,
    trends, or comparisons across patient groups.

    Examples of questions this handles:
    - "What percentage of patients died within 30 days?"
    - "What is the median age of patients?"
    - "How many patients had surgery delayed more than 48 hours?"
    - "What is the 30-day mortality rate for ASA IV patients?"
    - "What proportion of patients were female?"
    """
    df = _get_df()
    q = question.lower()
    results = {}

    try:
        # --- Mortality stats ---
        if any(k in q for k in ["30-day mortality", "mort30d", "died within 30", "30 day death"]):
            mort = pd.to_numeric(df["mort30d"], errors="coerce")
            n_valid = mort.notna().sum()
            n_deceased = (mort == 2).sum()
            results["30-day mortality"] = {
                "deceased": int(n_deceased),
                "total_with_data": int(n_valid),
                "rate": f"{n_deceased / n_valid:.1%}",
            }

        if any(k in q for k in ["365-day", "1-year", "one year", "mort365"]):
            mort = pd.to_numeric(df["mort365d"], errors="coerce")
            n_valid = mort.notna().sum()
            n_deceased = (mort == 2).sum()
            results["365-day mortality"] = {
                "deceased": int(n_deceased),
                "total_with_data": int(n_valid),
                "rate": f"{n_deceased / n_valid:.1%}",
            }

        # --- Age stats ---
        if any(k in q for k in ["age", "old", "median age", "average age"]):
            age = pd.to_numeric(df["age"], errors="coerce")
            results["age_statistics"] = {
                "median": float(age.median()),
                "mean": round(float(age.mean()), 1),
                "min": int(age.min()),
                "max": int(age.max()),
                "pct_80_plus": f"{(age >= 80).sum() / age.notna().sum():.1%}",
            }

        # --- Sex/gender ---
        if any(k in q for k in ["sex", "gender", "female", "male", "women", "men"]):
            sex = pd.to_numeric(df["sex"], errors="coerce")
            results["sex_distribution"] = {
                "male": int((sex == 1).sum()),
                "female": int((sex == 2).sum()),
                "pct_female": f"{(sex == 2).sum() / sex.notna().sum():.1%}",
            }

        # --- Surgery delay ---
        if any(k in q for k in ["delay", "48 hour", "48h", "time to surgery", "surgery wait"]):
            delay = pd.to_numeric(df["delay"], errors="coerce")
            no_delay = (delay == 1).sum()
            delayed = (delay > 1).sum()
            n_valid = delay.notna().sum()
            tts = df["time_to_surgery_hours"].dropna()
            results["surgery_timing"] = {
                "no_delay_under_48h": int(no_delay),
                "delayed_over_48h": int(delayed),
                "pct_on_time": f"{no_delay / n_valid:.1%}" if n_valid else "N/A",
                "median_time_to_surgery_hours": round(float(tts.median()), 1) if len(tts) else "N/A",
            }

        # --- ASA grade ---
        if any(k in q for k in ["asa", "anaesthetic risk", "anesthetic risk"]):
            asa = pd.to_numeric(df["asa"], errors="coerce")
            asa_counts = asa.value_counts().sort_index()
            results["asa_distribution"] = {
                LABEL_MAPS["asa"].get(int(k), f"ASA {k}"): int(v)
                for k, v in asa_counts.items()
            }

        # --- Frailty ---
        if any(k in q for k in ["frailty", "frail", "clinical frailty"]):
            frailty = pd.to_numeric(df["frailty"], errors="coerce")
            results["frailty_statistics"] = {
                "median_frailty_score": float(frailty.median()),
                "pct_severely_frail_7plus": f"{(frailty >= 7).sum() / frailty.notna().sum():.1%}",
                "distribution": frailty.value_counts().sort_index().to_dict(),
            }

        # --- Walking recovery ---
        if any(k in q for k in ["walk", "walking", "mobility", "120 day", "120-day"]):
            fwalk = pd.to_numeric(df["fwalk2"], errors="coerce")
            n_valid = fwalk.notna().sum()
            results["walking_recovery_120d"] = {
                "recovered": int((fwalk == 1).sum()),
                "not_recovered": int((fwalk == 2).sum()),
                "pct_recovered": f"{(fwalk == 1).sum() / n_valid:.1%}" if n_valid else "N/A",
            }

        # --- Geriatric assessment ---
        if any(k in q for k in ["geriatric", "gerimed", "geriatrician"]):
            ger = pd.to_numeric(df["gerimed"], errors="coerce")
            n_valid = ger.notna().sum()
            results["geriatric_assessment"] = {
                "assessed": int((ger == 1).sum()),
                "not_assessed": int((ger == 0).sum()),
                "pct_assessed": f"{(ger == 1).sum() / n_valid:.1%}" if n_valid else "N/A",
            }

        # --- Discharge destination ---
        if any(k in q for k in ["discharge", "destination", "rehab", "home", "aged care"]):
            wdest = pd.to_numeric(df["wdest"], errors="coerce")
            dist = wdest.value_counts().sort_index()
            results["discharge_destination"] = {
                LABEL_MAPS["wdest"].get(int(k), f"Code {k}"): int(v)
                for k, v in dist.items()
            }

        # --- General count ---
        if any(k in q for k in ["total", "how many", "count", "number of patient"]):
            results["total_patients"] = len(df)

        if not results:
            # Fallback: return basic summary
            results["dataset_summary"] = {
                "total_patients": len(df),
                "available_variables": len(df.columns),
                "note": "Please specify a more targeted question (e.g. mortality rate, age distribution, surgery timing).",
            }

    except Exception as e:
        results["error"] = str(e)

    return json.dumps(results, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# Tool 2: Walking recovery prediction (primary model — AUC 0.84)
# ---------------------------------------------------------------------------

@tool
def predict_walking_recovery(patient_json: str) -> str:
    """
    Predict whether a patient will recover their walking ability by 120 days
    post-discharge, using the trained XGBoost model (AUC 0.84).
    The strongest predictor is pre-admission walking ability.

    Input: JSON string with patient features:
      age (numeric), sex (1=Male, 2=Female), uresidence (1=Home, 2=Aged care),
      walk (1=No aids, 2=Stick, 3=Frame, 4=Wheelchair/bed),
      cogstat (1=Normal, 2=Impaired), asa (1-5, ASA grade),
      frailty (1-9, Clinical Frailty Scale),
      ftype (1=Intracapsular undispl, 2=Intracapsular displ, 3=Pertrochanteric, 4=Subtrochanteric),
      ptype (1=Public, 2=Private), analges (1=Nerve block pre-OT, 2=In OT, 3=Both, 4=Neither)

    Example: {"age": 78, "sex": 1, "walk": 2, "asa": 3, "frailty": 5, "ftype": 2}
    """
    from train_model import predict_patient
    try:
        features = json.loads(patient_json)
        result = predict_patient(features, model_name="fwalk2_model")

        explanation = []
        for factor in result["top_risk_factors"]:
            direction = "supports" if factor["shap_value"] > 0 else "hinders"
            explanation.append(f"  - {factor['feature']}: {direction} recovery (SHAP={factor['shap_value']:+.3f})")

        output = (
            f"120-Day Walking Recovery Prediction\n"
            f"Recovery Probability: {result['risk_probability']:.1%}\n"
            f"Outlook: {'Favourable' if result['risk_probability'] >= 0.3 else 'Guarded'}\n"
            f"Model AUC: {result['auc_at_training']:.3f}\n\n"
            f"Key Factors:\n" + "\n".join(explanation) +
            "\n\nNote: Clinical review recommended before care planning decisions."
        )
        return output
    except FileNotFoundError:
        return "Error: Model not trained yet. Run train_model.py first."
    except Exception as e:
        return f"Error: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 3: Rehabilitation access prediction (AUC 0.78)
# ---------------------------------------------------------------------------

@tool
def predict_rehab_access(patient_json: str) -> str:
    """
    Predict whether a patient will be discharged to a rehabilitation unit
    (public or private) after acute hip fracture care. Uses XGBoost (AUC 0.78).
    Key predictors: usual place of residence, cognitive status, age, frailty, insurance type.

    Input: JSON string with patient features (same schema as predict_walking_recovery).
    Example: {"age": 75, "sex": 2, "walk": 2, "asa": 2, "ptype": 2, "uresidence": 1}
    """
    from train_model import predict_patient
    try:
        features = json.loads(patient_json)
        result = predict_patient(features, model_name="rehab_model")

        explanation = []
        for factor in result["top_risk_factors"]:
            direction = "increases" if factor["shap_value"] > 0 else "decreases"
            explanation.append(f"  - {factor['feature']}: {direction} rehab likelihood (SHAP={factor['shap_value']:+.3f})")

        output = (
            f"Rehabilitation Access Prediction\n"
            f"Probability of Rehab Discharge: {result['risk_probability']:.1%}\n"
            f"Likelihood: {'High' if result['risk_probability'] >= 0.5 else 'Low'}\n"
            f"Model AUC: {result['auc_at_training']:.3f}\n\n"
            f"Key Factors:\n" + "\n".join(explanation)
        )
        return output
    except FileNotFoundError:
        return "Error: Model not trained yet. Run train_model.py first."
    except Exception as e:
        return f"Error: {str(e)}"


# ---------------------------------------------------------------------------
# Tool 4: Clinical guideline RAG search
# ---------------------------------------------------------------------------

@tool
def search_clinical_guideline(query: str) -> str:
    """
    Search the AQSQHC Hip Fracture Clinical Care Standards (2016 & 2023) for
    evidence-based guidelines relevant to the query. Use this tool when the
    question involves clinical protocols, care standards, best practices, or
    quality indicators for hip fracture management.

    Examples:
    - "What is the standard for time to surgery?"
    - "How should post-operative delirium be managed?"
    - "What are the pain management guidelines in the ED?"
    - "What bone protection medications are recommended?"
    """
    try:
        from rag_pipeline import search_guidelines
        results = search_guidelines(query, k=3)
        if not results:
            return "No relevant guideline sections found for this query."
        output = f"Clinical Guideline References for: '{query}'\n\n"
        for i, r in enumerate(results, 1):
            output += f"[{i}] {r['source']}\n{r['content']}\n\n"
        return output.strip()
    except ImportError:
        return (
            "RAG pipeline not initialised. "
            "Key guideline summary:\n"
            "- Surgery should occur within 48 hours of admission (ACSQHC standard)\n"
            "- Pain assessment must occur within 30 minutes of ED presentation\n"
            "- All patients should receive geriatric medicine assessment\n"
            "- Bone protection medication should be prescribed at discharge\n"
            "- Early mobilisation (day 1 post-surgery) is recommended\n"
            "- 30-day mortality benchmark: <7% (ACSQHC 2023)"
        )
    except Exception as e:
        return f"Guideline search error: {str(e)}"
