"""Generate dummy staffing history for the Staffing model.

Simulates 26 weeks (Mon 30 Mar - Sat 26 Sep 2026) of three shift crews on the backend's assembly section:
24 stations in zones A-D, one operator per station plus 2 floaters per zone, qualification levels
0 untrained, 1 trainee, 2 qualified, 3 trainer (same scale as backend/shiftloop/models.py).

What drives the simulation, loosely based on Giga Berlin in 2026:
- the ramp from May: more new hires, who start as trainees and qualify after about 4-6 weeks
- special shifts from July: more overtime per crew
- absences around 12-15%, higher on Mondays/Fridays, on nights, with more overtime and in zone C
  (heavier work around the battery), plus short flu waves per zone
- a few people leave mid-shift

Each row is one station on one shift, with only what the supervisor knows the day before (the roster and
qualification matrix, crew overtime, zone-level absence history). The label says whether that station
ended the shift with a gap: no qualified person, or a trainee left without a qualified buddy, after the
best possible cover with the floaters who turned up.

Absence is simulated from crew- and zone-level drivers only. There is no per-person absence score, and the
model never sees who was absent.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta

import pandas as pd

from common import DATA_DIR, SAFETY_CRITICAL, STATIONS, ZONES, zone_of

SEED = 7
START = date(2026, 3, 30)
WEEKS = 26
SHIFTS = ["early", "late", "night"]


@dataclass
class Person:
    role: str  # operator | floater
    zone: str
    station: str | None
    quals: dict[str, int] = field(default_factory=dict)
    weeks_to_qualify: int = 0  # > 0 while a new hire is still a trainee at their home station


def new_operator(rng: random.Random, station: str, hire: bool) -> Person:
    zone = zone_of(station)
    peers = [s for s in STATIONS if zone_of(s) == zone and s != station]
    if hire:
        return Person("operator", zone, station, {station: 1}, weeks_to_qualify=rng.randint(4, 6))
    quals = {station: rng.choice([2, 2, 3])}
    for s in rng.sample(peers, 2):
        quals[s] = rng.choice([1, 2, 2])
    return Person("operator", zone, station, quals)


def new_floater(rng: random.Random, zone: str) -> Person:
    zone_stations = [s for s in STATIONS if zone_of(s) == zone]
    quals = {s: rng.choice([2, 3]) for s in rng.sample(zone_stations, 4)}
    other = rng.choice([s for s in STATIONS if zone_of(s) != zone])
    quals[other] = 2  # one station outside the home zone
    return Person("floater", zone, None, quals)


def build_crew(rng: random.Random) -> list[Person]:
    return [new_operator(rng, s, hire=False) for s in STATIONS] + [new_floater(rng, z) for z in ZONES for _ in range(2)]


def hire_rate(week_start: date) -> float:
    """Weekly chance that an operator seat is filled by a new hire (turnover + ramp hiring)."""
    if week_start < date(2026, 5, 1):
        return 0.01
    if week_start < date(2026, 8, 1):
        return 0.045
    return 0.06


def overtime_hours(rng: random.Random, week_start: date) -> float:
    base = 1.0 if week_start < date(2026, 7, 1) else 4.0 if week_start < date(2026, 9, 1) else 6.0
    return max(0.0, rng.gauss(base, 0.8))


def absence_prob(day: date, shift: str, zone: str, overtime: float, flu: float) -> float:
    p = 0.095
    p += 0.03 if day.weekday() in (0, 4) else 0.0
    p += 0.02 if shift == "night" else 0.0
    p += 0.015 if zone == "C" else 0.0
    p += 0.008 * overtime
    return min(0.5, p + flu)


def run_cover(free: list[Person], needs: list[tuple[str, str]], rng: random.Random) -> set[str]:
    """Assign free floaters to needs (station, kind), removing them from `free`. Returns stations left with a gap."""
    gaps = set()
    # safety-critical stations first, then empty stations before trainee buddies
    needs = sorted(needs, key=lambda n: (n[0] not in SAFETY_CRITICAL, n[1] != "empty", rng.random()))
    for station, _kind in needs:
        options = [f for f in free if f.quals.get(station, 0) >= 2]
        if not options:
            gaps.add(station)
            continue
        options.sort(key=lambda f: (f.zone != zone_of(station), -f.quals[station]))
        free.remove(options[0])
    return gaps


def simulate() -> pd.DataFrame:
    rng = random.Random(SEED)
    crews = {s: build_crew(rng) for s in SHIFTS}
    zone_history: dict[tuple[str, str], list[float]] = {(s, z): [] for s in SHIFTS for z in ZONES}
    rows = []

    for week in range(WEEKS):
        week_start = START + timedelta(weeks=week)
        flu = {z: (rng.uniform(0.03, 0.08) if rng.random() < 0.08 else 0.0) for z in ZONES}

        for shift, crew in crews.items():
            # weekly roster update: trainees progress, some seats go to new hires
            for i, p in enumerate(crew):
                if p.weeks_to_qualify > 0:
                    p.weeks_to_qualify -= 1
                    if p.weeks_to_qualify == 0:
                        p.quals[p.station] = 2
                elif p.role == "operator" and rng.random() < hire_rate(week_start):
                    crew[i] = new_operator(rng, p.station, hire=True)
            overtime = overtime_hours(rng, week_start)

            for d in range(6):  # Mon-Sat
                day = week_start + timedelta(days=d)
                ops = {p.station: p for p in crew if p.role == "operator"}
                floaters = [p for p in crew if p.role == "floater"]

                # features: known the day before, from the roster and zone history only
                zone_trainees = {z: sum(1 for s, p in ops.items() if zone_of(s) == z and p.quals[s] < 2) for z in ZONES}
                zone_rate = {}
                for z in ZONES:
                    hist = zone_history[(shift, z)][-24:]  # last 4 weeks of shifts
                    zone_rate[z] = sum(hist) / len(hist) if hist else 0.12

                # what actually happens on the shift
                absent = {id(p) for p in crew if rng.random() < absence_prob(day, shift, p.zone, overtime, flu[p.zone])}
                present = [p for p in crew if id(p) not in absent]
                for z in ZONES:
                    zone_people = [p for p in crew if p.zone == z]
                    zone_history[(shift, z)].append(sum(id(p) in absent for p in zone_people) / len(zone_people))

                needs = []
                for s, p in ops.items():
                    if id(p) in absent:
                        needs.append((s, "empty"))
                    elif p.quals[s] < 2:
                        needs.append((s, "buddy"))
                free = [p for p in present if p.role == "floater"]
                gaps = run_cover(free, needs, rng)
                # mid-shift: someone goes home, cover again with whoever is still free
                for s, p in ops.items():
                    if id(p) not in absent and s not in gaps and rng.random() < 0.015:
                        gaps |= run_cover(free, [(s, "empty")], rng)

                for s, p in ops.items():
                    z = zone_of(s)
                    rows.append({
                        "date": day.isoformat(), "shift": shift, "station": s, "zone": z,
                        "day_of_week": day.strftime("%A"),
                        "safety_critical": int(s in SAFETY_CRITICAL),
                        "operator_level": p.quals[s],
                        "qualified_backups": sum(1 for f in floaters if f.quals.get(s, 0) >= 2),
                        "zone_trainees": zone_trainees[z],
                        "crew_trainees": sum(zone_trainees.values()),
                        "zone_floaters": sum(1 for f in floaters if f.zone == z),
                        "zone_absence_rate_4w": round(zone_rate[z], 3),
                        "crew_overtime_h_last_week": round(overtime, 1),
                        "gap": int(s in gaps),
                    })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = simulate()
    out = DATA_DIR / "staffing_shifts.csv"
    df.to_csv(out, index=False)
    print(f"Wrote {len(df):,} station-shifts to {out.relative_to(DATA_DIR.parent)}")
    print(f"Stations with a gap: {df.gap.mean():.1%}")
    print(df.groupby(df.date.str[:7]).gap.mean().round(3).rename("gap rate by month").to_string())
