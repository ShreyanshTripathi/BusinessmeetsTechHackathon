"""Staffing model: the day before a shift, which stations are likely to end up without qualified cover?

Small and explainable on purpose: a logistic regression on 11 roster-level features. The supervisor sees
a risk per station plus the reasons (coefficients), and can act early: pair a trainee, book a floater,
plan cross-training. Rules in backend/shiftloop/agents/staffing.py still handle the live shift.

Run generate_staffing_data.py first.
"""
from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import DATA_DIR, MODEL_DIR, save_card

CATEGORICAL = ["zone", "shift", "day_of_week"]
NUMERIC = ["safety_critical", "operator_level", "qualified_backups", "zone_trainees", "crew_trainees",
           "zone_floaters", "zone_absence_rate_4w", "crew_overtime_h_last_week"]
FEATURES = CATEGORICAL + NUMERIC
TEST_FROM = "2026-09-01"  # train on Mar-Aug, test on September (the hardest month of the ramp)


def precision_at_top(df: pd.DataFrame, scores: np.ndarray, k: int = 3) -> float:
    """Of the k riskiest stations per shift, how many really had a gap?"""
    d = df.assign(score=scores)
    top = d.sort_values("score", ascending=False).groupby(["date", "shift"]).head(k)
    return float(top["gap"].mean())


def main() -> None:
    df = pd.read_csv(DATA_DIR / "staffing_shifts.csv")
    train, test = df[df.date < TEST_FROM], df[df.date >= TEST_FROM]

    model = make_pipeline(
        make_column_transformer(
            (OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            (StandardScaler(), NUMERIC),
        ),
        LogisticRegression(max_iter=1000, class_weight="balanced"),
    )
    model.fit(train[FEATURES], train["gap"])
    p = model.predict_proba(test[FEATURES])[:, 1]

    # Baseline: the rule a supervisor might use today
    rule = ((test.operator_level < 2) | (test.qualified_backups == 0)).astype(float).to_numpy()

    metrics = {
        "test_rows": int(len(test)),
        "test_gap_rate": round(float(test.gap.mean()), 3),
        "roc_auc": round(roc_auc_score(test.gap, p), 3),
        "pr_auc": round(average_precision_score(test.gap, p), 3),
        "precision_top3_per_shift": round(precision_at_top(test, p), 3),
        "baseline_rule_roc_auc": round(roc_auc_score(test.gap, rule), 3),
        "baseline_rule_precision_top3": round(precision_at_top(test, rule + np.random.default_rng(0).random(len(rule)) * 1e-3), 3),
    }
    print(f"Trained on {len(train):,} station-shifts (Mar-Aug), tested on {len(test):,} (September)\n")
    for k, v in metrics.items():
        print(f"  {k:32s} {v}")

    # Refit on everything and explain the drivers
    model.fit(df[FEATURES], df["gap"])
    names = model[0].get_feature_names_out()
    coefs = model[-1].coef_[0]
    drivers = sorted(zip(names, coefs), key=lambda t: -abs(t[1]))[:8]
    print("\nStrongest drivers (standardised coefficient, + means more risk):")
    for n, c in drivers:
        print(f"  {n:40s} {c:+.2f}")

    joblib.dump(model, MODEL_DIR / "staffing_model.joblib")
    save_card("staffing_model", {
        "predicts": "probability that a station ends the shift without qualified cover (gap)",
        "used_by": "staffing agent, the day before the shift",
        "algorithm": "logistic regression (scikit-learn), balanced classes",
        "data": "synthetic: ml/generate_staffing_data.py, 26 weeks x 3 crews x 24 stations, Giga Berlin 2026 ramp",
        "features": FEATURES,
        "not_used": "no names, no individual absence history, no performance data",
        "split": f"train before {TEST_FROM}, test from {TEST_FROM}",
        "metrics": metrics,
        "drivers": {n: round(float(c), 3) for n, c in drivers},
        "limits": "Synthetic data. In production, retrain on the plant's own roster and qualification history.",
        "must_not_be_used_for": "rating, ranking or predicting individual workers",
    })
    print(f"\nSaved {MODEL_DIR.name}/staffing_model.joblib and staffing_model.card.json")


if __name__ == "__main__":
    main()
