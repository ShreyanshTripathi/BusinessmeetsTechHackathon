"""General Assembly model: at shift start, will this line team miss its output target today?

Data: "Productivity Prediction of Garment Employees" (UCI), 1,197 team-days from a garment factory.
It is a public stand-in for assembly-line data with the same structure:

| garments column      | meaning on the assembly line                  |
|----------------------|-----------------------------------------------|
| team                 | line team / zone                              |
| targeted_productivity| planned output as a share of the line rate    |
| smv                  | work content per unit (standard minutes)      |
| wip                  | units waiting in the buffer                   |
| over_time            | planned overtime (minutes)                    |
| no_of_style_change   | product changes today (new variant, new trim) |
| no_of_workers        | people on the team                            |

Predicts per team, never per worker. Incentive, idle time and idle men are recorded after the shift,
so they would leak the answer and are left out.
"""
from __future__ import annotations

import joblib
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common import DATA_DIR, MODEL_DIR, save_card
from drivers import reference_values

CATEGORICAL = ["department", "day", "team"]
NUMERIC = ["targeted_productivity", "smv", "wip", "over_time", "no_of_style_change", "no_of_workers"]
FEATURES = CATEGORICAL + NUMERIC
LEAKY = ["incentive", "idle_time", "idle_men", "actual_productivity"]


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA_DIR / "garments_worker_productivity.csv", parse_dates=["date"])
    df["department"] = df["department"].str.strip().replace({"sweing": "sewing"})
    df["wip"] = df["wip"].fillna(0)  # finishing has no buffer
    df["miss_target"] = (df["actual_productivity"] < df["targeted_productivity"]).astype(int)
    return df


def build_model():
    return make_pipeline(
        make_column_transformer(
            (OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            ("passthrough", NUMERIC),
        ),
        RandomForestClassifier(n_estimators=300, min_samples_leaf=3, class_weight="balanced", random_state=42),
    )


def build_baseline():
    """A logistic regression on the same features, to check the forest earns its place."""
    return make_pipeline(
        make_column_transformer(
            (OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
            (StandardScaler(), NUMERIC),
        ),
        LogisticRegression(max_iter=2000, class_weight="balanced"),
    )


def split(df: pd.DataFrame):
    cutoff = df["date"].quantile(0.8)  # train on earlier weeks, test on the last 20% of days
    return df[df.date <= cutoff], df[df.date > cutoff], cutoff


def evaluate(df: pd.DataFrame) -> dict:
    train, test, _ = split(df)
    p = build_model().fit(train[FEATURES], train["miss_target"]).predict_proba(test[FEATURES])[:, 1]
    lr = build_baseline().fit(train[FEATURES], train["miss_target"]).predict_proba(test[FEATURES])[:, 1]
    pred = (p >= 0.5).astype(int)
    miss = (test.miss_target == 1).to_numpy()
    return {
        "test_team_days": int(len(test)),
        "test_miss_rate": round(float(miss.mean()), 3),
        "roc_auc": round(roc_auc_score(test.miss_target, p), 3),
        "miss_recall": round(float(pred[miss].mean()), 3),
        "miss_precision": round(float(test.miss_target[pred == 1].mean()), 3),
        "accuracy": round(float((pred == test.miss_target).mean()), 3),
        "baseline_logreg_roc_auc": round(roc_auc_score(test.miss_target, lr), 3),
        "baseline_logreg_miss_recall": round(float((lr >= 0.5)[miss].mean()), 3),
    }


def main() -> None:
    df = load()
    train, test, cutoff = split(df)
    metrics = evaluate(df)
    print(f"Trained on {len(train)} team-days, tested on {len(test)} later team-days\n")
    for k, v in metrics.items():
        print(f"  {k:28s} {v}")

    model = build_model().fit(train[FEATURES], train["miss_target"])
    imp = permutation_importance(model, test[FEATURES], test.miss_target, scoring="roc_auc",
                                 n_repeats=10, random_state=0)
    drivers = sorted(zip(FEATURES, imp.importances_mean), key=lambda t: -t[1])
    print("\nWhat matters most (drop in ROC AUC when the column is shuffled):")
    for n, v in drivers:
        print(f"  {n:24s} {v:+.3f}")

    model = build_model().fit(df[FEATURES], df["miss_target"])
    joblib.dump(model, MODEL_DIR / "assembly_model.joblib")
    save_card("assembly_model", {
        "predicts": "probability that a line team misses its output target today",
        "used_by": "general assembly agent, at shift start and after a product change",
        "algorithm": "random forest (scikit-learn), 300 trees, min 3 team-days per leaf, balanced classes",
        "explanations": "per prediction: drivers.tabular_drivers against reference_values; plain language: explain.py",
        "data": "UCI Productivity Prediction of Garment Employees, 1,197 team-days (public stand-in)",
        "features": FEATURES,
        "reference_values": reference_values(df, FEATURES),
        "excluded_leaky": LEAKY,
        "split": f"train up to {cutoff.date()}, test after",
        "metrics": metrics,
        "importances": {n: round(float(v), 3) for n, v in drivers},
        "limits": "Garment data, not car assembly. Retrain on the plant's MES output per team and shift.",
        "must_not_be_used_for": "rating individual workers; the unit is the team",
    })
    print(f"\nSaved {MODEL_DIR.name}/assembly_model.joblib and assembly_model.card.json")


if __name__ == "__main__":
    main()
