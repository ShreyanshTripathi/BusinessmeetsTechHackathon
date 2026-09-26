from datetime import datetime, timedelta

from shiftloop.bus import EventBus
from shiftloop.models import StaffingChange
from shiftloop.state import FactoryState

T0 = datetime(2026, 10, 1, 6, 0)


def test_new_state_starts_at_shift_start_with_everyone_present():
    state = FactoryState.create()
    assert state.now == T0
    assert state.signals == 0
    assert all(w.status == "present" for w in state.workers.values())


def test_station_occupant_and_zone_headcount():
    state = FactoryState.create()
    occupant = state.station_occupant("S12")
    assert occupant is not None and occupant.station == "S12"
    # 6 operators + 2 floaters in zone B, plus one maintenance tech based there
    assert state.zone_headcount("B") == 9


def test_absence_clears_station_and_removes_from_headcount():
    state = FactoryState.create()
    worker = state.station_occupant("S12")
    state.apply_staffing(StaffingChange(time=T0, worker=worker.id, change="absent"))
    assert state.workers[worker.id].status == "absent"
    assert state.workers[worker.id].station is None
    assert state.station_occupant("S12") is None
    assert state.zone_headcount("B") == 8


def test_assign_moves_worker_and_displaces_previous_occupant():
    state = FactoryState.create()
    floater = next(w for w in state.workers.values() if w.role == "floater" and w.home_zone == "A")
    previous = state.station_occupant("S03")
    displaced = state.assign(floater.id, "S03")
    assert displaced == previous.id
    assert state.station_occupant("S03").id == floater.id
    assert state.workers[previous.id].station is None
    assert state.workers[floater.id].zone == "A"


def test_assign_across_zones_updates_zone():
    state = FactoryState.create()
    warden_a = next(w for w in state.workers.values() if w.fire_warden and w.zone == "A")
    state.move_zone(warden_a.id, "B")
    assert state.workers[warden_a.id].zone == "B"
    assert state.workers[warden_a.id].station is None
    assert len(state.fire_wardens("B")) == 2


def test_advance_clock_adds_hours_to_present_workers_only():
    state = FactoryState.create()
    absent = state.station_occupant("S01")
    state.apply_staffing(StaffingChange(time=T0, worker=absent.id, change="absent"))
    state.advance(timedelta(minutes=90))
    assert state.now == T0 + timedelta(minutes=90)
    assert state.workers[absent.id].hours_worked == 0
    present = state.station_occupant("S02")
    assert abs(present.hours_worked - 1.5) < 1e-9


def test_ids_are_unique_and_prefixed():
    state = FactoryState.create()
    assert state.next_id("inc") == "inc_0001"
    assert state.next_id("inc") == "inc_0002"
    assert state.next_id("evt") == "evt_0001"


def test_bus_delivers_messages_to_subscribers_in_order():
    bus = EventBus()
    got = []
    bus.subscribe("reading", lambda m: got.append(("a", m)))
    bus.subscribe("reading", lambda m: got.append(("b", m)))
    bus.subscribe("other", lambda m: got.append(("x", m)))
    bus.publish("reading", 1)
    assert got == [("a", 1), ("b", 1)]


def test_bus_handler_can_publish_follow_up_messages():
    bus = EventBus()
    got = []
    bus.subscribe("reading", lambda m: bus.publish("event", m * 10))
    bus.subscribe("event", got.append)
    bus.publish("reading", 2)
    assert got == [20]
