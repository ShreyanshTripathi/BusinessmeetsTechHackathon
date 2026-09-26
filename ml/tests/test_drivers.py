"""Per-prediction drivers: which inputs pushed this prediction up or down."""
import numpy as np
import pandas as pd

from drivers import reference_values, tabular_drivers, text_drivers


class LinearRisk:
    """Fake model: risk rises with 'load', falls with 'backups', ignores 'noise'."""

    classes_ = np.array([0, 1])

    def predict_proba(self, X: pd.DataFrame):
        p = (0.2 + 0.1 * X["load"] - 0.05 * X["backups"]).clip(0, 1).to_numpy()
        return np.column_stack([1 - p, p])


def test_reference_values_use_median_for_numbers_and_mode_for_categories():
    df = pd.DataFrame({"n": [1, 2, 3, 10], "c": ["a", "b", "b", "c"]})
    assert reference_values(df, ["n", "c"]) == {"n": 2.5, "c": "b"}


def test_tabular_drivers_rank_by_effect_and_keep_the_sign():
    row = {"load": 5, "backups": 4, "noise": 99}
    ref = {"load": 1, "backups": 1, "noise": 0}
    out = tabular_drivers(LinearRisk(), row, ["load", "backups", "noise"], ref)
    assert [d["feature"] for d in out] == ["load", "backups"]  # noise has no effect and is dropped
    assert out[0]["effect"] > 0 and out[1]["effect"] < 0
    assert out[0]["value"] == 5 and out[0]["typical"] == 1


def test_tabular_drivers_respect_top_n():
    row = {"load": 5, "backups": 4, "noise": 99}
    ref = {"load": 1, "backups": 1, "noise": 0}
    assert len(tabular_drivers(LinearRisk(), row, ["load", "backups", "noise"], ref, top=1)) == 1


class WordRisk:
    """Fake text model: 'chain' and 'dropped' raise the 'high' class."""

    classes_ = np.array(["high", "low"])

    def predict_proba(self, texts):
        out = []
        for t in texts:
            p = 0.2 + 0.3 * ("chain" in t) + 0.2 * ("dropped" in t)
            out.append([p, 1 - p])
        return np.array(out)


def test_text_drivers_find_the_words_that_raise_the_class():
    out = text_drivers(WordRisk(), "the hoist chain slipped and the pack dropped", "high")
    assert [d["word"] for d in out] == ["chain", "dropped"]
    assert out[0]["effect"] > out[1]["effect"] > 0
