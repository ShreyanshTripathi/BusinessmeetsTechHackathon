# Conversation summary

**Session:** Tesla Giga Berlin hackathon, 25–26 Sep 2026 · **Full log:** [conversation_log.md](conversation_log.md)

## Goal

Build an AI product that makes the day-to-day work of a **production supervisor** or **production engineer**
at Giga Berlin easier. Role definitions are in [../roles/](../roles/). Hackathon theme (from Tesla's slide):
**"Sustainably increase efficiency through AI"**, with three pillars (Program, People, Tech) and nine topics:
Compliance, Oversight, Impact / Quality, Data, Applications / Interaction, Development, Change.

## How the idea developed

1. **Problem discovery.** Pain points for both roles came from the role files. The key insight was the gap
   between them: supervisors make floor corrections that never get written down, and engineers own a method
   that can drift from what's really done. Giga Berlin constraints: works council co-determination (no
   individual performance monitoring), GDPR / EU AI Act (worker management AI is high-risk), a multilingual
   workforce, noisy shop floor.
2. **Multi-agent idea (yours).** One agent per pain point feeding a supervisor-facing layer, because
   supervisors face too much data. Refined to: specialised agents emit structured events, and a central
   agent merges, ranks and recommends within an attention budget of max 3 items.
3. **Multimodal question.** Use small per-sensor models (vision, audio, vibration, temperature) near the
   line, and multimodal LLMs only for low-volume explanation tasks.
4. **Novelty check.** Predictive maintenance and copilots already exist. The differentiator: deciding what
   the supervisor can ignore, linking machines with people and qualifications, and closing the loop.
5. **Other angles explored:** supply chain (fits as a Material agent), sustainability (lasting fixes plus
   energy/scrap/water and workload), engineer–supervisor communication (station threads), your expert visual
   inspection model, expert checks by supervisors and engineers (ergonomics, restart checks), reliability
   (maintenance-log structuring, service intervals).
6. **Tesla's slide** pointed to **Oversight** as AI governance, so an oversight layer was added: decision
   log, human approval, drift fallback, works council view, measured impact.
7. **Final MVP scope (your decision):** a central intelligence for the whole factory, starting with three
   functions (**Staffing**, **General Assembly Line**, **Fire & Safety**), each with its own agent, plus
   one broader agent that connects them, and a supervisor dashboard with notifications and a chatbot.

## Decisions

| Topic | Choice |
|---|---|
| Timeline | 1 week or more |
| Vision | Pretrained YOLO (fire/smoke, PPE) + your own visual QC model |
| Stack | Python/FastAPI backend, React + Tailwind frontend |
| LLM | Claude API: Sonnet 5 for chat, Haiku 4.5 for summaries (configurable) |
| Method | Test-driven development |

## What was built ("ShiftLoop")

See [../PLAN.md](../PLAN.md) and [../README.md](../README.md).

- **Backend** (`backend/`, 148 tests)
  - Staffing, Assembly and Fire & Safety agents
  - Central intelligence: merge, rank (safety first, max 3 visible), people matching, recommendations with
    hard stop rules
  - Decisions, escalations with reminders, emergency all-clear with restart plan, what-if, KPIs, oversight
  - Scripted demo shift simulator
  - Claude chat copilot with tools and confirm-before-apply proposals (offline fallback)
  - Shift handover
  - Vision service with detector slots
  - FastAPI + WebSocket
- **Frontend** (`frontend/`, 43 tests): sidebar with sections Now, Line, People, Safety, Alerts, Copilot,
  Oversight, Handover. An emergency takes over the screen with headcount, check-ins and all clear. Redesigned
  from a busy single screen after your feedback.
- **Demo shift:**
  - 06:00 absences
  - 08:30 tool wear at S12, predicted before the 09:30 break
  - 09:00 trainee at S09, then 09:40 defects, merged into one incident
  - 10:16 battery smoke in zone C: emergency
  - 10:25 all clear
  - later: part shortage, PPE and blocked-exit events

**Bugs found by tests and fixed:**
- Recommendations could open a new staffing gap.
- The merge window missed ongoing conditions.
- Low-severity items took inbox slots.
- A duplicated escalation text.
- The Vite proxy failed over IPv6.

## Not yet verified or open

- **Claude:** the real API is untested because no key was available; tests use a fake client. Add a key or
  run `ant auth login`.
- **Vision:** YOLO and your QC model have only been tested with stand-in models. Still needed: which
  inspection your model does, and the code to plug in (`SHIFTLOOP_QC_MODEL=module:function`).
- **Voice input:** not tried in a real browser.
- **Organisers:** confirm what "Oversight" means and whether the nine topics are the judging criteria.
- **Housekeeping:** `~/.npm` has root-owned files (`sudo chown -R 501:20 ~/.npm`). The project is not a git
  repository yet.

## Run

```bash
cd backend && uv sync && uv run shiftloop      # :8000
cd frontend && npm install && npm run dev      # http://localhost:5173
```
