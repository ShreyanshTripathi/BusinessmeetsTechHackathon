"""Fire & Safety model: how serious could this reported incident or near miss have been?

Reads the free-text report a team lead or worker writes and predicts the potential severity:
low (levels I-II), medium (III) or high (IV-VI). The names match backend Severity, so the result can
become a safety-agent event directly. When the model is unsure it says so, and the report goes to the
safety expert instead of being auto-rated.

Data: IHM Stefanini industrial safety database (Kaggle), 425 real reports from mining and metals plants.
It is a public stand-in; in production the model is retrained on the plant's own near-miss reports.
Fire, smoke, gas and PPE detection stay with the sensors and cameras in the backend.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict
from sklearn.pipeline import make_pipeline

from common import DATA_DIR, MODEL_DIR, save_card

LEVEL_TO_SEVERITY = {"I": "low", "II": "low", "III": "medium", "IV": "high", "V": "high", "VI": "high"}
CLASSES = ["low", "medium", "high"]
UNSURE_BELOW = 0.5  # max class probability under this -> expert review


def build_model():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True, stop_words="english"),
        LogisticRegression(max_iter=2000, class_weight="balanced", C=3.0),
    )


def main() -> None:
    df = pd.read_csv(DATA_DIR / "industrial_safety_incidents.csv")
    X = df["Description"]
    y = df["Potential Accident Level"].map(LEVEL_TO_SEVERITY)

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    proba = cross_val_predict(build_model(), X, y, cv=cv, method="predict_proba")
    classes = sorted(y.unique())  # sklearn orders classes alphabetically
    pred = np.array(classes)[proba.argmax(1)]
    conf = proba.max(1)
    sure = conf >= UNSURE_BELOW

    print("5-fold cross-validation, all reports:\n")
    print(classification_report(y, pred, labels=CLASSES, zero_division=0))
    print("Confusion matrix (rows = true, cols = predicted):", CLASSES)
    print(confusion_matrix(y, pred, labels=CLASSES))

    high = y == "high"
    metrics = {
        "reports": int(len(df)),
        "accuracy": round(float((pred == y).mean()), 3),
        "high_recall": round(float((pred[high] == "high").mean()), 3),
        "high_precision": round(float((y[pred == "high"] == "high").mean()), 3),
        "high_missed_as_low": round(float((pred[high] == "low").mean()), 3),
        "unsure_share": round(float((~sure).mean()), 3),
        "accuracy_when_sure": round(float((pred[sure] == y[sure]).mean()), 3),
    }
    print()
    for k, v in metrics.items():
        print(f"  {k:22s} {v}")

    model = build_model().fit(X, y)
    joblib.dump(model, MODEL_DIR / "safety_model.joblib")
    save_card("safety_model", {
        "predicts": "potential severity of an incident / near-miss report: low (I-II), medium (III), high (IV-VI)",
        "used_by": "fire & safety agent, when a report is filed",
        "algorithm": "TF-IDF word and word-pair features + logistic regression (scikit-learn)",
        "data": "IHM Stefanini industrial safety database (Kaggle), 425 reports, mining and metals plants",
        "target_note": "potential level, not actual level: how bad it could have been",
        "unsure_rule": f"max class probability below {UNSURE_BELOW} -> safety expert review",
        "split": "5-fold stratified cross-validation",
        "metrics": metrics,
        "limits": "Small public dataset from other industries. Retrain on the plant's own reports before real use.",
        "must_not_be_used_for": "blaming individuals; the report text is about the event, not the person",
    })
    print(f"\nSaved {MODEL_DIR.name}/safety_model.joblib and safety_model.card.json")


if __name__ == "__main__":
    main()
