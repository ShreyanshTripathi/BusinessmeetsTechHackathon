"""Why did the model say this? Per-prediction drivers that work with any model, forests included.

Tabular: for each input, put it back to a typical value (median or most common) and see how much the risk
drops or rises. The difference is that input's effect on this one prediction.
Text: remove each word from the report and see how much the predicted class loses.
"""
from __future__ import annotations

import re

import numpy as np
import pandas as pd


def reference_values(df: pd.DataFrame, features: list[str]) -> dict:
    """Typical value per feature: median for numbers, most common value for categories."""
    ref = {}
    for f in features:
        col = df[f]
        if pd.api.types.is_numeric_dtype(col):
            v = float(col.median())
            ref[f] = int(v) if v.is_integer() and pd.api.types.is_integer_dtype(col) else v
        else:
            ref[f] = col.mode().iloc[0]
    return ref


def _risk(model, rows: pd.DataFrame, positive=1) -> np.ndarray:
    idx = list(model.classes_).index(positive)
    return model.predict_proba(rows)[:, idx]


def tabular_drivers(model, row: dict, features: list[str], reference: dict, top: int = 4,
                    positive=1, min_effect: float = 1e-3) -> list[dict]:
    """Effect of each input on this prediction: risk(actual row) - risk(row with the input set to typical)."""
    base = pd.DataFrame([{f: row[f] for f in features}])
    variants = []
    for f in features:
        v = base.copy()
        v[f] = reference[f]
        variants.append(v)
    risks = _risk(model, pd.concat([base, *variants], ignore_index=True), positive)
    out = []
    for f, r in zip(features, risks[1:]):
        effect = float(risks[0] - r)
        if abs(effect) >= min_effect:
            out.append({"feature": f, "value": row[f], "typical": reference[f], "effect": round(effect, 3)})
    out.sort(key=lambda d: -abs(d["effect"]))
    return out[:top]


def text_drivers(model, text: str, cls: str, top: int = 4, min_effect: float = 1e-3) -> list[dict]:
    """Words whose removal lowers the probability of `cls` the most."""
    words = list(dict.fromkeys(re.findall(r"[a-z]{3,}", text.lower())))
    if not words:
        return []
    variants = [re.sub(rf"\b{w}\b", " ", text.lower()) for w in words]
    idx = list(model.classes_).index(cls)
    proba = model.predict_proba([text.lower(), *variants])[:, idx]
    out = [{"word": w, "effect": round(float(proba[0] - p), 3)} for w, p in zip(words, proba[1:])]
    out = [d for d in out if d["effect"] >= min_effect]
    out.sort(key=lambda d: -d["effect"])
    return out[:top]
