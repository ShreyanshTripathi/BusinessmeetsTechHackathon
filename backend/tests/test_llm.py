from datetime import datetime, time
from types import SimpleNamespace

import pytest

from shiftloop.llm.chat import ChatCopilot
from shiftloop.llm.handover import handover_facts, handover_text
from shiftloop.llm.tools import TOOLS, ToolExecutor
from shiftloop.plant import Plant


# ------------------------------------------------------------------ fake Claude client


def text_block(t):
    return SimpleNamespace(type="text", text=t)


def tool_block(name, inp, id_="tu_1"):
    return SimpleNamespace(type="tool_use", name=name, input=inp, id=id_)


class FakeClient:
    """Replays scripted responses and records every request."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.messages = self

    def create(self, **kwargs):
        self.requests.append(kwargs)
        content, stop = self.responses.pop(0)
        return SimpleNamespace(content=content, stop_reason=stop)


@pytest.fixture
def plant():
    p = Plant(scenario="demo")
    p.step(2)
    return p


# ------------------------------------------------------------------ tools


def test_every_tool_has_a_schema_and_an_implementation(plant):
    ex = ToolExecutor(plant)
    names = {t["name"] for t in TOOLS}
    assert {"get_incidents", "get_zone", "find_cover", "get_kpis", "propose_assignment", "propose_decision"} <= names
    for t in TOOLS:
        assert t["input_schema"]["type"] == "object"
        assert hasattr(ex, t["name"]), t["name"]


def test_find_cover_returns_qualified_candidates(plant):
    out = ToolExecutor(plant).run("find_cover", {"station_id": "S12"})
    assert out["station"] == "S12" and out["candidates"]


def test_get_zone_reports_people_and_safety_roles(plant):
    out = ToolExecutor(plant).run("get_zone", {"zone": "B"})
    assert out["people"] > 0 and "fire_wardens" in out and len(out["stations"]) == 6


def test_propose_assignment_stages_but_does_not_apply(plant):
    ex = ToolExecutor(plant)
    worker = next(w for w in plant.state.workers.values() if w.role == "floater" and w.station is None)
    out = ex.run("propose_assignment", {"worker": worker.name, "station_id": "S03", "reason": "test"})
    assert out["status"] == "pending"
    assert plant.state.workers[worker.id].station is None
    assert ex.proposals[0].params["worker"] == worker.id


def test_unknown_worker_returns_an_error_not_an_exception(plant):
    out = ToolExecutor(plant).run("get_worker", {"name_or_id": "Nobody Here"})
    assert "error" in out


def test_unknown_tool_returns_error(plant):
    assert "error" in ToolExecutor(plant).run("drop_tables", {})


# ------------------------------------------------------------------ chat loop


def test_chat_runs_tool_loop_and_returns_final_text(plant):
    client = FakeClient([
        ([text_block("Checking zone B."), tool_block("get_zone", {"zone": "B"})], "tool_use"),
        ([text_block("Zone B has 7 people.")], "end_turn"),
    ])
    out = ChatCopilot(plant, client=client).ask("How is zone B?")
    assert out["reply"] == "Zone B has 7 people."
    assert out["mode"] == "claude"
    second = client.requests[1]["messages"]
    tool_result = second[-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "tu_1"
    assert '"people"' in tool_result["content"]


def test_chat_returns_proposals_for_confirmation(plant):
    worker = next(w for w in plant.state.workers.values() if w.role == "floater" and w.station is None)
    client = FakeClient([
        ([tool_block("propose_assignment", {"worker": worker.id, "station_id": "S12", "reason": "cover"})], "tool_use"),
        ([text_block("I proposed the move. Confirm to apply.")], "end_turn"),
    ])
    out = ChatCopilot(plant, client=client).ask("Put someone on S12")
    assert len(out["proposals"]) == 1 and out["proposals"][0]["status"] == "pending"
    assert plant.state.proposals[out["proposals"][0]["id"]].kind == "assign"


def test_chat_system_prompt_sets_language_and_rules(plant):
    client = FakeClient([([text_block("Hallo")], "end_turn")])
    ChatCopilot(plant, client=client).ask("Hi", language="de")
    system = client.requests[0]["system"]
    text = system if isinstance(system, str) else " ".join(b["text"] for b in system)
    assert "German" in text and "confirm" in text.lower()


def test_chat_passes_history(plant):
    client = FakeClient([([text_block("ok")], "end_turn")])
    history = [{"role": "user", "content": "earlier"}, {"role": "assistant", "content": "answer"}]
    ChatCopilot(plant, client=client).ask("now", history=history)
    msgs = client.requests[0]["messages"]
    assert msgs[0]["content"] == "earlier" and msgs[-1]["content"] == "now"


def test_refusal_is_reported(plant):
    client = FakeClient([([], "refusal")])
    out = ChatCopilot(plant, client=client).ask("x")
    assert out["mode"] == "claude" and "can't help" in out["reply"].lower()


def test_offline_mode_answers_cover_question(plant):
    out = ChatCopilot(plant, client=None, offline=True).ask("Who can cover S12?")
    assert out["mode"] == "offline"
    assert "S12" in out["reply"]


def test_offline_mode_can_propose_assignment(plant):
    worker = next(w for w in plant.state.workers.values() if w.role == "floater" and w.station is None)
    out = ChatCopilot(plant, client=None, offline=True).ask(f"assign {worker.name} to S03")
    assert out["proposals"] and out["proposals"][0]["params"]["station"] == "S03"


def test_offline_mode_default_lists_priorities(plant):
    out = ChatCopilot(plant, client=None, offline=True).ask("what now?")
    assert "1." in out["reply"]


# ------------------------------------------------------------------ confirming proposals


def test_confirming_assignment_proposal_applies_and_logs(plant):
    ex = ToolExecutor(plant)
    worker = next(w for w in plant.state.workers.values() if w.role == "floater" and w.station is None)
    ex.run("propose_assignment", {"worker": worker.id, "station_id": "S12", "reason": "cover"})
    pid = ex.proposals[0].id
    result = plant.confirm_proposal(pid)
    assert plant.state.station_occupant("S12").id == worker.id
    assert plant.state.proposals[pid].status == "confirmed"
    assert plant.state.decisions[-1].decided_by == "supervisor (via chat)"
    assert result["applied"]


def test_rejecting_proposal_changes_nothing(plant):
    ex = ToolExecutor(plant)
    worker = next(w for w in plant.state.workers.values() if w.role == "floater" and w.station is None)
    ex.run("propose_assignment", {"worker": worker.id, "station_id": "S03", "reason": "x"})
    plant.reject_proposal(ex.proposals[0].id)
    assert plant.state.workers[worker.id].station is None


# ------------------------------------------------------------------ handover


def test_handover_facts_and_text_cover_the_shift():
    p = Plant(scenario="demo")
    p.step(1)
    for inc in list(p.central.open_incidents(p.state)):
        p.decide(inc.id, "accept")
    p.run_until(datetime.combine(p.state.now.date(), time(9, 0)))
    facts = handover_facts(p)
    assert facts["kpis"]["cars_built"] > 0
    assert facts["decisions"] and facts["open_issues"] is not None
    text = handover_text(facts)
    assert "Shift handover" in text and "Open issues" in text and "Decisions" in text
