from shiftloop.actions import decide
from shiftloop.central.engine import CentralIntelligence
from shiftloop.kpis import kpis
from shiftloop.models import Event, Severity, StaffingChange
from shiftloop.oversight import oversight_report
from shiftloop.state import FactoryState
from shiftloop.whatif import what_if


def ev(state, agent, type_, zone, station=None, severity="high", data=None, key=None):
    return Event(id=state.next_id("evt"), agent=agent, time=state.now, zone=zone, station=station, type=type_,
                 severity=Severity(severity), key=key or f"{agent}:{type_}:{station or zone}", data=data or {},
                 evidence=["e"])


def test_oversight_reports_decisions_and_override_rate():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "slowdown", "A", "S01", "medium"),
                           ev(state, "assembly", "slowdown", "D", "S22", "medium")])
    a, b = central.open_incidents(state)
    decide(state, central, a.id, "accept")
    decide(state, central, b.id, "dismiss", reason="known issue")
    rep = oversight_report(state, central)
    assert rep["decisions"]["total"] == 2
    assert rep["decisions"]["accept"] == 1 and rep["decisions"]["dismiss"] == 1
    assert rep["override_rate"] == 0.5
    assert rep["human_decided_pct"] == 100
    assert rep["agents"]["assembly"]["events"] == 2
    assert rep["log"][0]["reason"] in ("", "known issue")


def test_oversight_lists_data_use_without_individual_performance():
    rep = oversight_report(FactoryState.create(), CentralIntelligence())
    assert set(rep["data_use"]) == {"staffing", "assembly", "safety", "central"}
    assert rep["works_council"]["individual_performance_scoring"] is False
    assert rep["works_council"]["all_decisions_by_humans"] is True


def test_oversight_counts_expert_queue():
    state, central = FactoryState.create(), CentralIntelligence()
    central.ingest(state, [ev(state, "assembly", "inspection_unsure", "B", "S09", "low", key="assembly:unsure:1")])
    assert oversight_report(state, central)["expert_queue"] == 1


def test_what_if_moving_a_warden_warns_about_coverage():
    state = FactoryState.create()
    warden_c = state.fire_wardens("C")[0]  # the only warden in zone C, runs a station
    result = what_if(state, warden_c.id, "S01")
    assert not result["ok"]
    assert any("Zone C would have no fire warden" in w for w in result["warnings"])
    assert any(warden_c.station in w for w in result["warnings"])  # leaves own station open
    assert state.workers[warden_c.id].station == warden_c.station  # real state untouched


def test_what_if_to_unqualified_station_warns():
    state = FactoryState.create()
    floater = next(w for w in state.workers.values() if w.role == "floater" and w.home_zone == "A")
    target = next(s for s in state.layout.stations if floater.qualifications.get(s, 0) == 0)
    result = what_if(state, floater.id, target)
    assert any("not qualified" in w for w in result["warnings"])


def test_what_if_good_move_is_ok():
    state = FactoryState.create()
    absent = state.station_occupant("S12")
    state.apply_staffing(StaffingChange(time=state.now, worker=absent.id, change="absent"))
    floater = next(w for w in state.workers.values() if w.role == "floater" and w.qualifications.get("S12", 0) >= 2)
    result = what_if(state, floater.id, "S12")
    assert result["ok"], result["warnings"]
    assert any("S12 covered" in b for b in result["benefits"])


def test_kpis_compare_output_to_plan():
    state = FactoryState.create()
    state.cars_built = 50
    state.now = state.now.replace(hour=7)
    k = kpis(state, CentralIntelligence())
    assert k["plan"] == 60 and k["cars_built"] == 50 and k["output_pct"] == 83
    assert "downtime_min" in k and "open_safety" in k
