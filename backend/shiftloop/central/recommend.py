"""Turn an incident into a recommendation: what to do with the area and who to send.

Hard rules from the supervisor role come first and cannot be overridden by ranking or by the LLM:
  * a safety risk stops the area,
  * a quality problem that may still spread stops the station,
  * a defect already contained is fixed while the rest keeps running.
"""
from __future__ import annotations

from datetime import datetime, time

from ..factory import ZONE_ORDER
from ..matching import Candidate, cover_candidates, maintenance_candidates
from ..models import Assignment, Event, Incident, Recommendation
from ..state import FactoryState

BREAKS = [time(9, 30), time(12, 0)]


def next_break(now: datetime) -> datetime | None:
    for b in BREAKS:
        at = datetime.combine(now.date(), b)
        if at > now:
            return at
    return None


def _neighbours(zone: str) -> tuple[str | None, str | None]:
    i = ZONE_ORDER.index(zone)
    up = ZONE_ORDER[i - 1] if i > 0 else None
    down = ZONE_ORDER[i + 1] if i < len(ZONE_ORDER) - 1 else None
    return up, down


def _usable(state: FactoryState, cand: dict, taken: set[str]) -> bool:
    w = state.workers.get(cand.get("worker_id", ""))
    return (w is not None and w.status == "present" and not w.busy_with and w.id not in taken
            and w.station == cand.get("current_station"))


def _pick(state: FactoryState, from_event: list[dict], fresh: list[Candidate], taken: set[str]) -> dict | None:
    for c in from_event:
        if _usable(state, c, taken):
            return c
    for c in fresh:
        if c.worker_id not in taken:
            return c.as_dict()
    return None


