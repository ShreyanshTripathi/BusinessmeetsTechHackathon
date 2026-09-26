"""Vision service: runs a detector per camera purpose and feeds detections into the plant.

Detector slots:
  quality -> the team's visual QC model (SHIFTLOOP_QC_MODEL="module:function", returns (label, confidence, detail))
  fire    -> pretrained YOLO fire/smoke model (SHIFTLOOP_FIRE_MODEL=path/to/weights.pt)
  ppe     -> pretrained YOLO PPE model (SHIFTLOOP_PPE_MODEL=path/to/weights.pt)
  exit    -> any detector that reports "exit_blocked"
"""
from __future__ import annotations

import importlib
import io
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Protocol

from PIL import Image

from ..models import VisionDetection

if TYPE_CHECKING:
    from ..plant import Plant

LABELS = {"ok", "defect", "fire", "smoke", "ppe_missing", "exit_blocked"}

# class names commonly used by public fire/smoke and PPE datasets -> our labels
FIRE_LABELS = {"fire": "fire", "flame": "fire", "smoke": "smoke"}
PPE_LABELS = {"no-helmet": "ppe_missing", "no_helmet": "ppe_missing", "no-vest": "ppe_missing",
              "no_vest": "ppe_missing", "no-gloves": "ppe_missing", "no-hardhat": "ppe_missing",
              "no-safety vest": "ppe_missing"}


@dataclass
class Detection:
    label: str
    confidence: float
    detail: str = ""


class Detector(Protocol):
    def detect(self, image: Image.Image) -> list[Detection]: ...


class YoloDetector:
    """Wraps an Ultralytics YOLO model; keeps only classes in `label_map`."""

    def __init__(self, model=None, weights: str | None = None, label_map: dict[str, str] | None = None,
                 min_confidence: float = 0.4) -> None:
        if model is None:
            from ultralytics import YOLO  # optional dependency: `uv sync --extra vision`
            model = YOLO(weights)
        self.model = model
        self.label_map = label_map or {}
        self.min_confidence = min_confidence

    def detect(self, image: Image.Image) -> list[Detection]:
        out = []
        for result in self.model(image, verbose=False):
            for box in result.boxes:
                name = result.names[int(box.cls[0])].lower()
                conf = float(box.conf[0])
                if name in self.label_map and conf >= self.min_confidence:
                    out.append(Detection(self.label_map[name], conf, name))
        return out


class CallableDetector:
    """Adapter for the team's own model: fn(image) -> (label, confidence, detail) or a list of those."""

    def __init__(self, fn: Callable) -> None:
        self.fn = fn

    def detect(self, image: Image.Image) -> list[Detection]:
        result = self.fn(image)
        rows = result if isinstance(result, list) else [result]
        return [Detection(*row) for row in rows if row]


def load_callable_detector(path: str) -> CallableDetector:
    module, _, attr = path.partition(":")
    return CallableDetector(getattr(importlib.import_module(module), attr))


def detectors_from_env() -> dict[str, Detector]:
    dets: dict[str, Detector] = {}
    if qc := os.getenv("SHIFTLOOP_QC_MODEL"):
        dets["quality"] = load_callable_detector(qc)
    if fire := os.getenv("SHIFTLOOP_FIRE_MODEL"):
        dets["fire"] = YoloDetector(weights=fire, label_map=FIRE_LABELS)
    if ppe := os.getenv("SHIFTLOOP_PPE_MODEL"):
        dets["ppe"] = YoloDetector(weights=ppe, label_map=PPE_LABELS)
    return dets


class VisionService:
    def __init__(self, plant: "Plant", detectors: dict[str, Detector]) -> None:
        self.plant = plant
        self.detectors = detectors

    def status(self) -> dict[str, str]:
        return {p: ("loaded" if p in self.detectors else "no model loaded") for p in ("quality", "fire", "ppe", "exit")}

    def process(self, camera_id: str, image_bytes: bytes, image_ref: str | None = None) -> list[VisionDetection]:
        cam = self.plant.state.layout.cameras[camera_id]
        det = self.detectors.get(cam.purpose)
        if det is None:
            raise LookupError(f"no model loaded for {cam.purpose} cameras")
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        found = [d for d in det.detect(image) if d.label in LABELS and d.label != "ok"]
        now = self.plant.state.now
        readings = [VisionDetection(time=now, camera=camera_id, zone=cam.zone, station=cam.station, label=d.label,
                                    confidence=round(d.confidence, 3), detail=d.detail, image_ref=image_ref)
                    for d in found] or [VisionDetection(time=now, camera=camera_id, zone=cam.zone,
                                                        station=cam.station, label="ok", confidence=1.0,
                                                        image_ref=image_ref)]
        for r in readings:
            self.plant.ingest(r)
        return readings
