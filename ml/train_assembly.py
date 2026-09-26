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
from sklearn.metrics import classification_report, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from common import DATA_DIR, MODEL_DIR, save_card

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


def main() -> None:
    df = load()
    cutoff = df["date"].quantile(0.8)  # train on earlier weeks, test on the last 20% of days
    train, test = df[df.date <= cutoff], df[df.date > cutoff]

    model = build_model().fit(train[FEATURES], train["miss_target"])
    p = model.predict_proba(test[FEATURES])[:, 1]
    pred = (p >= 0.5).astype(int)
    print(f"Trained on {len(train)} team-days, tested on {len(test)} later team-days\n")
    print(classification_report(test.miss_target, pred, target_names=["on target", "miss target"]))

    imp = permutation_importance(model, test[FEATURES], test.miss_target, scoring="roc_auc",
                                 n_repeats=10, random_state=0)
    drivers = sorted(zip(FEATURES, imp.importances_mean), key=lambda t: -t[1])
    print("What matters most (drop in ROC AUC when the column is shuffled):")
    for n, v in drivers:
        print(f"  {n:24s} {v:+.3f}")

    miss = test.miss_target == 1
    metrics = {
        "test_team_days": int(len(test)),
        "test_miss_rate": round(float(miss.mean()), 3),
        "roc_auc": round(roc_auc_score(test.miss_target, p), 3),
        "miss_recall": round(float(pred[miss.to_numpy()].mean()), 3),
        "miss_precision": round(float(test.miss_target[pred == 1].mean()), 3),
        "accuracy": round(float((pred == test.miss_target).mean()), 3),
    }
    print()
    for k, v in metrics.items():
        print(f"  {k:16s} {v}")

    model = build_model().fit(df[FEATURES], df["miss_target"])
    joblib.dump(model, MODEL_DIR / "assembly_model.joblib")
    save_card("assembly_model", {
        "predicts": "probability that a line team misses its output target today",
        "used_by": "general assembly agent, at shift start and after a product change",
        "algorithm": "random forest (scikit-learn), 300 trees",
        "data": "UCI Productivity Prediction of Garment Employees, 1,197 team-days (public stand-in)",
        "features": FEATURES,
        "excluded_leaky": LEAKY,
        "split": f"train up to {cutoff.date()}, test after",
        "metrics": metrics,
        "drivers": {n: round(float(v), 3) for n, v in drivers},
        "limits": "Garment data, not car assembly. Retrain on the plant's MES output per team and shift.",
        "must_not_be_used_for": "rating individual workers; the unit is the team",
    })
    print(f"\nSaved {MODEL_DIR.name}/assembly_model.joblib and assembly_model.card.json")


if __name__ == "__main__":
    main()
