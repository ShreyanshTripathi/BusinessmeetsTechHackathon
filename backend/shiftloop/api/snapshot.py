"""The dashboard's view of the plant: one JSON document, pushed over WebSocket after every simulated minute."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..kpis import kpis
from ..models import Incident

if TYPE_CHECKING:
    from ..plant import Plant

SEVERITY_ORDER = ["info", "low", "medium", "high", "critical"]


def _incident(inc: Incident) -> dict:
    d = inc.model_dump(mode="json", exclude={"event_ids", "event_keys"})
    return d


def snapshot(plant: "Plant", sim: dict, mode: str) -> dict:
    st, central = plant.state, plant.central
    today = st.now.date()
    open_ = central.open_incidents(st)

    # strongest open alert per station and zone, for colouring the floor map
    station_alert: dict[str, str] = {}
    zone_alert: dict[str, str] = {}
    for inc in open_:
        sev = inc.severity.value
        for sid in inc.stations:
            if SEVERITY_ORDER.index(sev) > SEVERITY_ORDER.index(station_alert.get(sid, "info")):
                station_alert[sid] = sev
        if SEVERITY_ORDER.index(sev) > SEVERITY_ORDER.index(zone_alert.get(inc.zone, "info")):
            zone_alert[inc.zone] = sev

    stations = []
    for sid, s in st.layout.stations.items():
        occ = st.station_occupant(sid)
        last = st.last_station.get(sid)
        stations.append({
            "id": sid, "zone": s.zone, "name": s.name, "status": s.status, "safety_critical": s.safety_critical,
            "operator": None if occ is None else {"id": occ.id, "name": occ.name, "level": occ.level(sid, on=today)},
            "cycle_time_s": last.cycle_time_s if last else None, "takt_s": s.takt_s,
            "downtime_min": round(st.downtime_min.get(sid, 0), 1), "defects": st.defects.get(sid, 0),
            "alert": station_alert.get(sid),
        })

    zones = []
    for z in st.layout.zones:
        sensors = [{"id": sid, "kind": sen.kind, "unit": sen.unit, "warn": sen.warn, "crit": sen.crit,
                    "station": sen.station,
                    "value": st.last_sensor[sid].value if sid in st.last_sensor else None}
                   for sid, sen in st.layout.sensors.items() if sen.zone == z.id]
        zones.append({"id": z.id, "name": z.name, "people": st.zone_headcount(z.id),
                      "fire_wardens": [w.name for w in st.fire_wardens(z.id)],
                      "first_aiders": [w.name for w in st.first_aiders(z.id)],
                      "exits": z.exits, "assembly_point": z.assembly_point, "sensors": sensors,
                      "alert": zone_alert.get(z.id)})

    emergency = None
    if st.emergency:
        em = st.emergency
        people = [{"id": w.id, "name": w.name, "station": w.station, "fire_warden": w.fire_warden,
                   "accounted": w.id in em.accounted} for w in st.present() if w.zone == em.zone]
        z = st.layout.zone(em.zone)
        emergency = {"zone": em.zone, "started": em.started.isoformat(), "reason": em.reason,
                     "incident_id": em.incident_id, "people": people,
                     "accounted": sum(1 for p in people if p["accounted"]), "exits": z.exits,
                     "assembly_point": z.assembly_point,
                     "wardens": [p["name"] for p in people if p["fire_warden"]],
                     "minutes": int((st.now - em.started).total_seconds() // 60)}

    expert_queue = [{"id": e.id, "time": e.time.isoformat(), "station": e.station, "evidence": e.evidence,
                     "confidence": e.confidence} for e in st.events if e.type == "inspection_unsure"][-20:]

    return {
        "clock": st.now.isoformat(),
        "sim": sim,
        "mode": mode,
        "zones": zones,
        "stations": stations,
        "incidents": {
            "active": [_incident(i) for i in open_ if i.visibility == "active"],
            "held": [_incident(i) for i in open_ if i.visibility == "held"],
            "in_progress": [_incident(i) for i in st.incidents.values() if i.status == "accepted"],
        },
        "notifications": [n.model_dump(mode="json") for n in reversed(st.notifications[-40:])],
        "escalations": [e.model_dump(mode="json") for e in st.escalations.values()
                        if e.acknowledged_at is None or (st.now - e.acknowledged_at).total_seconds() < 1800],
        "proposals": [p.model_dump() for p in st.proposals.values() if p.status == "pending"],
        "emergency": emergency,
        "kpis": kpis(st, central),
        "attention": central.attention_summary(st),
        "expert_queue": expert_queue,
    }
