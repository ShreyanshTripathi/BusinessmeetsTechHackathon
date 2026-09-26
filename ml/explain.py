"""Plain-language explanations of model predictions, written by Claude for the supervisor.

The random forests make every prediction. This layer only explains one: it gets the event (risk, evidence)
and the per-prediction drivers, and writes two or three sentences a supervisor can act on. It is told to use
only those facts and never to change the prediction. Without Claude it falls back to a template.
"""
from __future__ import annotations

import os

import anthropic

MODEL = os.getenv("SHIFTLOOP_SUMMARY_MODEL", "claude-haiku-4-5")
LANGUAGES = {"en": "English", "de": "German", "pl": "Polish"}
AUTO = object()  # resolve a client from the environment

SYSTEM = """You explain predictions from a factory's machine-learning models to a production supervisor on \
the shop floor of a vehicle assembly line.

Rules:
- Use only the facts given: the prediction, the evidence and the drivers. Do not add numbers, causes or \
people that are not in the facts.
- Do not change the prediction or its severity. You explain it; the model made it.
- Write two or three short sentences: what is predicted, the main reasons in plain words, and what to do.
- Drivers are the inputs that moved this prediction the most compared with a typical shift; a positive \
effect raised the risk.
- Talk about stations, zones, teams and qualifications. Never judge or blame an individual worker."""


def make_client():
    if os.getenv("SHIFTLOOP_OFFLINE") == "1":
        return None
    try:
        client = anthropic.Anthropic()
    except Exception:  # the SDK raises when a configured credential source is broken
        return None
    # the client constructs even with no credentials and only fails on the first request, so check here
    if not (client.api_key or client.auth_token or getattr(client, "credentials", None)):
        return None
    return client


def _label(feature: str) -> str:
    return feature.replace("_", " ")


def _driver_line(d: dict) -> str:
    points = d["effect"] * 100
    if "word" in d:
        return f'the word "{d["word"]}" ({points:+.0f} points)'
    return f"{_label(d['feature'])} is {d['value']} (usually {d['typical']}), {points:+.0f} points"


def facts(event: dict) -> str:
    where = event.get("station") or f"zone {event['zone']}"
    lines = [
        f"Model: {event.get('data', {}).get('model', event['agent'] + ' model')} ({event['agent']} agent)",
        f"Where: {where}, zone {event['zone']}",
        f"Prediction: {event['type'].replace('_', ' ')}, severity {event['severity']}, "
        f"confidence {event['confidence']:.0%}",
        "Evidence:", *[f"- {e}" for e in event.get("evidence", [])],
        "Drivers (effect on this prediction, in percentage points):",
        *[f"- {_driver_line(d)}" for d in event.get("data", {}).get("drivers", [])],
        f"Suggested action: {event.get('suggested_action', '')}",
    ]
    return "\n".join(lines)


def template(event: dict) -> str:
    drivers = event.get("data", {}).get("drivers", [])
    lead = event.get("evidence", [f"{event['severity']} ({event['confidence']:.0%})"])[0]
    parts = [lead[0].upper() + lead[1:] + "."]
    if drivers:
        parts.append("Main reasons: " + "; ".join(_driver_line(d) for d in drivers[:3]) + ".")
    if event.get("suggested_action"):
        parts.append(f"Suggested: {event['suggested_action']}.")
    return " ".join(parts)


def explain(event: dict, client=AUTO, language: str = "en") -> dict:
    """Return {"text", "mode"}; mode is "claude" or "offline"."""
    if client is AUTO:
        client = make_client()
    if client is None:
        return {"text": template(event), "mode": "offline"}
    prompt = f"{facts(event)}\n\nWrite the explanation in {LANGUAGES.get(language, 'English')}."
    try:
        resp = client.messages.create(model=MODEL, max_tokens=1000, system=SYSTEM,
                                      messages=[{"role": "user", "content": prompt}])
    except (anthropic.APIConnectionError, anthropic.AuthenticationError, anthropic.PermissionDeniedError,
            anthropic.RateLimitError, anthropic.APIStatusError):
        return {"text": template(event), "mode": "offline"}
    if resp.stop_reason == "refusal":
        return {"text": template(event), "mode": "offline"}
    text = "".join(b.text for b in resp.content if b.type == "text").strip()
    return {"text": text or template(event), "mode": "claude" if text else "offline"}
