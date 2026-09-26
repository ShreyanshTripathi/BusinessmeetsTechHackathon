"""Use the three trained models and get results in the backend's event format.

Each function returns dicts shaped like backend/shiftloop/models.py `Event` (agent, type, zone, station,
severity, confidence, evidence, suggested_action, data), so an agent can emit them without changes to the
central intelligence. Run this file for a demo: python predict.py
"""
from __future__ import annotations

import json
from functools import cache

import joblib
import numpy as np
import pandas as pd

from common import MODEL_DIR
from drivers import tabular_drivers, text_drivers
from train_assembly import FEATURES as ASSEMBLY_FEATURES
from train_safety import UNSURE_BELOW
from train_staffing import FEATURES as STAFFING_FEATURES


@cache
def _load(name: str):
    return joblib.load(MODEL_DIR / f"{name}.joblib")


@cache
def _card(name: str) -> dict:
    return json.loads((MODEL_DIR / f"{name}.card.json").read_text())


# --------------------------------------------------------------------------- staffing


def staffing_risk(stations: list[dict], top: int = 3, min_risk: float = 0.5) -> list[dict]:
    """Rank stations for tomorrow's shift by risk of ending up without qualified cover.

    Each dict needs the columns in train_staffing.FEATURES plus "station".
    """
    model, ref = _load("staffing_model"), _card("staffing_model")["reference_values"]
    df = pd.DataFrame(stations)
    df["risk"] = model.predict_proba(df[STAFFING_FEATURES])[:, 1]
    events = []
    for r in df.sort_values("risk", ascending=False).head(top).itertuples():
        if r.risk < min_risk:
            continue
        drivers = tabular_drivers(model, df.loc[r.Index].to_dict(), STAFFING_FEATURES, ref)
        why = []
        if r.operator_level < 2:
            why.append(f"planned operator is a trainee (level {r.operator_level})")
        why.append(f"{r.qualified_backups} qualified floater(s) for {r.station} on the crew")
        if r.zone_trainees:
            why.append(f"{r.zone_trainees} trainee(s) in zone {r.zone} also need floaters")
        why.append(f"zone {r.zone} absence rate last 4 weeks: {r.zone_absence_rate_4w:.0%}")
        events.append({
            "agent": "staffing", "type": "cover_risk_tomorrow", "zone": r.zone, "station": r.station,
            "severity": "high" if r.risk >= 0.75 else "medium", "confidence": round(float(r.risk), 2),
            "evidence": [f"{r.risk:.0%} risk of no qualified cover on the {r.shift} shift"] + why,
            "suggested_action": "Book a qualified floater or plan cross-training for this station",
            "data": {"risk": round(float(r.risk), 3), "model": "staffing_model", "drivers": drivers},
        })
    return events


# --------------------------------------------------------------------------- assembly


def assembly_risk(team_day: dict, zone: str) -> dict:
    """Risk that a line team misses today's output target (columns from train_assembly.FEATURES)."""
    model = _load("assembly_model")
    p = float(model.predict_proba(pd.DataFrame([team_day])[ASSEMBLY_FEATURES])[0, 1])
    drivers = tabular_drivers(model, team_day, ASSEMBLY_FEATURES, _card("assembly_model")["reference_values"])
    return {
        "agent": "assembly", "type": "output_target_risk", "zone": zone, "station": None,
        "severity": "high" if p >= 0.7 else "medium" if p >= 0.5 else "low", "confidence": round(p, 2),
        "evidence": [f"{p:.0%} risk of missing today's target",
                     f"{team_day['no_of_workers']} people, {team_day['wip']} units in buffer, "
                     f"{team_day['no_of_style_change']} product change(s)"],
        "suggested_action": "Check staffing and buffer before the first break" if p >= 0.5 else "No action",
        "data": {"risk": round(p, 3), "model": "assembly_model", "drivers": drivers},
    }


# --------------------------------------------------------------------------- safety


def safety_triage(report: str, zone: str, station: str | None = None) -> dict:
    """Potential severity of an incident / near-miss report. Unsure results go to the safety expert."""
    model = _load("safety_model")
    proba = model.predict_proba([report])[0]
    cls = model.classes_[proba.argmax()]
    conf = float(proba.max())
    unsure = conf < UNSURE_BELOW
    drivers = text_drivers(model, report, cls)
    terms = [d["word"] for d in drivers]
    return {
        "agent": "safety", "type": "near_miss_unsure" if unsure else "near_miss_rated",
        "zone": zone, "station": station, "severity": "low" if unsure else cls, "confidence": round(conf, 2),
        "evidence": [f"potential severity: {cls} ({conf:.0%})" + (" - model unsure" if unsure else ""),
                     "key words: " + (", ".join(terms) if terms else "none")],
        "suggested_action": "Safety expert rates this report" if unsure
        else "Review the station method with the engineer" if cls == "high" else "Log and track",
        "data": {"probabilities": dict(zip(model.classes_, np.round(proba, 3).tolist())), "model": "safety_model",
                 "drivers": drivers},
    }


# --------------------------------------------------------------------------- demo


def _print(event: dict) -> None:
    from explain import explain

    where = event["station"] or f"zone {event['zone']}"
    print(f"[{event['agent']}] {event['type']} at {where}: {event['severity']} ({event['confidence']:.0%})")
    for e in event["evidence"]:
        print(f"    - {e}")
    for d in event["data"].get("drivers", []):
        name = d.get("feature") or f'"{d["word"]}"'
        print(f"    driver {name:28s} {d['effect'] * 100:+.0f} points")
    print(f"    -> {event['suggested_action']}")
    out = explain(event)
    print(f"    explanation ({out['mode']}): {out['text']}\n")


if __name__ == "__main__":
    print("Scenario: product change on the Model Y, Friday night shift during the ramp to 7,500/week\n")

    base = {"shift": "night", "day_of_week": "Friday", "crew_overtime_h_last_week": 6.0, "zone_floaters": 2}
    tomorrow = [
        {**base, "station": "S18", "zone": "C", "safety_critical": 1, "operator_level": 1, "qualified_backups": 1,
         "zone_trainees": 2, "crew_trainees": 5, "zone_absence_rate_4w": 0.17},
        {**base, "station": "S12", "zone": "B", "safety_critical": 0, "operator_level": 2, "qualified_backups": 0,
         "zone_trainees": 1, "crew_trainees": 5, "zone_absence_rate_4w": 0.14},
        {**base, "station": "S03", "zone": "A", "safety_critical": 0, "operator_level": 3, "qualified_backups": 3,
         "zone_trainees": 0, "crew_trainees": 5, "zone_absence_rate_4w": 0.10},
    ]
    for ev in staffing_risk(tomorrow):
        _print(ev)

    _print(assembly_risk({"department": "sewing", "day": "Saturday", "team": 3, "targeted_productivity": 0.8,
                          "smv": 30.0, "wip": 400, "over_time": 7000, "no_of_style_change": 1,
                          "no_of_workers": 38}, zone="C"))

    _print(safety_triage("While lifting the battery pack into position the hoist chain slipped and the pack "
                         "dropped a few centimetres, the operator pulled his hand away just in time.",
                         zone="C", station="S18"))
