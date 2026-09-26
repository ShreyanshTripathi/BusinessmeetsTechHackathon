"""Each arm is a random forest, evaluated honestly against the model it replaced."""
import json

import pandas as pd
import pytest
from sklearn.ensemble import RandomForestClassifier

import train_assembly
import train_safety
import train_staffing
from common import DATA_DIR, MODEL_DIR


@pytest.mark.parametrize("module", [train_staffing, train_assembly, train_safety])
def test_every_arm_uses_a_random_forest(module):
    assert isinstance(module.build_model()[-1], RandomForestClassifier)


def test_staffing_forest_is_evaluated_against_rule_and_logistic_baseline():
    m = train_staffing.evaluate(pd.read_csv(DATA_DIR / "staffing_shifts.csv"))
    assert m["roc_auc"] >= 0.8
    assert m["roc_auc"] > m["baseline_rule_roc_auc"]
    assert "baseline_logreg_roc_auc" in m and "baseline_logreg_precision_top3" in m


def test_assembly_forest_is_evaluated_against_logistic_baseline():
    m = train_assembly.evaluate(train_assembly.load())
    assert m["roc_auc"] >= 0.7
    assert "baseline_logreg_roc_auc" in m


def test_safety_forest_beats_guessing_and_reports_baseline():
    df = pd.read_csv(DATA_DIR / "industrial_safety_incidents.csv")
    m = train_safety.evaluate(df)
    majority = df["Potential Accident Level"].map(train_safety.LEVEL_TO_SEVERITY).value_counts(normalize=True).max()
    assert m["accuracy"] > majority
    assert "baseline_logreg_accuracy" in m and "baseline_logreg_high_recall" in m


@pytest.fixture(scope="session")
def trained():
    for module in (train_staffing, train_assembly, train_safety):
        module.main()
    return {n: json.loads((MODEL_DIR / f"{n}.card.json").read_text())
            for n in ("staffing_model", "assembly_model", "safety_model")}


def test_cards_say_random_forest_and_compare_to_baseline(trained):
    for name, card in trained.items():
        assert "random forest" in card["algorithm"], name
        assert any(k.startswith("baseline_logreg") for k in card["metrics"]), name


def test_tabular_cards_store_reference_values_for_explanations(trained):
    for name, module in (("staffing_model", train_staffing), ("assembly_model", train_assembly)):
        assert set(trained[name]["reference_values"]) == set(module.FEATURES)
