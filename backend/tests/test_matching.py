from datetime import datetime

from shiftloop.matching import cover_candidates, maintenance_candidates, warden_donors
from shiftloop.models import StaffingChange
from shiftloop.state import FactoryState

T0 = datetime(2026, 10, 1, 6, 0)


def _absent(state, station):
    w = state.station_occupant(station)
    state.apply_staffing(StaffingChange(time=T0, worker=w.id, change="absent"))
    return w


def test_cover_candidates_are_qualified_and_present():
    state = FactoryState.create()
    _absent(state, "S12")
    cands = cover_candidates(state, "S12")
    assert cands
    for c in cands:
        w = state.workers[c.worker_id]
        assert w.status == "present"
        assert w.level("S12") >= 2


def test_free_floater_in_same_zone_ranks_first():
    state = FactoryState.create()
    _absent(state, "S12")
    best = state.workers[cover_candidates(state, "S12")[0].worker_id]
    assert best.role == "floater" and best.zone == "B" and best.station is None


def test_workers_assigned_elsewhere_are_excluded_unless_requested():
    state = FactoryState.create()
    _absent(state, "S12")
    assert all(state.workers[c.worker_id].station is None for c in cover_candidates(state, "S12"))
    with_assigned = cover_candidates(state, "S12", include_assigned=True, limit=50)
    assert any(state.workers[c.worker_id].station is not None for c in with_assigned)


def test_candidates_who_would_exceed_ten_hours_are_excluded():
    state = FactoryState.create()
    _absent(state, "S12")
    best_id = cover_candidates(state, "S12")[0].worker_id
    state.workers[best_id].hours_worked = 9.9
    assert best_id not in [c.worker_id for c in cover_candidates(state, "S12", needed_hours=1.0)]


def test_busy_workers_are_excluded():
    state = FactoryState.create()
    _absent(state, "S12")
    best_id = cover_candidates(state, "S12")[0].worker_id
    state.workers[best_id].busy_with = "inc_0001"
    assert best_id not in [c.worker_id for c in cover_candidates(state, "S12")]


def test_candidate_has_human_readable_reason():
    state = FactoryState.create()
    _absent(state, "S12")
    c = cover_candidates(state, "S12")[0]
    assert "S12" in c.reason and ("qualified" in c.reason or "trainer" in c.reason)


def test_maintenance_candidates_prefer_closest_free_technician():
    state = FactoryState.create()
    techs = maintenance_candidates(state, "B")
    assert state.workers[techs[0].worker_id].zone == "B"
    state.workers[techs[0].worker_id].busy_with = "esc_0001"
    nxt = maintenance_candidates(state, "B")[0]
    assert state.workers[nxt.worker_id].zone in {"A", "C"}


def test_warden_donors_come_from_zones_with_spare_wardens():
    state = FactoryState.create()
    donors = warden_donors(state, "B")
    assert donors and all(state.workers[d.worker_id].zone == "A" for d in donors)
