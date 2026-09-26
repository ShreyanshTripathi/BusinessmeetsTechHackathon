from shiftloop.factory import build_layout, build_roster, ZONE_ORDER


def test_layout_has_four_zones_in_line_order():
    layout = build_layout()
    assert [z.id for z in layout.zones] == ["A", "B", "C", "D"]
    assert ZONE_ORDER == ["A", "B", "C", "D"]


def test_layout_has_24_stations_six_per_zone():
    layout = build_layout()
    assert len(layout.stations) == 24
    for zone in "ABCD":
        assert len([s for s in layout.stations.values() if s.zone == zone]) == 6
    assert layout.stations["S09"].zone == "B"
    assert layout.stations["S12"].zone == "B"
    assert layout.stations["S18"].zone == "C"


def test_battery_station_is_safety_critical_and_has_temperature_sensor():
    layout = build_layout()
    assert layout.stations["S18"].safety_critical
    kinds = {s.kind for s in layout.sensors.values() if s.station == "S18"}
    assert "battery_temp" in kinds


def test_every_zone_has_exit_smoke_heat_gas_sensors_and_fire_camera():
    layout = build_layout()
    for zone in layout.zones:
        assert zone.exits, zone.id
        kinds = {s.kind for s in layout.sensors.values() if s.zone == zone.id}
        assert {"smoke", "heat", "gas"} <= kinds
        purposes = {c.purpose for c in layout.cameras.values() if c.zone == zone.id}
        assert {"fire", "ppe", "exit"} <= purposes


def test_quality_cameras_cover_every_station():
    layout = build_layout()
    covered = {c.station for c in layout.cameras.values() if c.purpose == "quality"}
    assert covered == set(layout.stations)


def test_roster_is_deterministic_for_a_seed():
    a = build_roster(build_layout(), seed=7)
    b = build_roster(build_layout(), seed=7)
    assert [w.model_dump() for w in a.values()] == [w.model_dump() for w in b.values()]


def test_roster_assigns_one_qualified_operator_per_station():
    layout = build_layout()
    roster = build_roster(layout)
    for station_id in layout.stations:
        assigned = [w for w in roster.values() if w.station == station_id]
        assert len(assigned) == 1, station_id
        assert assigned[0].qualifications[station_id] >= 2


def test_every_station_has_at_least_three_qualified_workers():
    layout = build_layout()
    roster = build_roster(layout)
    for station_id in layout.stations:
        qualified = [w for w in roster.values() if w.qualifications.get(station_id, 0) >= 2]
        assert len(qualified) >= 3, station_id


def test_roster_has_floaters_maintenance_and_safety_roles():
    roster = build_roster(build_layout())
    roles = [w.role for w in roster.values()]
    assert roles.count("floater") == 8
    assert roles.count("maintenance") == 3
    # zone A has two fire wardens, every other zone exactly one (the demo relies on this)
    for zone, expected in {"A": 2, "B": 1, "C": 1, "D": 1}.items():
        wardens = [w for w in roster.values() if w.fire_warden and w.zone == zone]
        assert len(wardens) == expected, zone
    for zone in "ABCD":
        assert any(w.first_aider and w.zone == zone for w in roster.values()), zone


def test_everyone_starts_present_with_zero_hours():
    roster = build_roster(build_layout())
    assert all(w.status == "present" and w.hours_worked == 0 for w in roster.values())
