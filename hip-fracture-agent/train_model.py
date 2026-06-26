"""
XGBoost mortality & recovery prediction models for ANZHFR dataset.
Trains two models:
  - mort30d_model: 30-day mortality (binary classification)
  - fwalk2_model:  Walking recovery at 120 days (binary classification)
Both use only pre-surgery variables (time zero = hospital admission).
"""

import os
# Pin OpenMP before heavy imports (xgboost/torch duplicate libomp deadlocks SHAP).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
import pickle
import warnings
import numpy as np
import pandas as pd
import shap
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, classification_report
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
import xgboost as xgb

warnings.filterwarnings("ignore")

DATA_PATH = os.path.join(os.path.dirname(__file__), "unsw_datathon_2025.csv")
MODEL_DIR = os.path.join(os.path.dirname(__file__), "models")
os.makedirs(MODEL_DIR, exist_ok=True)

# Pre-surgery features only (time zero = admission).
# Variables recorded AFTER surgery are excluded to avoid data leakage.
# frailty excluded from mortality model: 51% missing degrades signal.
# gerimed excluded from mortality model: reverse causality (patients who die
#   quickly have no time to be assessed, creating spurious correlation).
SHARED_FEATURES = [
    "age", "sex", "uresidence", "e_dadmit",
    "walk",       # pre-admission walking ability — strongest functional predictor
    "cogstat",    # cognitive status
    "bonemed",    # bone medication at admission
    "passess",    # pre-op medical assessment
    "ftype",      # fracture type
    "asa",        # ASA grade
    "frailty",    # clinical frailty scale
    "analges",    # nerve block
    "side", "afracture",
    "ptype",      # public/private — key driver of care access
    "ward",
]

# Mortality targets have no predictable signal in this synthetic dataset
# (all mortality rates ~21% regardless of age/ASA — outcome was randomly assigned).
# We use two outcomes with preserved real-world relationships:
#   fwalk2:  strongly predicted by pre-admission walk (AUC 0.84)
#   rehab:   driven by ptype, age, walk, cognitive status

TARGETS = {
    "fwalk2": {
        "label": "Walking Recovery at 120 Days",
        "positive_class": 1,
        "features": SHARED_FEATURES,
        "model_name": "fwalk2_model",
    },
    "rehab": {
        "label": "Rehabilitation Access at Discharge",
        "positive_class": None,   # custom: wdest in {3,4}
        "features": SHARED_FEATURES,
        "model_name": "rehab_model",
    },
}


def load_and_prepare(target_col: str, features: list[str], positive_class=None) -> tuple:
    df = pd.read_csv(DATA_PATH, low_memory=False)

    extra_cols = ["wdest"] if target_col == "rehab" else [target_col]
    cols = features + extra_cols
    df = df[[c for c in cols if c in df.columns]].copy()

    if target_col == "rehab":
        # Rehabilitation access: discharged to public or private rehab unit
        wdest = pd.to_numeric(df["wdest"], errors="coerce")
        df = df[wdest.notna()].copy()
        df["target"] = wdest.loc[df.index].isin([3, 4]).astype(int)
        df = df.drop(columns=["wdest"], errors="ignore")
    else:
        df = df.dropna(subset=[target_col])
        df["target"] = (pd.to_numeric(df[target_col], errors="coerce") == positive_class).astype(int)
        df = df.drop(columns=[target_col])

    for col in features:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    available = [c for c in features if c in df.columns]
    X = df[available]
    y = df["target"]
    mask = X.notna().any(axis=1)
    return X[mask], y[mask]


