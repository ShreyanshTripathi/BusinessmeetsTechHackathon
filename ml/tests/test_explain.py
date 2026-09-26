"""The LLM layer explains a model's prediction; it never makes the prediction."""
from types import SimpleNamespace

import anthropic

from explain import SYSTEM, explain

EVENT = {
    "agent": "staffing", "type": "cover_risk_tomorrow", "zone": "C", "station": "S18", "severity": "high",
    "confidence": 0.82,
    "evidence": ["82% risk of no qualified cover on the night shift", "0 qualified floater(s) for S18 on the crew"],
    "suggested_action": "Book a qualified floater or plan cross-training for this station",
    "data": {"risk": 0.82, "model": "staffing_model", "drivers": [
        {"feature": "qualified_backups", "value": 0, "typical": 2.0, "effect": 0.31},
        {"feature": "operator_level", "value": 1, "typical": 2.0, "effect": 0.22},
        {"feature": "day_of_week", "value": "Friday", "typical": "Tuesday", "effect": 0.03},
    ]},
}


class FakeClient:
    def __init__(self, response=None, error=None):
        self.response, self.error, self.requests = response, error, []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def reply(text, stop="end_turn"):
    return SimpleNamespace(content=[SimpleNamespace(type="text", text=text)], stop_reason=stop)


def test_claude_gets_the_prediction_evidence_and_drivers():
    client = FakeClient(reply("S18 has no qualified floater tonight."))
    out = explain(EVENT, client=client)
    assert out == {"text": "S18 has no qualified floater tonight.", "mode": "claude"}
    prompt = client.requests[0]["messages"][0]["content"]
    assert "82%" in prompt and "qualified backups is 0 (usually 2.0)" in prompt and "S18" in prompt
    assert client.requests[0]["model"] == "claude-haiku-4-5"


def test_system_prompt_keeps_the_llm_to_explaining():
    low = SYSTEM.lower()
    assert "do not change" in low and "only the facts" in low
    assert "individual" in low


def test_language_is_passed_on():
    client = FakeClient(reply("ok"))
    explain(EVENT, client=client, language="de")
    assert "German" in client.requests[0]["messages"][0]["content"]


def test_offline_template_names_the_top_drivers_and_action():
    out = explain(EVENT, client=None)
    assert out["mode"] == "offline"
    assert "82%" in out["text"] and "qualified backups" in out["text"] and "operator level" in out["text"]
    assert "Book a qualified floater" in out["text"]


def test_refusal_falls_back_to_template():
    out = explain(EVENT, client=FakeClient(reply("", stop="refusal")))
    assert out["mode"] == "offline"


def test_connection_error_falls_back_to_template():
    import httpx2
    err = anthropic.APIConnectionError(message="down", request=httpx2.Request("POST", "https://api.anthropic.com"))
    assert explain(EVENT, client=FakeClient(error=err))["mode"] == "offline"


def test_text_drivers_are_explained_offline_too():
    ev = {**EVENT, "agent": "safety", "data": {"drivers": [{"word": "chain", "effect": 0.12}]}}
    assert "chain" in explain(ev, client=None)["text"]


def test_no_credentials_means_no_client(monkeypatch):
    import explain as ex
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "SHIFTLOOP_OFFLINE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent")  # no `ant auth login` profile either
    assert ex.make_client() is None
    assert explain(EVENT)["mode"] == "offline"


def test_api_key_gives_a_client(monkeypatch):
    import explain as ex
    monkeypatch.delenv("SHIFTLOOP_OFFLINE", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    assert ex.make_client() is not None
