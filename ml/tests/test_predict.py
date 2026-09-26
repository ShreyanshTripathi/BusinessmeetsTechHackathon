"""Predictions come back as backend events with their drivers attached."""
import pytest

import predict
import train_assembly
import train_safety
import train_staffing

BASE = {"shift": "night", "day_of_week": "Friday", "crew_overtime_h_last_week": 6.0, "zone_floaters": 2}
RISKY = {**BASE, "station": "S18", "zone": "C", "safety_critical": 1, "operator_level": 1, "qualified_backups": 0,
         "zone_trainees": 3, "crew_trainees": 7, "zone_absence_rate_4w": 0.2}
SAFE = {**BASE, "station": "S03", "zone": "A", "safety_critical": 0, "operator_level": 3, "qualified_backups": 3,
        "zone_trainees": 0, "crew_trainees": 2, "zone_absence_rate_4w": 0.08}
TEAM_DAY = {"department": "sewing", "day": "Saturday", "team": 3, "targeted_productivity": 0.8, "smv": 30.0,
            "wip": 400, "over_time": 7000, "no_of_style_change": 1, "no_of_workers": 38}
REPORT = ("While lifting the battery pack into position the hoist chain slipped and the pack dropped a few "
          "centimetres, the operator pulled his hand away just in time.")


@pytest.fixture(scope="module", autouse=True)
def models():
    for module in (train_staffing, train_assembly, train_safety):
        module.main()
    predict._load.cache_clear()
    predict._card.cache_clear()


def test_staffing_ranks_the_risky_station_first_with_drivers():
    events = predict.staffing_risk([SAFE, RISKY], top=2, min_risk=0.0)
    assert events[0]["station"] == "S18"
    drivers = events[0]["data"]["drivers"]
    assert drivers and all(d["feature"] in train_staffing.FEATURES for d in drivers)
    assert events[0]["agent"] == "staffing" and events[0]["severity"] in {"medium", "high"}


def test_assembly_event_has_drivers():
    ev = predict.assembly_risk(TEAM_DAY, zone="C")
    assert ev["agent"] == "assembly" and 0 <= ev["confidence"] <= 1
    assert all(d["feature"] in train_assembly.FEATURES for d in ev["data"]["drivers"])


def test_safety_event_has_words_from_the_report_as_drivers():
    ev = predict.safety_triage(REPORT, zone="C", station="S18")
    assert ev["agent"] == "safety" and ev["type"] in {"near_miss_rated", "near_miss_unsure"}
    assert all(d["word"] in REPORT.lower() for d in ev["data"]["drivers"])