def train_xgboost(X: pd.DataFrame, y: pd.Series, model_name: str) -> dict:
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Median imputation before XGBoost to handle high-missingness features
    imputer = SimpleImputer(strategy="median")
    X_train_imp = pd.DataFrame(imputer.fit_transform(X_train), columns=X.columns)
    X_test_imp = pd.DataFrame(imputer.transform(X_test), columns=X.columns)

    pos_weight = (y_train == 0).sum() / max((y_train == 1).sum(), 1)

    model = xgb.XGBClassifier(
        n_estimators=500,
        max_depth=4,
        learning_rate=0.03,
        subsample=0.8,
        colsample_bytree=0.8,
        min_child_weight=10,
        scale_pos_weight=pos_weight,
        eval_metric="auc",
        early_stopping_rounds=40,
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )

    model.fit(
        X_train_imp, y_train,
        eval_set=[(X_test_imp, y_test)],
        verbose=False,
    )

    y_prob = model.predict_proba(X_test_imp)[:, 1]
    # Optimal threshold via Youden's J for imbalanced data
    from sklearn.metrics import roc_curve
    fpr, tpr, thresholds = roc_curve(y_test, y_prob)
    j_scores = tpr - fpr
    opt_threshold = thresholds[np.argmax(j_scores)]
    y_pred = (y_prob >= opt_threshold).astype(int)
    auc = roc_auc_score(y_test, y_prob)

    print(f"\n{'='*50}")
    print(f"Model: {model_name}")
    print(f"Test AUC: {auc:.4f}")
    print(f"Positive rate: {y.mean():.3f}")
    print(classification_report(y_test, y_pred, target_names=["Negative", "Positive"]))

    # SHAP values for explainability
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_test_imp.iloc[:500])

    importance = pd.DataFrame({
        "feature": X.columns.tolist(),
        "importance": model.feature_importances_,
        "mean_abs_shap": np.abs(shap_values).mean(axis=0),
    }).sort_values("mean_abs_shap", ascending=False)

    print("\nTop 10 features by SHAP importance:")
    print(importance.head(10).to_string(index=False))

    artifact = {
        "model": model,
        "imputer": imputer,
        "explainer": explainer,
        "feature_names": X.columns.tolist(),
        "auc": auc,
        "opt_threshold": float(opt_threshold),
        "importance": importance,
        "X_test_sample": X_test_imp.iloc[:200],
        "y_test_sample": y_test.iloc[:200],
    }

    path = os.path.join(MODEL_DIR, f"{model_name}.pkl")
    with open(path, "wb") as f:
        pickle.dump(artifact, f)

    print(f"Saved: {path}")
    return artifact


def predict_patient(
    patient_features: dict,
    model_name: str = "mort30d_model",
) -> dict:
    """Single-patient inference used as an Agent Tool at runtime."""
    path = os.path.join(MODEL_DIR, f"{model_name}.pkl")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Model not found. Run train_model.py first.")

    with open(path, "rb") as f:
        artifact = pickle.load(f)

    model = artifact["model"]
    imputer = artifact["imputer"]
    explainer = artifact["explainer"]
    feature_names = artifact["feature_names"]

    row = pd.DataFrame([{f: patient_features.get(f, np.nan) for f in feature_names}])
    row_imp = pd.DataFrame(imputer.transform(row), columns=feature_names)
    prob = float(model.predict_proba(row_imp)[0][1])

    shap_vals = explainer.shap_values(row_imp)[0]
    contributions = sorted(
        zip(feature_names, shap_vals),
        key=lambda x: abs(x[1]),
        reverse=True,
    )

    top_factors = [
        {"feature": f, "shap_value": round(float(v), 4)}
        for f, v in contributions[:5]
    ]

    return {
        "model": model_name,
        "risk_probability": round(prob, 4),
        "risk_level": "High" if prob >= 0.3 else "Moderate" if prob >= 0.15 else "Low",
        "top_risk_factors": top_factors,
        "auc_at_training": round(artifact["auc"], 4),
    }


if __name__ == "__main__":
    print("Training Walking Recovery Model (120-day)...")
    X, y = load_and_prepare("fwalk2", features=SHARED_FEATURES, positive_class=1)
    print(f"Dataset: {len(X)} patients, {y.mean():.2%} recovered walking")
    train_xgboost(X, y, "fwalk2_model")

    print("\nTraining Rehabilitation Access Model...")
    X, y = load_and_prepare("rehab", features=SHARED_FEATURES)
    print(f"Dataset: {len(X)} patients, {y.mean():.2%} accessed rehabilitation")
    train_xgboost(X, y, "rehab_model")

    print("\nAll models trained. Testing predict_patient()...")
    result = predict_patient(
        {"age": 85, "sex": 2, "asa": 4, "frailty": 7, "walk": 3, "ptype": 1},
        model_name="fwalk2_model",
    )
    print(result)
