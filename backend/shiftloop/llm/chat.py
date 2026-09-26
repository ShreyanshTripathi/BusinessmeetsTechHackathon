"""Supervisor chat copilot: Claude with tools over the live factory state, plus an offline fallback."""
from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

import anthropic

from .client import CHAT_MODEL, UNAVAILABLE, make_client
from .handover import handover_facts, handover_text
from .tools import TOOLS, ToolExecutor

if TYPE_CHECKING:
    from ..plant import Plant

MAX_TOOL_ROUNDS = 8
LANGUAGES = {"en": "English", "de": "German", "pl": "Polish"}

SYSTEM = """You are the shift copilot for a production supervisor on a moving vehicle assembly line \
(general assembly, zones A-D, stations S01-S24, one shift). Three specialised agents watch staffing, \
the assembly line and fire & safety; a central agent merges their findings into ranked incidents.

How to answer:
- Use the tools to get live facts before answering. Never invent people, stations or numbers.
- Be brief: the supervisor is on the floor. Lead with the answer, then at most a few short lines of why.
- Name people, stations and times concretely.
- Safety rules are not negotiable: a safety risk stops the area; a quality problem that may still spread stops \
the station; a contained defect is fixed while the rest keeps running.
- You never change anything yourself. To suggest a change, call propose_assignment or propose_decision; the \
supervisor must confirm it in the dashboard. Say that it needs their confirmation.
- Qualification levels: 0 untrained, 1 trainee, 2 qualified, 3 trainer. Nobody may exceed 10 working hours a day.
- Do not judge individual workers' performance; talk about stations, processes and qualifications."""


class ChatCopilot:
    def __init__(self, plant: "Plant", client=None, offline: bool = False, model: str = CHAT_MODEL) -> None:
        self.plant = plant
        self.model = model
        self.client = None if offline else (client if client is not None else make_client())

    def ask(self, message: str, history: list[dict] | None = None, language: str = "en") -> dict:
        executor = ToolExecutor(self.plant)
        if self.client is None:
            return self._offline(message, executor)
        try:
            reply = self._claude(message, history or [], language, executor)
        except UNAVAILABLE:
            out = self._offline(message, executor)
            out["reply"] = "(Claude unavailable, offline answer)\n" + out["reply"]
            return out
        except anthropic.RateLimitError:
            reply = "Claude is rate-limited right now. Try again in a moment."
        except anthropic.APIStatusError as e:
            reply = f"Claude returned an error ({e.status_code}). Try again."
        return {"reply": reply, "proposals": [p.model_dump() for p in executor.proposals], "mode": "claude"}

    # ------------------------------------------------------------------ Claude tool loop

    def _claude(self, message: str, history: list[dict], language: str, executor: ToolExecutor) -> str:
        system = [
            {"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": f"Reply in {LANGUAGES.get(language, 'English')}. "
                                     f"Current time on the floor: {self.plant.state.now:%H:%M}."},
        ]
        messages = [*history, {"role": "user", "content": message}]
        for _ in range(MAX_TOOL_ROUNDS):
            resp = self.client.messages.create(model=self.model, max_tokens=16000, system=system, tools=TOOLS,
                                               messages=messages, output_config={"effort": "medium"})
            if resp.stop_reason == "refusal":
                return "Sorry, I can't help with that request."
            if resp.stop_reason != "tool_use":
                return "".join(b.text for b in resp.content if b.type == "text").strip()
            messages.append({"role": "assistant", "content": resp.content})
            results = [{"type": "tool_result", "tool_use_id": b.id,
                        "content": json.dumps(executor.run(b.name, b.input), default=str)}
                       for b in resp.content if b.type == "tool_use"]
            messages.append({"role": "user", "content": results})
        return "I needed too many lookups for that. Please ask a narrower question."

    # ------------------------------------------------------------------ offline fallback

    def _offline(self, message: str, ex: ToolExecutor) -> dict:
        text = message.strip()
        low = text.lower()
        station = re.search(r"\bS\d{2}\b", text, re.IGNORECASE)
        zone = re.search(r"\bzone\s+([a-d])\b", low)
        reply: str

        assign = re.match(r"(?:assign|move|put)\s+(.+?)\s+(?:to|on|at)\s+(S\d{2})\b", text, re.IGNORECASE)
        if assign:
            out = ex.run("propose_assignment", {"worker": assign.group(1), "station_id": assign.group(2)})
            if "error" in out:
                reply = out["error"]
            else:
                warn = ("\nWarnings: " + "; ".join(out["warnings"])) if out["warnings"] else ""
                reply = f"{out['description']}. Confirm in the dashboard to apply.{warn}"
        elif station and re.search(r"cover|who can|replace|instead", low):
            out = ex.run("find_cover", {"station_id": station.group(0)})
            cands = out.get("candidates", [])
            if not cands:
                out = ex.run("find_cover", {"station_id": station.group(0), "include_assigned": True})
                cands = out.get("candidates", [])
            reply = (f"Cover for {out.get('station', station.group(0).upper())}:\n" +
                     "\n".join(f"- {c['name']}: {c['reason']}" for c in cands[:3])) if cands \
                else f"No qualified cover available for {station.group(0).upper()}."
        elif zone:
            z = ex.run("get_zone", {"zone": zone.group(1)})
            safe = "EMERGENCY in progress" if z["emergency"] else "no emergency"
            reply = (f"Zone {z['zone']}: {z['people']} people, {safe}. Fire wardens: "
                     f"{', '.join(z['fire_wardens']) or 'none'}. First aiders: {', '.join(z['first_aiders']) or 'none'}. "
                     f"Stations: " + ", ".join(f"{k} {v}" for k, v in z["stations"].items()))
        elif station:
            s = ex.run("get_station", {"station_id": station.group(0)})
            op = s["operator"]["name"] + f" (level {s['operator']['level']})" if s.get("operator") else "nobody"
            reply = (f"{s['station']} {s['name']}: {s['status']}, operator {op}, cycle {s['cycle_time_s']}s "
                     f"(takt {s['takt_s']:.0f}s), downtime {s['downtime_min']} min, defects {s['defects']}.")
        elif re.search(r"handover|summar", low):
            reply = handover_text(handover_facts(self.plant))
        elif re.search(r"downtime|output|behind|plan|kpi", low):
            k = ex.run("get_kpis", {})
            top = ", ".join(f"{s} {m} min" for s, m in list(k["downtime_min"].items())[:3]) or "none"
            reply = (f"{k['cars_built']} cars built vs plan {k['plan']} ({k['output_pct']}%). "
                     f"Downtime: {top}. Open incidents: {k['open_incidents']}.")
        else:
            incs = ex.run("get_incidents", {})["incidents"]
            if not incs:
                reply = "Nothing needs your attention right now."
            else:
                reply = "Top priorities:\n" + "\n".join(
                    f"{n}. {i['title']}: {i['recommendation']['summary'] if i['recommendation'] else ''}"
                    for n, i in enumerate(incs, 1))
        return {"reply": reply, "proposals": [p.model_dump() for p in ex.proposals], "mode": "offline"}
