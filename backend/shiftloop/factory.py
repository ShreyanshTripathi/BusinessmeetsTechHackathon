"""Synthetic model of one general-assembly section: layout and shift roster.

In production these come from the plant's layout data, HR system and qualification matrix.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from .models import Camera, Layout, Sensor, Station, Worker, Zone

ZONE_ORDER = ["A", "B", "C", "D"]
SHIFT_DATE = date(2026, 10, 1)

STATION_NAMES = [
    # zone A: interior
    "Wiring harness", "Headliner", "Instrument panel", "Carpet & insulation", "Pedal box", "HVAC module",
    # zone B: chassis prep
    "Brake lines", "Fuel-free cooling lines", "Front subframe", "Rear subframe", "Suspension bolts", "Underbody torque",
    # zone C: powertrain
    "Drive unit (rear)", "Drive unit (front)", "HV cabling", "Coolant fill", "Battery lift prep", "Battery marriage",
    # zone D: final trim
    "Glass install", "Seats", "Doors on", "Wheels & tyres", "Fluids & flash", "Final inspection",
]

NAMES = [
    "Lena Schmidt", "Jan Kowalski", "Ahmed Yilmaz", "Anna Nowak", "Lukas Weber", "Marta Wiśniewska",
    "Felix Braun", "Olga Petrenko", "Tobias Klein", "Zofia Lewandowska", "Mehmet Demir", "Sara Hoffmann",
    "Piotr Zieliński", "Julia Wagner", "Karim Haddad", "Katarzyna Wójcik", "Jonas Becker", "Elif Kaya",
    "Tomasz Kamiński", "Laura Fischer", "Nikolai Ivanov", "Hanna Schulz", "Omar Saleh", "Agnieszka Dąbrowska",
    "Paul Richter", "Aylin Öztürk", "Michał Szymański", "Clara Neumann", "Yusuf Aydın", "Ewa Kozłowska",
    "David Koch", "Ines Wolf", "Bartosz Mazur", "Mira Schröder", "Ali Hassan", "Natalia Krawczyk",
    "Moritz Lange", "Leyla Aksoy", "Kacper Jankowski", "Sophie Krüger",
]

POLISH_NAMES = {"Jan Kowalski", "Anna Nowak", "Marta Wiśniewska", "Zofia Lewandowska", "Piotr Zieliński",
                "Katarzyna Wójcik", "Tomasz Kamiński", "Agnieszka Dąbrowska", "Michał Szymański", "Ewa Kozłowska",
                "Bartosz Mazur", "Natalia Krawczyk", "Kacper Jankowski"}

# Deterministic safety roles so the demo scenario is reproducible
FIRE_WARDEN_STATIONS = {"S02", "S04", "S15", "S21"}  # zone B's warden is a floater (see below)
FIRST_AIDER_STATIONS = {"S03", "S10", "S14", "S22"}


def station_ids() -> list[str]:
    return [f"S{i:02d}" for i in range(1, 25)]


def zone_of(station_id: str) -> str:
    return ZONE_ORDER[(int(station_id[1:]) - 1) // 6]


def build_layout() -> Layout:
    zones = [
        Zone(id=z, name=f"Zone {z}", order=i, exits=[f"EXIT-{z}1", f"EXIT-{z}2"], assembly_point=f"AP-{z}")
        for i, z in enumerate(ZONE_ORDER)
    ]
    stations = {
        sid: Station(id=sid, zone=zone_of(sid), name=STATION_NAMES[i], safety_critical=sid in {"S15", "S18"})
        for i, sid in enumerate(station_ids())
    }
    sensors: dict[str, Sensor] = {}
    cameras: dict[str, Camera] = {}
    for z in ZONE_ORDER:
        sensors[f"SMK-{z}"] = Sensor(id=f"SMK-{z}", zone=z, kind="smoke", unit="%obs/m", warn=2.0, crit=4.0)
        sensors[f"HEAT-{z}"] = Sensor(id=f"HEAT-{z}", zone=z, kind="heat", unit="°C", warn=40.0, crit=57.0)
        sensors[f"GAS-{z}"] = Sensor(id=f"GAS-{z}", zone=z, kind="gas", unit="ppm CO", warn=30.0, crit=100.0)
        cameras[f"CAM-FIRE-{z}"] = Camera(id=f"CAM-FIRE-{z}", zone=z, purpose="fire")
        cameras[f"CAM-PPE-{z}"] = Camera(id=f"CAM-PPE-{z}", zone=z, purpose="ppe")
        cameras[f"CAM-EXIT-{z}"] = Camera(id=f"CAM-EXIT-{z}", zone=z, purpose="exit")
    sensors["BT-S18"] = Sensor(id="BT-S18", zone="C", station="S18", kind="battery_temp", unit="°C", warn=45.0, crit=60.0)
    for sid, st in stations.items():
        cameras[f"CAM-QC-{sid}"] = Camera(id=f"CAM-QC-{sid}", zone=st.zone, station=sid, purpose="quality")
    return Layout(zones=zones, stations=stations, sensors=sensors, cameras=cameras)


def _languages(name: str) -> list[str]:
    return ["pl", "en"] if name in POLISH_NAMES else ["de", "en"]


def build_roster(layout: Layout, seed: int = 42) -> dict[str, Worker]:
    rng = random.Random(seed)
    names = iter(NAMES)
    workers: dict[str, Worker] = {}
    far = SHIFT_DATE + timedelta(days=365)

    def add(**kw) -> Worker:
        wid = f"W{len(workers) + 1:03d}"
        name = next(names)
        w = Worker(id=wid, name=name, languages=_languages(name), **kw)
        workers[wid] = w
        return w

    sids = list(layout.stations)
    for sid in sids:
        z = zone_of(sid)
        quals = {sid: rng.choice([2, 2, 3])}
        zone_peers = [s for s in sids if zone_of(s) == z and s != sid]
        for other in rng.sample(zone_peers, 2):
            quals[other] = rng.choice([1, 2, 2, 3])
        add(role="operator", home_zone=z, zone=z, station=sid, qualifications=quals,
            qual_expiry={s: far for s in quals},
            fire_warden=sid in FIRE_WARDEN_STATIONS, first_aider=sid in FIRST_AIDER_STATIONS)

    for z in ZONE_ORDER:
        zone_sids = [s for s in sids if zone_of(s) == z]
        for _ in range(2):
            quals = {s: rng.choice([2, 3]) for s in rng.sample(zone_sids, 4)}
            add(role="floater", home_zone=z, zone=z, qualifications=quals, qual_expiry={s: far for s in quals})

    for z in ["B", "C", "A"]:
        add(role="maintenance", home_zone=z, zone=z, qualifications={})

    # Guarantee cover depth: besides its own operator, every station has three qualified people,
    # at least one of them another operator
    def qualified_others(sid: str, role: str | None = None) -> int:
        return sum(1 for w in workers.values()
                   if w.station != sid and w.qualifications.get(sid, 0) >= 2 and (role is None or w.role == role))

    for sid in sids:
        z = zone_of(sid)
        while qualified_others(sid, "operator") < 1 or qualified_others(sid) < 3:
            role = "operator" if qualified_others(sid, "operator") < 1 else None
            pool = [w for w in workers.values()
                    if w.role in ("operator", "floater") and (role is None or w.role == role)
                    and w.home_zone == z and w.station != sid and w.qualifications.get(sid, 0) < 2]
            w = rng.choice(pool)
            w.qualifications[sid] = 2
            w.qual_expiry[sid] = far

    # Demo guarantees: a zone-B floater can cover S12; one qualification expires during the week
    floater_b, floater_b2 = [w for w in workers.values() if w.role == "floater" and w.home_zone == "B"]
    floater_b.qualifications["S12"] = 3
    floater_b.qual_expiry["S12"] = far
    floater_b2.fire_warden = True
    op_s20 = next(w for w in workers.values() if w.station == "S20")
    op_s20.qual_expiry["S20"] = SHIFT_DATE + timedelta(days=4)
    return workers
