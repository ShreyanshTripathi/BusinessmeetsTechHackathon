"""Bridge to the random-forest models in ml/: live factory state in, backend-style events out.

The models are trained and documented in ml/ (see ml/README.md and the model cards). This module:
  * builds each model's inputs from the live FactoryState,
  * calls ml/predict.py and attaches a plain-language explanation (ml/explain.py template; Claude on request),
  * degrades to "unavailable" if the models or their dependencies are missing, so the agents run rules-only.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
from pathlib import Path

from .factory import ZONE_ORDER
from .state import FactoryState

DEFAULT_ML_DIR = Path(__file__).resolve().parents[2] / "ml"
MODELS = ("staffing", "assembly", "safety")

# Inputs the plant would take from HR and planning systems; fixed here for the MVP (synthetic)
ZONE_ABSENCE_HISTORY_4W = {"A": 0.11, "B": 0.12, "C": 0.15, "D": 0.12}
CREW_OVERTIME_H_LAST_WEEK = 4.0
STAFFING_TOP, STAFFING_MIN_RISK = 3, 0.6
ASSEMBLY_MIN_RISK = 0.5

# assembly model columns shown to supervisors under plain names; team/department are mapping artefacts
ASSEMBLY_LABELS = {"smv": "work_content", "over_time": "planned_overtime", "day": "day",
                   "targeted_productivity": "target", "no_of_style_change": "product_changes"}
BLOCKED = ("stopped", "starved", "halted")


def shift_name(hour: int) -> str:
    return "early" if 6 <= hour < 14 else "late" if 14 <= hour < 22 else "night"


def staffing_rows(state: FactoryState) -> list[dict]:
    """One row per staffed station, with the staffing model's features (see ml/train_staffing.py)."""
    today = state.now.date()
    occupants = {sid: state.station_occupant(sid) for sid in state.layout.stations}
    levels = {sid: w.level(sid, on=today) for sid, w in occupants.items() if w is not None}
    zone_trainees = {z: sum(1 for sid, lv in levels.items() if state.layout.stations[sid].zone == z and lv < 2)
                     for z in ZONE_ORDER}
    floaters = [w for w in state.present() if w.role == "floater"]
    rows = []
    for sid, level in levels.items():
        st = state.layout.stations[sid]
        rows.append({
            "station": sid, "zone": st.zone, "shift": shift_name(state.now.hour),
            "day_of_week": state.now.strftime("%A"), "safety_critical": int(st.safety_critical),
            "operator_level": level,
            "qualified_backups": sum(1 for f in floaters if f.station is None and f.level(sid, on=today) >= 2),
            "zone_trainees": zone_trainees[st.zone], "crew_trainees": sum(zone_trainees.values()),
            "zone_floaters": sum(1 for f in floaters if f.home_zone == st.zone),
            "zone_absence_rate_4w": ZONE_ABSENCE_HISTORY_4W[st.zone],
            "crew_overtime_h_last_week": CREW_OVERTIME_H_LAST_WEEK,
        })
    return rows


def assembly_rows(state: FactoryState, reference: dict) -> list[dict]:
    """Per zone: the assembly model's features, scaled from the live section onto the model's units.

    The model was trained on public garment-line data, so headcount and buffer are expressed relative to
    that data's typical team: a zone at full strength gets the typical team size, a blocked flow a low buffer.
    """
    rows = []
    for i, z in enumerate(ZONE_ORDER):
        planned = sum(1 for w in state.workers.values() if w.home_zone == z and w.role != "maintenance")
        present = sum(1 for w in state.present() if w.zone == z and w.role != "maintenance")
        upstream = ZONE_ORDER[: i + 1]
        blocked = [sid for sid, s in state.layout.stations.items() if s.zone in upstream and s.status in BLOCKED]
        features = {
            **{k: reference[k] for k in ("targeted_productivity", "smv", "over_time", "no_of_style_change")},
            "department": "sewing", "day": state.now.strftime("%A"), "team": i + 1,
            "no_of_workers": round(reference["no_of_workers"] * present / max(planned, 1)),
            "wip": round(reference["wip"] * (0.3 if blocked else 1.0)),
        }
        rows.append({"zone": z, "features": features, "present": present, "planned": planned, "blocked": blocked})
    return rows


