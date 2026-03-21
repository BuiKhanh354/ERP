from pathlib import Path
import pickle

import requests
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
from sklearn.model_selection import train_test_split


DATASET_URL = "https://raw.githubusercontent.com/shantanu1109/IBM-HR-Analytics-Employee-Attrition-and-Performance-Prediction/main/DATASET/IBM-HR-Analytics-Employee-Attrition-and-Performance.csv"


def find_dataset() -> Path:
    base_dir = Path(__file__).resolve().parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    default_path = data_dir / "WA_Fn-UseC_-HR-Employee-Attrition.csv"
    candidates = [
        default_path,
        base_dir / "WA_Fn-UseC_-HR-Employee-Attrition.csv",
        base_dir.parent / "WA_Fn-UseC_-HR-Employee-Attrition.csv",
        Path.cwd() / "WA_Fn-UseC_-HR-Employee-Attrition.csv",
        Path.cwd() / "ai" / "data" / "WA_Fn-UseC_-HR-Employee-Attrition.csv",
        Path.cwd() / "ai" / "WA_Fn-UseC_-HR-Employee-Attrition.csv",
    ]

    for candidate in candidates:
        if candidate.exists():
            return candidate

    response = requests.get(DATASET_URL, timeout=60)
    response.raise_for_status()
    default_path.write_bytes(response.content)
    return default_path


def main() -> None:
    dataset_path = find_dataset()
    model_path = Path(__file__).resolve().parent / "models" / "attrition_model.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(dataset_path)
    df = df[
        [
            "Age",
            "JobLevel",
            "MonthlyIncome",
            "TotalWorkingYears",
            "YearsAtCompany",
            "JobSatisfaction",
            "OverTime",
            "Attrition",
        ]
    ].copy()

    df["Attrition"] = df["Attrition"].map({"Yes": 1, "No": 0})
    df["OverTime"] = df["OverTime"].map({"Yes": 1, "No": 0})

    X = df.drop("Attrition", axis=1)
    y = df["Attrition"]

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=0.2,
        random_state=42,
    )

    model = RandomForestClassifier(random_state=42)
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    with open(model_path, "wb") as f:
        pickle.dump(model, f)
    print(f"Saved attrition model to {model_path}")
    print(f"Test accuracy: {accuracy:.4f}")


if __name__ == "__main__":
    main()
