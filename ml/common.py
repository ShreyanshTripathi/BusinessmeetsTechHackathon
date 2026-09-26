"""Shared helpers: paths and model cards.

Every trained model is saved with a model card (JSON) next to it: what it predicts, what data it saw,
how well it did on held-out data, and what it must not be used for. The oversight view can show these.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ML_DIR = Path(__file__).parent
DATA_DIR = ML_DIR / "data"
MODEL_DIR = ML_DIR / "models"

# Same layout as backend/shiftloop/factory.py: 4 zones, 24 stations, S15 and S18 safety critical
ZONES = ["A", "B", "C", "D"]
STATIONS = [f"S{i:02d}" for i in range(1, 25)]
SAFETY_CRITICAL = {"S15", "S18"}


def zone_of(station_id: str) -> str:
    return ZONES[(int(station_id[1:]) - 1) // 6]


def save_card(name: str, card: dict) -> Path:
    MODEL_DIR.mkdir(exist_ok=True)
    card = {"model": name, "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **card}
    path = MODEL_DIR / f"{name}.card.json"
    path.write_text(json.dumps(card, indent=2, ensure_ascii=False))
    return path