class MLBridge:
    def __init__(self, predict=None, explain=None, status: dict | None = None, ml_dir: Path | None = None):
        self.predict, self.explain_mod = predict, explain
        self.status = status or {m: "unavailable" for m in MODELS}
        self.ml_dir = ml_dir
        self._explained: dict[tuple[str, str, str], dict] = {}

    @property
    def available(self) -> bool:
        return all(v == "loaded" for v in self.status.values())

    @classmethod
    def load(cls, ml_dir: Path | None = None) -> "MLBridge":
        ml_dir = Path(ml_dir or os.getenv("SHIFTLOOP_ML_DIR") or DEFAULT_ML_DIR)
        needed = [ml_dir / "predict.py", ml_dir / "explain.py"] + [ml_dir / "models" / f"{m}_model.joblib" for m in MODELS]
        if not all(p.exists() for p in needed):
            return cls(ml_dir=ml_dir)
        try:
            if str(ml_dir) not in sys.path:
                sys.path.insert(0, str(ml_dir))
            predict = importlib.import_module("predict")
            explain = importlib.import_module("explain")
            for m in MODELS:
                forest = predict._load(f"{m}_model")[-1]
                forest.set_params(n_jobs=1)  # small batches: threads cost more than they save
        except Exception:  # missing scikit-learn/pandas, incompatible pickle, ...
            return cls(ml_dir=ml_dir)
        return cls(predict, explain, {m: "loaded" for m in MODELS}, ml_dir)

    # ------------------------------------------------------------------ predictions

    def _with_explanation(self, event: dict) -> dict:
        event["data"]["explanation"] = self.explain_mod.template(event)
        return event

    def staffing_forecast(self, state: FactoryState) -> list[dict]:
        if not self.available:
            return []
        rows = staffing_rows(state)
        if not rows:
            return []
        events = self.predict.staffing_risk(rows, top=STAFFING_TOP, min_risk=STAFFING_MIN_RISK)
        for ev in events:
            ev["type"] = "cover_risk"
            ev["evidence"][0] = ev["evidence"][0].replace("no qualified cover on the", "losing qualified cover this")
            ev["suggested_action"] = "Line up a qualified backup now, before the gap happens"
        return [self._with_explanation(ev) for ev in events]

    def assembly_forecast(self, state: FactoryState) -> list[dict]:
        if not self.available:
            return []
        reference = self.predict._card("assembly_model")["reference_values"]
        out = []
        for row in assembly_rows(state, reference):
            ev = self.predict.assembly_risk(row["features"], zone=row["zone"])
            risk = ev["data"]["risk"]
            if risk < ASSEMBLY_MIN_RISK:
                continue
            z = row["zone"]
            flow = f"; flow blocked at {', '.join(row['blocked'])}" if row["blocked"] else ""
            ev["evidence"] = [f"{risk:.0%} risk that zone {z} misses today's output target",
                              f"{row['present']} of {row['planned']} people present in zone {z}{flow}",
                              "model trained on public garment-line data (stand-in until plant MES data)"]
            ev["suggested_action"] = f"Check staffing and buffer in zone {z} before the next break"
            ev["data"]["drivers"] = self._assembly_drivers(ev["data"]["drivers"], row)
            out.append(self._with_explanation(ev))
        return out

    @staticmethod
    def _assembly_drivers(drivers: list[dict], row: dict) -> list[dict]:
        out = []
        for d in drivers:
            f = d["feature"]
            if f == "no_of_workers":
                out.append({**d, "feature": "people_present", "value": row["present"], "typical": row["planned"]})
            elif f == "wip":
                out.append({**d, "feature": "buffer", "value": "low" if row["blocked"] else "normal",
                            "typical": "normal"})
            elif f in ASSEMBLY_LABELS:
                out.append({**d, "feature": ASSEMBLY_LABELS[f]})
        return out

    def safety_triage(self, text: str, zone: str, station: str | None) -> dict:
        if not self.available:
            raise LookupError("safety model not available")
        return self._with_explanation(self.predict.safety_triage(text, zone=zone, station=station))

    # ------------------------------------------------------------------ explanations and cards

    def explain(self, event_id: str, event: dict, client, language: str = "en") -> dict:
        key = (event_id, "offline" if client is None else "claude", language)
        if key not in self._explained:
            self._explained[key] = self.explain_mod.explain(event, client=client, language=language)
        return self._explained[key]

    def cards(self) -> list[dict]:
        if self.ml_dir is None or not (self.ml_dir / "models").exists():
            return []
        return [json.loads(p.read_text()) for p in sorted((self.ml_dir / "models").glob("*.card.json"))]