class Builder:
    def __init__(self, state: FactoryState, incident: Incident, events: list[Event]):
        self.state, self.incident, self.events = state, incident, events
        self.types = {e.type: e for e in events}
        self.steps: list[str] = []
        self.assignments: list[Assignment] = []
        self.escalations: list[str] = []
        self.taken: set[str] = set()

    # -------------------------------------------------------------- helpers

    def assign(self, cand: dict, task: str, to_station: str | None = None, to_zone: str | None = None,
               kind: str = "station") -> None:
        self.taken.add(cand["worker_id"])
        self.assignments.append(Assignment(worker=cand["worker_id"], worker_name=cand["name"], kind=kind,
                                           to_station=to_station, to_zone=to_zone, task=task,
                                           reason=cand.get("reason", "")))

    def send_maintenance(self, zone: str, task: str) -> None:
        tech = _pick(self.state, [], maintenance_candidates(self.state, zone), self.taken)
        if tech:
            self.assign(tech, task, to_zone=zone, kind="relocate")
            self.steps.append(f"Send {tech['name']} (maintenance): {task}")
        else:
            self.steps.append("No maintenance technician free: call the maintenance lead")
        self._escalate("maintenance")

    def cover(self, station: str, task: str, from_event: list[dict] | None = None) -> bool:
        """Cover a station without opening a new gap: free people first, otherwise a move plus a backfill."""
        free = [c for c in (from_event or []) if not c.get("current_station")]
        cand = _pick(self.state, free, cover_candidates(self.state, station), self.taken)
        if cand:
            self.assign(cand, task, to_station=station)
            self.steps.append(f"Move {cand['name']} to {station}: {cand.get('reason', '')}")
            return True
        for c in cover_candidates(self.state, station, include_assigned=True, limit=20):
            if c.worker_id in self.taken or c.current_station is None:
                continue
            backfill = next((b for b in cover_candidates(self.state, c.current_station)
                             if b.worker_id not in self.taken and b.worker_id != c.worker_id), None)
            if backfill:
                self.assign(c.as_dict(), task, to_station=station)
                self.assign(backfill.as_dict(), f"backfill {c.current_station}", to_station=c.current_station)
                self.steps.append(f"Move {c.name} from {c.current_station} to {station}; "
                                  f"{backfill.name} backfills {c.current_station}")
                return True
        self.steps.append(f"No qualified cover free for {station}: ask the neighbouring section")
        return False

    def _escalate(self, team: str) -> None:
        if team not in self.escalations:
            self.escalations.append(team)

    def rec(self, action: str, target: str, summary: str, scope: str = "station", hard_rule: str | None = None):
        return Recommendation(action=action, scope=scope, target=target, summary=summary, steps=self.steps,
                              assignments=self.assignments, escalations=self.escalations, hard_rule=hard_rule)

    # -------------------------------------------------------------- rules

    def build(self) -> Recommendation:
        inc, t, state = self.incident, self.types, self.state
        zone = inc.zone
        station = inc.stations[0] if inc.stations else None
        up, down = _neighbours(zone)

        # 1. Confirmed fire: emergency, hard rule
        if "fire_confirmed" in t:
            people = state.zone_headcount(zone)
            z = state.layout.zone(zone)
            wardens = state.fire_wardens(zone)
            self.steps.append(f"STOP zone {zone} now (safety rule)")
            self.steps.append(f"{people} people in zone {zone}: evacuate via {', '.join(z.exits)} to {z.assembly_point}")
            if wardens:
                self.steps.append("Fire warden(s) on site: " + ", ".join(w.name for w in wardens))
            else:
                self.steps.append(f"No fire warden in zone {zone}: nearest warden takes over")
            if up:
                self.steps.append(f"Slow zone {up} (upstream) so cars do not pile up")
            if down:
                self.steps.append(f"Zone {down} (downstream) runs on buffer, then waits")
            self._escalate("plant fire brigade")
            self._escalate("EHS")
            return self.rec("emergency", zone, f"Fire in zone {zone}: stop, evacuate, count people",
                            scope="zone", hard_rule="safety_stop")

        # 2. Other hard safety stops (critical battery, gas, heat)
        hard = [e for e in self.events if e.data.get("hard_rule") == "safety_stop"]
        if hard:
            e = hard[0]
            scope, target = ("station", e.station) if e.station else ("zone", zone)
            self.steps.append(f"STOP {target} now (safety rule): {e.evidence[0]}")
            if e.type == "battery_overheating":
                self.steps.append("Clear people from the battery area, start the thermal-runaway procedure")
            if up and scope == "zone":
                self.steps.append(f"Slow zone {up} (upstream)")
            self._escalate("EHS")
            self.send_maintenance(zone, f"make {target} safe")
            return self.rec("stop", target, f"Safety stop at {target}", scope=scope, hard_rule="safety_stop")

        # Near-miss report rated by the safety model: learn from it, no blame
        if "near_miss_rated" in t or "near_miss_unsure" in t:
            e = t.get("near_miss_rated") or t["near_miss_unsure"]
            where = station or f"zone {zone}"
            if e.type == "near_miss_unsure":
                self.steps.append("Safety expert rates the report (the model is unsure)")
            self.steps.append(f"Engineer reviews the method at {where} with the team: fix the process, no blame")
            self.steps.append("Check whether the same risk exists at similar stations")
            self._escalate("EHS")
            self._escalate("engineering")
            return self.rec("keep_running", station or zone, f"Learn from the near miss at {where}",
                            scope="station" if station else "zone")

        # 3. Safety warnings needing action but not a stop
        if "possible_fire" in t or "battery_overheating" in t:
            wardens = state.fire_wardens(zone)
            if wardens:
                w = wardens[0]
                self.assign({"worker_id": w.id, "name": w.name, "reason": "fire warden in zone"},
                            "verify smoke source now", to_zone=zone, kind="task")
                self.steps.append(f"Fire warden {w.name} verifies zone {zone} now")
            else:
                self.steps.append(f"No fire warden in zone {zone}: send the nearest one to verify")
            if "battery_overheating" in t:
                self.steps.append("Pause battery fitting at S18 until the pack is checked")
            self.steps.append("Prepare to stop the zone if confirmed")
            self._escalate("EHS")
            action = "stop" if "battery_overheating" in t else "keep_running"
            target = "S18" if "battery_overheating" in t else zone
            return self.rec(action, target, f"Verify possible fire in zone {zone}",
                            scope="station" if action == "stop" else "zone")
        if inc.category == "safety":
            for e in self.events:
                if e.type == "exit_blocked":
                    self.steps.append(f"Clear the blocked exit in zone {zone} now; check with logistics")
                    self._escalate("logistics")
                elif e.type == "ppe_missing":
                    self.steps.append(f"Remind zone {zone} about protective equipment (no individual tracking)")
                elif e.type in ("gas_alarm", "high_heat"):
                    self.steps.append(f"Check the source: {e.evidence[0]}")
                    self._escalate("EHS")
            return self.rec("keep_running", zone, self.incident.title, scope="zone")

        # 4. Quality: repeated defects
        if "defect_pattern" in t:
            d = t["defect_pattern"]
            spread = d.data.get("spread_risk", False)
            if spread:
                self.steps.append(f"STOP {station} (quality rule): the defect may still be spreading")
                self.steps.append(f"Hold and check the last {d.data.get('count', 3) * 3} cars from {station}")
            else:
                self.steps.append(f"100% check at {station} until the cause is fixed")
            if "predicted_tool_failure" in t:
                self.send_maintenance(zone, f"swap the tool at {station} now")
            elif "untrained_at_station" in t:
                buddy = next((c for c in cover_candidates(state, station, include_assigned=True, limit=10)
                              if c.level == 3), None)
                if buddy:
                    self.assign(buddy.as_dict(), f"buddy the trainee at {station}", to_station=station, kind="task")
                    self.steps.append(f"Pair the trainee with {buddy.name} (trainer on {station})")
            self._escalate("quality")
            if spread:
                return self.rec("stop", station, f"Contain defects at {station}", hard_rule="quality_spread")
            return self.rec("keep_running", station, f"Check every car at {station}")

        if "inspection_unsure" in t:
            self.steps.append("Send the images to the quality expert queue; the car continues")
            return self.rec("keep_running", station, "Expert review requested")

        # 5. Production
        if "predicted_tool_failure" in t or "station_stopped" in t:
            if "station_stopped" in t:
                self.send_maintenance(zone, f"repair {station}")
                if up:
                    self.steps.append(f"Upstream stations fill their buffers; slow zone {up} if the repair takes >10 min")
            else:
                p = t["predicted_tool_failure"]
                eta = p.data.get("eta_min")
                brk = next_break(state.now)
                minutes_to_break = (brk - state.now).total_seconds() / 60 if brk else None
                if brk and eta is not None and minutes_to_break is not None and minutes_to_break < eta:
                    self.send_maintenance(zone, f"swap the tool at {station} at the {brk:%H:%M} break")
                    self.steps.append(f"Planned swap avoids an unplanned stop (failure expected in ~{eta} min)")
                else:
                    self.send_maintenance(zone, f"swap the tool at {station} now, before it fails")
            if "station_uncovered" in t:
                self.cover(station, f"cover {station}", t["station_uncovered"].data.get("candidates", []))
            return self.rec("keep_running", station, self.incident.title)

        if "station_uncovered" in t:
            self.cover(station, f"cover {station}", t["station_uncovered"].data.get("candidates", []))
            return self.rec("keep_running", station, f"Cover {station}")

        if "untrained_at_station" in t:
            buddy = next((c for c in cover_candidates(state, station, include_assigned=True, limit=10)
                          if c.level == 3), None)
            if buddy:
                self.assign(buddy.as_dict(), f"buddy the trainee at {station}", to_station=station, kind="task")
                self.steps.append(f"Pair the trainee with {buddy.name} (trainer on {station})")
            else:
                self.cover(station, f"take over {station}", t["untrained_at_station"].data.get("candidates", []))
            return self.rec("keep_running", station, f"Support the trainee at {station}")

        if "cover_risk" in t:
            cand = _pick(state, [], cover_candidates(state, station), self.taken)
            if cand:
                self.assign(cand, f"stand by as qualified backup for {station}", to_station=station, kind="task")
                self.steps.append(f"Line up {cand['name']} as backup for {station}: {cand.get('reason', '')}")
            else:
                self.steps.append(f"No free qualified backup for {station}: plan cross-training this week")
            self.steps.append(t["cover_risk"].evidence[0])
            return self.rec("keep_running", station, f"Prepare cover for {station} before a gap opens")

        if "part_shortage" in t:
            p = t["part_shortage"]
            self.steps.append(f"Call logistics: {p.evidence[0]}")
            self._escalate("logistics")
            action = "slow" if p.data.get("minutes_left", 99) < 10 else "keep_running"
            if action == "slow":
                self.steps.append(f"Slow {station} to stretch the remaining parts")
            return self.rec(action, station, f"Replenish {p.data.get('part')} at {station}")

        if "slowdown" in t:
            self.steps.append(f"Walk to {station}: {t['slowdown'].evidence[0]}")
            return self.rec("keep_running", station, f"Find why {station} is slow")

        if "output_target_risk" in t:
            e = t["output_target_risk"]
            self.steps.extend(e.evidence[:2])
            self.steps.append(f"Check staffing and buffer in zone {zone} before the next break")
            return self.rec("keep_running", zone, f"Protect zone {zone}'s output target", scope="zone")

        # 6. Staffing-only
        if "fire_warden_gap" in t:
            donors = t["fire_warden_gap"].data.get("donors", [])
            donor = next((d for d in donors if _usable(state, d, self.taken)), None)
            if donor:
                self.assign(donor, f"fire warden cover for zone {zone}", to_zone=zone, kind="relocate")
                self.steps.append(f"Move {donor['name']} (fire warden) to zone {zone}")
                if donor.get("current_station"):
                    self.cover(donor["current_station"], f"backfill {donor['current_station']}")
            else:
                self.steps.append(f"No spare fire warden: call one in for zone {zone}")
            return self.rec("keep_running", zone, f"Restore fire warden cover in zone {zone}", scope="zone")

        if "first_aider_gap" in t:
            self.steps.append(f"Tell zone {zone} who the nearest first aider is")
            return self.rec("keep_running", zone, f"First aid cover for zone {zone}", scope="zone")

        if "working_time_limit" in t:
            e = t["working_time_limit"]
            if e.station:
                self.cover(e.station, f"relieve at {e.station} before the legal limit")
            else:
                self.steps.append("Send home before the legal limit")
            return self.rec("keep_running", e.station or zone, "Relieve before the working-time limit")

        if "qualification_expiring" in t:
            self.steps.append("Book re-certification with training this week")
            return self.rec("keep_running", station or zone, "Schedule re-certification")

        self.steps.append("Review")
        return self.rec("keep_running", station or zone, self.incident.title)


def recommend(state: FactoryState, incident: Incident, events: list[Event]) -> Recommendation:
    return Builder(state, incident, events).build()
