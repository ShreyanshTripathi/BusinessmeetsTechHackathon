# ShiftLoop: Central Factory Intelligence (MVP)

Tesla Giga Berlin hackathon. Theme: *Sustainably increase efficiency through AI.*

Three specialised agents (**Staffing**, **General Assembly**, **Fire & Safety**) watch their part of the line.
A **central intelligence** merges their findings into incidents, ranks them (safety first), matches people to
problems and recommends actions. The **supervisor dashboard** shows at most three decisions at a time, with
notifications, a chat copilot (Claude), an emergency mode and a full oversight log. Humans make every decision.

See [PLAN.md](PLAN.md) for the product plan and [roles/](roles/) for the role definitions it is built from.

## Run it

Two terminals.

```bash
# 1. backend (http://127.0.0.1:8000)
cd backend
uv sync
uv run shiftloop            # or: uv run uvicorn shiftloop.api.app:make_default --factory --port 8000

# 2. frontend (http://localhost:5173)
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The demo shift starts at 06:00 and runs at 2 simulated minutes per second; use
▶ / ❚❚, **+15 min** and the speed selector in the top bar. **Reset** restarts the scripted shift.

### Claude

The chat copilot and handover use the Claude API when credentials resolve (`ANTHROPIC_API_KEY`, an auth token,
or an `ant auth login` profile). Without credentials the app runs in **offline mode**: rule-based answers and a
template handover; everything else works the same.

| Variable | Default | Purpose |
|---|---|---|
| `SHIFTLOOP_CHAT_MODEL` | `claude-sonnet-5` | chat copilot |
| `SHIFTLOOP_SUMMARY_MODEL` | `claude-haiku-4-5` | shift handover |
| `SHIFTLOOP_OFFLINE=1` | unset | force offline mode |

### Vision models

Camera frames can be posted to `POST /api/vision/{camera_id}` (multipart `image`). Each camera purpose has a
detector slot; empty slots return 503 and the simulator's scripted detections are used instead.

| Variable | Slot | Expected |
|---|---|---|
| `SHIFTLOOP_QC_MODEL=module:function` | quality cameras `CAM-QC-Sxx` | `fn(PIL.Image) -> (label, confidence, detail)`; label `ok` or `defect` |
| `SHIFTLOOP_FIRE_MODEL=weights.pt` | fire cameras `CAM-FIRE-x` | YOLO weights with `fire`/`smoke` classes (`uv sync --extra vision`) |
| `SHIFTLOOP_PPE_MODEL=weights.pt` | PPE cameras `CAM-PPE-x` | YOLO weights with `no-helmet`/`no-vest` style classes |

Detections under 50% confidence become *expert review* items instead of defects.

## The demo shift

| Time | What happens | What the system does |
|---|---|---|
| 06:00 | 3 absences | S12 uncovered + zone B without fire warden → cover and warden swap suggested (with backfill) |
| 08:30 | Tool at S12 starts wearing (torque spread grows) | ~09:00 predicts failure, schedules the swap at the 09:30 break and names the free technician. Ignore it and S12 stops at ~10:00 |
| 09:00 | S09 operator goes home; a trainee takes over | Staffing flags the trainee |
| 09:40 | Loose-fastener defects at S09 | Merged with the trainee: *likely method/training, not the machine*; quality rule stops S09 at 3 defects |
| 10:12–10:16 | Battery pack at S18 heats up, smoke on camera, then smoke sensor | Fire confirmed → **emergency mode**: zone C stopped, headcount, exits, wardens, upstream zone slowed |
| 10:25 | Fire out | Supervisor taps **All clear** → restart plan with cars to recover |
| 11:00+ | Part shortage at S22, missing PPE in zone A, blocked exit in zone D | Logistics call, zone-level reminders |

Try the copilot: *"Who can cover S12?"*, *"Is zone C safe?"*, *"assign Lena Schmidt to S03"* (creates a
proposal you confirm), *"Summarise the shift for the handover"*.

## Tests

```bash
cd backend && uv run pytest        # agents, central, actions, simulator, API, LLM loop (fake client), vision
cd frontend && npm test            # components against real snapshot fixtures
```

Frontend fixtures in `frontend/src/test/fixtures/` are generated from the real backend; regenerate them if the
snapshot format changes.

## Layout

```
backend/shiftloop/
  factory.py, models.py, state.py   layout, roster, domain models, shared state
  agents/                           staffing.py, assembly.py, safety.py (+ base condition tracking)
  central/                          fusion (merge), ranking, recommend (hard rules), engine
  actions.py                        decisions, escalations + reminders, all clear, impact accounting
  matching.py, whatif.py, kpis.py, oversight.py, stats.py
  simulator/shift.py                synthetic signals + scripted demo shift
  plant.py                          simulator → bus → agents → central
  llm/                              Claude chat tool loop, tools, handover, offline fallback
  vision/service.py                 detector slots (team QC model, YOLO fire/PPE)
  api/                              FastAPI app + snapshot
frontend/src/
  App.tsx, api.ts, useSnapshot.ts   shell, REST client, live WebSocket
  components/                       PriorityInbox, FloorMap, Notifications, Escalations, ChatPanel,
                                    EmergencyView, StaffingBoard, OversightView, HandoverView, TopBar
```

## Assumptions to replace with plant data

Impact numbers (downtime avoided, energy saved, rework avoided) use documented constants in
`backend/shiftloop/actions.py`. Takt is 60 s, breaks are at 09:30 and 12:00 (`central/recommend.py`), and the
working-time limit is 10 h/day (`matching.py`).
# BusinessmeetsTechHackathon
<<<<<<< HEAD
# BusinessmeetsTechHackathon
=======
>>>>>>> 80f4fef125dfb9fa3f0c1b99a25a01a675cdd3b1
# BusinessmeetsTechHackathon
