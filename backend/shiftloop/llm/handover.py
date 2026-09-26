"""Shift handover: facts gathered from the shift, written up by Claude or by a template when offline."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING

import anthropic

from ..kpis import kpis
from ..state import SHIFT_START
from .client import SUMMARY_MODEL, UNAVAILABLE

if TYPE_CHECKING:
    from ..plant import Plant


def handover_facts(plant: "Plant") -> dict:
    st, central = plant.state, plant.central
    open_ = central.open_incidents(st)
    return {
        "section": "General Assembly, zones A-D",
        "shift": f"{SHIFT_START:%Y-%m-%d} {SHIFT_START:%H:%M}-{st.now:%H:%M}",
        "kpis": kpis(st, central),
        "safety_events": [f"{i.opened:%H:%M} {i.title} ({i.status})" for i in st.incidents.values()
                          if i.category == "safety"],
        "decisions": [f"{d.time:%H:%M} {d.decision.upper()}: {d.incident_title}"
                      + (f" | {'; '.join(d.applied)}" if d.applied else "")
                      + (f" | reason: {d.reason}" if d.reason else "") for d in st.decisions],
        "supervisor_corrections": [f"{d.time:%H:%M} {d.incident_title}: {d.reason}" for d in st.decisions
                                   if d.decision in ("modify", "dismiss") and d.reason],
        "open_issues": [f"{i.title}: {i.recommendation.summary if i.recommendation else ''}" for i in open_],
        "in_progress": [i.title for i in st.incidents.values() if i.status == "accepted"],
        "unconfirmed_escalations": [f"{e.team}: {e.message}" for e in st.escalations.values()
                                    if e.acknowledged_at is None],
        "expert_queue": sum(1 for e in st.events if e.type == "inspection_unsure"),
        "absent": [w.name for w in st.workers.values() if w.status == "absent"],
    }


def _section(title: str, lines: list[str]) -> str:
    return f"{title}\n" + ("\n".join(f"- {line}" for line in lines) if lines else "- none")


def handover_text(facts: dict) -> str:
    k = facts["kpis"]
    downtime = ", ".join(f"{s} {m} min" for s, m in list(k["downtime_min"].items())[:3]) or "none"
    impact = k.get("impact", {})
    parts = [
        f"Shift handover: {facts['section']}, {facts['shift']}",
        _section("Output", [f"{k['cars_built']} cars vs plan {k['plan']} ({k['output_pct']}%)",
                            f"Top downtime: {downtime}", f"Defects detected: {k['defects']}",
                            f"Downtime avoided by early action: {impact.get('downtime_avoided_min', 0)} min"]),
        _section("Safety", facts["safety_events"]),
        _section("Decisions", facts["decisions"][-12:]),
        _section("Supervisor corrections (not yet in the standard)", facts["supervisor_corrections"]),
        _section("Open issues", facts["open_issues"]),
        _section("In progress", facts["in_progress"]),
        _section("Waiting for confirmation", facts["unconfirmed_escalations"]),
        _section("Absent this shift", facts["absent"]),
    ]
    if facts["expert_queue"]:
        parts.append(f"Expert queue: {facts['expert_queue']} inspection(s) waiting for review")
    return "\n\n".join(parts)


def write_handover(plant: "Plant", client=None, language: str = "en") -> dict:
    facts = handover_facts(plant)
    draft = handover_text(facts)
    if client is None:
        return {"text": draft, "facts": facts, "mode": "offline"}
    lang = {"en": "English", "de": "German", "pl": "Polish"}.get(language, "English")
    prompt = ("Write the shift handover for the next supervisor from these facts. Keep every number, name, "
              "station and time exactly as given. Put safety and open issues first, then what the next shift "
              f"should watch. Plain text, short bullet points, in {lang}.\n\nFacts:\n{json.dumps(facts, default=str)}")
    try:
        resp = client.messages.create(model=SUMMARY_MODEL, max_tokens=4000,
                                      messages=[{"role": "user", "content": prompt}])
    except (*UNAVAILABLE, anthropic.APIStatusError):
        return {"text": draft, "facts": facts, "mode": "offline"}
    if resp.stop_reason == "refusal":
        return {"text": draft, "facts": facts, "mode": "offline"}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {"text": text or draft, "facts": facts, "mode": "claude"}
