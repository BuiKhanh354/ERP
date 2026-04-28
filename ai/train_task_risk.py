from __future__ import annotations

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.model_selection import train_test_split

try:
    from xgboost import XGBClassifier
except Exception as exc:
    raise RuntimeError(
        "xgboost is required. Install with: .\\venv\\Scripts\\pip.exe install xgboost"
    ) from exc


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"

DATASET_PATH = DATA_DIR / "task_risk_train.csv"
MODEL_PATH = MODEL_DIR / "task_risk_xgb.pkl"
META_PATH = MODEL_DIR / "task_risk_meta.json"
FEATURE_IMPORTANCE_PATH = MODEL_DIR / "task_risk_shap_top_features.json"

RANDOM_SEED = 42
N_ROWS = 2500

FEATURE_COLUMNS = [
    "progress_percent",
    "days_to_due",
    "estimated_hours",
    "actual_hours",
    "warning_count",
    "kpi_current",
    "has_overdue_history",
    "is_critical",
]
TARGET_COLUMN = "is_delayed"


def _sigmoid(x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-x))


def generate_synthetic_dataset(n_rows: int = N_ROWS, random_seed: int = RANDOM_SEED) -> pd.DataFrame:
    rng = np.random.default_rng(random_seed)

    progress_percent = rng.integers(0, 101, size=n_rows)
    days_to_due = rng.integers(-15, 31, size=n_rows)
    estimated_hours = rng.uniform(2.0, 80.0, size=n_rows).round(2)
    effort_factor = rng.uniform(0.7, 1.6, size=n_rows)
    actual_hours = (estimated_hours * effort_factor).round(2)
    warning_count = rng.integers(0, 6, size=n_rows)
    kpi_current = rng.uniform(45.0, 100.0, size=n_rows).round(2)
    has_overdue_history = rng.integers(0, 2, size=n_rows)
    is_critical = rng.integers(0, 2, size=n_rows)

    # Synthetic delay probability with business-like signal.
    score = (
        (progress_percent < 60).astype(float) * 1.2
        + (days_to_due < 0).astype(float) * 1.5
        + (days_to_due <= 2).astype(float) * 0.8
        + (actual_hours > estimated_hours * 1.2).astype(float) * 0.7
        + (warning_count >= 3).astype(float) * 0.9
        + (kpi_current < 70).astype(float) * 0.8
        + has_overdue_history * 0.9
        + is_critical * 0.4
        + rng.normal(0.0, 0.45, size=n_rows)
        - 1.4
    )
    probability = _sigmoid(score)
    is_delayed = (rng.random(n_rows) < probability).astype(int)

    df = pd.DataFrame(
        {
            "progress_percent": progress_percent,
            "days_to_due": days_to_due,
            "estimated_hours": estimated_hours,
            "actual_hours": actual_hours,
            "warning_count": warning_count,
            "kpi_current": kpi_current,
            "has_overdue_history": has_overdue_history,
            "is_critical": is_critical,
            "is_delayed": is_delayed,
        }
    )
    return df


def train_xgboost_model(df: pd.DataFrame) -> tuple[XGBClassifier, dict]:
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=RANDOM_SEED,
        stratify=y,
    )

    model = XGBClassifier(
        n_estimators=200,
        learning_rate=0.07,
        max_depth=5,
        subsample=0.9,
        colsample_bytree=0.9,
        reg_lambda=1.0,
        random_state=RANDOM_SEED,
        eval_metric="logloss",
    )
    model.fit(X_train, y_train)

    pred = model.predict(X_test)
    pred_proba = model.predict_proba(X_test)[:, 1]

    metrics = {
        "accuracy": round(float(accuracy_score(y_test, pred)), 4),
        "roc_auc": round(float(roc_auc_score(y_test, pred_proba)), 4),
        "train_size": int(len(X_train)),
        "test_size": int(len(X_test)),
        "positive_rate": round(float(y.mean()), 4),
    }
    return model, metrics


def save_shap_top_features(model: XGBClassifier, X_sample: pd.DataFrame) -> dict | None:
    try:
        import shap  # type: ignore

        explainer = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_sample)
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        mean_abs = np.abs(shap_values).mean(axis=0)

        top_idx = np.argsort(mean_abs)[::-1][:5]
        top_features = []
        for idx in top_idx:
            top_features.append(
                {
                    "feature": FEATURE_COLUMNS[int(idx)],
                    "mean_abs_shap": round(float(mean_abs[int(idx)]), 6),
                }
            )
        payload = {"top_features": top_features}
        FEATURE_IMPORTANCE_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return payload
    except Exception:
        return None


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    df = generate_synthetic_dataset()
    df.to_csv(DATASET_PATH, index=False, encoding="utf-8")

    model, metrics = train_xgboost_model(df)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    X_sample = df[FEATURE_COLUMNS].sample(n=min(300, len(df)), random_state=RANDOM_SEED)
    shap_payload = save_shap_top_features(model, X_sample)

    meta = {
        "model": "xgboost.XGBClassifier",
        "dataset_path": str(DATASET_PATH),
        "model_path": str(MODEL_PATH),
        "feature_columns": FEATURE_COLUMNS,
        "target_column": TARGET_COLUMN,
        "metrics": metrics,
        "shap_top_features_path": str(FEATURE_IMPORTANCE_PATH) if shap_payload else None,
    }
    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Synthetic dataset saved: {DATASET_PATH}")
    print(f"Model saved: {MODEL_PATH}")
    print(f"Metadata saved: {META_PATH}")
    print(f"Metrics: {metrics}")
    if shap_payload:
        print(f"SHAP top features saved: {FEATURE_IMPORTANCE_PATH}")
    else:
        print("SHAP step skipped (package missing or runtime issue).")


if __name__ == "__main__":
    main()
