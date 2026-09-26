import io

import pytest
from PIL import Image

from shiftloop.plant import Plant
from shiftloop.vision.service import Detection, VisionService, YoloDetector, load_callable_detector


def png_bytes(color=(200, 200, 200)):
    buf = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(buf, format="PNG")
    return buf.getvalue()


class FakeDetector:
    def __init__(self, detections):
        self.detections = detections
        self.seen = []

    def detect(self, image):
        self.seen.append(image.size)
        return self.detections


def test_quality_camera_frame_becomes_a_reading_for_that_station():
    plant = Plant(scenario="quiet")
    det = FakeDetector([Detection("defect", 0.91, "scratch on door")])
    svc = VisionService(plant, {"quality": det})
    readings = svc.process("CAM-QC-S05", png_bytes())
    assert det.seen == [(64, 48)]
    assert len(readings) == 1 and readings[0].station == "S05" and readings[0].label == "defect"
    assert plant.state.recent_vision[-1].detail == "scratch on door"


def test_fire_camera_detection_reaches_the_safety_agent():
    plant = Plant(scenario="quiet")
    svc = VisionService(plant, {"fire": FakeDetector([Detection("fire", 0.95)])})
    svc.process("CAM-FIRE-B", png_bytes())
    types = {e.type for e in plant.state.events}
    assert "fire_confirmed" in types


def test_no_detection_reports_ok():
    plant = Plant(scenario="quiet")
    svc = VisionService(plant, {"ppe": FakeDetector([])})
    readings = svc.process("CAM-PPE-A", png_bytes())
    assert [r.label for r in readings] == ["ok"]


def test_camera_without_a_model_is_reported():
    plant = Plant(scenario="quiet")
    svc = VisionService(plant, {})
    with pytest.raises(LookupError):
        svc.process("CAM-EXIT-A", png_bytes())
    assert svc.status()["exit"] == "no model loaded"


def test_unknown_camera_raises_keyerror():
    with pytest.raises(KeyError):
        VisionService(Plant(scenario="quiet"), {}).process("CAM-NOPE", png_bytes())


def test_labels_outside_the_vocabulary_are_dropped():
    plant = Plant(scenario="quiet")
    svc = VisionService(plant, {"quality": FakeDetector([Detection("cat", 0.99)])})
    assert [r.label for r in svc.process("CAM-QC-S01", png_bytes())] == ["ok"]


def test_yolo_detector_maps_class_names_to_labels():
    class Box:
        def __init__(self, cls, conf):
            self.cls, self.conf = [cls], [conf]

    class Result:
        names = {0: "fire", 1: "smoke", 2: "person"}
        boxes = [Box(0, 0.8), Box(2, 0.9), Box(1, 0.3)]

    class FakeYolo:
        def __call__(self, image, verbose=False):
            return [Result()]

    det = YoloDetector(model=FakeYolo(), label_map={"fire": "fire", "smoke": "smoke"}, min_confidence=0.4)
    out = det.detect(Image.new("RGB", (10, 10)))
    assert [(d.label, round(d.confidence, 2)) for d in out] == [("fire", 0.8)]


def test_callable_detector_loads_team_model_from_module_path(tmp_path, monkeypatch):
    mod = tmp_path / "team_qc.py"
    mod.write_text("def predict(image):\n    return ('defect', 0.88, 'dent')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    det = load_callable_detector("team_qc:predict")
    assert [(d.label, d.confidence, d.detail) for d in det.detect(Image.new("RGB", (4, 4)))] == [("defect", 0.88, "dent")]
