# NERV: Central Factory Intelligence (MVP)

Tesla Giga Berlin hackathon. Theme: *Sustainably increase efficiency through AI.*

**Live app:** [nerv-tech.lovable.app](https://nerv-tech.lovable.app/)

The code still uses the working name `shiftloop` (Python package, `SHIFTLOOP_*` settings, service name). The
dashboard frontend was rebuilt in [Lovable](https://lovable.dev) and lives on the `frontend` branch — see
[Layout](#layout) below for how its files map onto the original design.

Three specialised agents (**Staffing**, **General Assembly**, **Fire & Safety**) watch their part of the line.
A **central intelligence** merges their findings into incidents, ranks them (safety first), matches people to
problems and recommends actions. The **supervisor dashboard** shows at most three decisions at a time, with
notifications, a chat copilot (Claude), an emergency mode and a full oversight log. Humans make every decision.

See [PLAN.md](PLAN.md) for the product plan and [roles/](roles/) for the role definitions it is built from.

## Benefits

1. **One central brain for the factory.** Staffing, assembly and safety are no longer separate systems: the
   central intelligence joins their findings, so a trainee plus rising defects at one station becomes one
   incident with one likely cause.
2. **Transparent, explainable decisions.** Every model prediction comes with its main drivers and a
   plain-language explanation (optionally rewritten by Claude). Every incident says in one line why it is ranked
   where it is, with the points behind its score. The oversight log records every recommendation and decision.
3. **Severity and action items, ready to act on.** Each incident carries a severity, a priority tier and a
   recommendation: concrete steps, who to send and which team to call. Today a supervisor works this out by hand.
4. **Problems predicted before they happen.** Tool failure is forecast from torque drift, parts run-out from
   stock and consumption, and missed output targets and staffing gaps by the ML models. That leaves time to plan
   a fix, for example a tool swap at the next break.
5. **Staff shortages predicted and covered.** The staffing model flags stations that may lose qualified
   cover this shift. The matching engine proposes qualified, available replacements within working-time limits,
   and backfills any station it takes them from.
6. **Voice alerts for decisions on the go.** Every alert includes a short phrase ready to be read aloud, so
   the dashboard can speak critical alerts to a supervisor walking the line.
7. **Modular and ready for new models.** Agents share one event format, and camera models plug into
   detector slots, so richer multimodal or spatial models can replace or join the current ones without
   changing the rest of the system.

## Run it

Two terminals.

```bash
# 1. backend (http://127.0.0.1:8000)
cd backend
uv sync
uv run shiftloop            # or: uv run uvicorn shiftloop.api.app:make_default --factory --port 8000

# 2. frontend
cd frontend
npm install
npm run dev
```

The dev server prints its local URL on start. By default the frontend talks to the **hosted** backend
(`https://shiftloop.onrender.com`, baked in as `DEFAULT_API`) — point it at your local backend instead by
opening the printed URL with `?api=http://127.0.0.1:8000`, or by setting `VITE_API_BASE_URL` (see below).

If nothing is reachable yet, the dashboard doesn't sit blank: it opens instantly on bundled mock snapshots
(`src/mocks/`) with a **DEMO DATA** badge, and switches over automatically the moment a real backend answers.
Set `DEMO_ENABLED = false` in `src/config.ts` (or delete `src/mocks/`) once you don't want that fallback.

The demo shift starts at 06:00 and runs at 2 simulated minutes per second. All shift timing is driven by the
backend's simulated clock (`snapshot.clock`) — the frontend renders it, it doesn't compute it.

### Claude

The chat copilot and handover use the Claude API when credentials resolve (`ANTHROPIC_API_KEY`, an auth token,
or an `ant auth login` profile). Without credentials the app runs in **offline mode**: rule-based answers and a
template handover; everything else works the same.

| Variable | Default | Purpose |
|---|---|---|
| `SHIFTLOOP_CHAT_MODEL` | `claude-sonnet-5` | chat copilot |
| `SHIFTLOOP_SUMMARY_MODEL` | `claude-haiku-4-5` | shift handover |
| `SHIFTLOOP_OFFLINE=1` | unset | force offline mode |

### Prioritization

Every live incident is re-scored each simulated minute ([central/ranking.py](backend/shiftloop/central/ranking.py)).
A strict tier comes first; the score (0–100) orders incidents within the tier, and each tier owns a 25-point band:

| Tier | Band | What |
|---|---|---|
| 0 Safety | 75–100 | live hazards, fire warden gaps, anything under the safety-stop rule (pinned at 100) |
| 1 Line stoppage | 50–75 | station stopped, starved, uncovered or below takt; tool failure or part run-out within 15 min |
| 2 Quality spill | 25–50 | defect patterns, trainee without sign-off at a safety-critical station, near-miss reports |
| 3 Shift hygiene | 0–25 | forecasts, cover planning, working-time and certification housekeeping |

Within the band: severity (critical 60, high 40, medium 20, low 10) + impact (people exposed, share of line
output lost, defect escape risk; 0–20) + ML risk × 20 + aging (+2 per minute active without a decision, max +20).
At most three medium-or-higher incidents are *active*; an active one keeps its slot unless a same-tier challenger
beats it by 5 points, so the list does not flicker. Each incident carries `tier`, `priority_reason`,
`score_parts`, `trend` and `waiting_min`, and keeps a history of its priority; `GET /api/priority/timeline`
returns it as bars, score points and markers for the timeline page.

### ML models (random forests)

The backend loads the three random forests from `ml/models/` at startup (see [ml/README.md](ml/README.md)):

| Agent | What the forest adds | When |
|---|---|---|
| Staffing | Which staffed stations may lose qualified cover this shift | shift start, then hourly |
| Assembly | Which zones may miss today's output target | every 30 min |
| Fire & Safety | How serious a reported near miss could have been (Safety page form; one scripted report at 11:10) | on report |

Each prediction carries its drivers and a plain-language explanation. Forecasts reach the inbox only at 80%+
risk; lower ones appear under **Model forecasts** on the Now page. With Claude available, incident cards get an
**Explain with Claude** button. `/api/health` shows whether the models loaded; if they are missing, the agents
run rules-only. `SHIFTLOOP_ML=0` turns the models off; `SHIFTLOOP_ML_DIR` points to another `ml/` folder.

### Vision models

Camera frames can be posted to `POST /api/vision/{camera_id}` (multipart `image`). Each camera purpose has a
detector slot; empty slots return 503 and the simulator's scripted detections are used instead.

| Variable | Slot | Expected |
|---|---|---|
| `SHIFTLOOP_QC_MODEL=module:function` | quality cameras `CAM-QC-Sxx` | `fn(PIL.Image) -> (label, confidence, detail)`; label `ok` or `defect` |
| `SHIFTLOOP_FIRE_MODEL=weights.pt` | fire cameras `CAM-FIRE-x` | YOLO weights with `fire`/`smoke` classes (`uv sync --extra vision`) |
| `SHIFTLOOP_PPE_MODEL=weights.pt` | PPE cameras `CAM-PPE-x` | YOLO weights with `no-helmet`/`no-vest` style classes |

Detections under 50% confidence become *expert review* items instead of defects.

## Deploy on Render (Docker)

The Docker image (`Dockerfile` at the repo root) is the **backend only**: API, WebSocket and ML models.
The dashboard is hosted separately.

**Backend on Render**
1. Push the repository. The trained models in `ml/models/` must be committed; the image copies them.
2. In Render: **New → Blueprint** and pick the repository. `render.yaml` creates a Docker web service with a
   health check on `/api/health`. (Or **New → Web Service**, runtime **Docker**.)
3. Optional: set `ANTHROPIC_API_KEY` for the Claude copilot and explanations.
4. Note the service URL, e.g. `https://shiftloop.onrender.com`. Opening it shows 404 at `/`; that is expected,
   try `/api/health`.

**Dashboard (anywhere that hosts static sites)**
Build it with the backend's URL, then upload the build output:
```bash
cd frontend
VITE_API_BASE_URL=https://shiftloop.onrender.com npm run build
```
The env var is `VITE_API_BASE_URL` (not `VITE_API_URL` — that was the old frontend's name; the rebuilt
dashboard renamed it, so update any deploy scripts or Render dashboard env settings that still reference the
old one). If you skip it entirely, the dashboard already defaults to the hosted `shiftloop.onrender.com`
backend (`DEFAULT_API` in `src/config.ts`), so this variable is now mainly for pointing a build at a *different*
backend (staging, local, etc).

Things to know:
- **One backend instance only.** The factory state lives in memory; each deploy or restart starts the shift again.
- **Free plan sleeps** after 15 minutes without traffic and restarts the shift on the next visit (first request
  takes ~30–60 s). Use a paid plan for a live demo. The backend uses about 180 MB of memory.
- The backend accepts requests from any origin (CORS `*`), which suits a demo; restrict it before real use.
- Locally: `docker build -t shiftloop . && docker run -p 8000:8000 shiftloop`.

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
```

The rebuilt frontend doesn't have a `test` script wired up yet (no test runner in `package.json`), so the old
`cd frontend && npm test` instruction no longer applies. `npm run lint` (ESLint) is available in the meantime.

## Architecture

![AI for Factories: a central decision-making brain feeds the dashboard and voice alerts; below it, one specialist model per factory function. Staffing, General assembly line and Fire and safety are built in the MVP; Casting, Plastics and Support are later phases.](ai_for_factories_architecture.png)

The design is modular: every factory function gets its own specialist, and the central brain above them stays
the same.

- **One specialist per function.** The MVP covers Staffing, General assembly line and Fire and safety. Casting,
  Plastics and Support are planned as later phases.
- **One shared event format.** Every specialist reports its findings the same way, so adding a function means
  adding one agent. Merging, ranking, recommendations, the dashboard and the voice alerts need no changes.
- **Models can be swapped per function.** A specialist's model can be replaced or upgraded on its own, for
  example a camera model through its detector slot or the random forests through `SHIFTLOOP_ML_DIR`, without
  touching the rest of the system.

In the MVP the specialists use rules, statistics and random forests, and Claude powers the chat copilot and
explanations. The function-specific LLMs in the diagram are the target architecture for later phases.

## Layout

```
backend/shiftloop/
  factory.py, models.py, state.py   layout, roster, domain models, shared state
  agents/                           staffing.py, assembly.py, safety.py (+ base condition tracking)
  central/                          fusion (merge), ranking, recommend (hard rules), engine
  actions.py                        decisions, escalations + reminders, all clear, impact accounting
  matching.py, whatif.py, kpis.py, oversight.py, stats.py
  simulator/shift.py                synthetic signals + scripted demo shift
  plant.py                          simulator to bus to agents to central
  llm/                              Claude chat tool loop, tools, handover, offline fallback
  vision/service.py                 detector slots (team QC model, YOLO fire/PPE)
  api/                              FastAPI app + snapshot
frontend/src/
  config.ts, types.ts               API base resolution (+ demo-mode switch), backend contract mirror
  lib/api.ts, lib/live.tsx          REST client; live state provider - WS + polling fallback + demo mocks
  lib/time.ts, lib/voice.ts         plant-time formatting (relative to snapshot.clock), voice alert reading
  routes/                           file-based pages - index (Now/decisions), line, alerts, people,
                                     oversight, handover, settings
  components/sl/                    AppShell (shell/nav), DecisionCard, ProposalCard, ChangeSheet,
                                     Copilot (chat), Emergency (emergency mode), ReasonDialog, bits
  components/ui/                    shared shadcn/ui primitives
```

Frontend rules the Lovable build follows: never compute business logic client-side (the backend owns decisions,
the frontend renders its order as-is); `types.ts` mirrors the backend contract exactly, no renamed/added fields;
all live state flows through `LiveProvider`. See `AGENTS.md` and `.lovable/plan/` in the frontend for the fuller
rationale and build history behind these choices.

## Assumptions to replace with plant data

Impact numbers (downtime avoided, energy saved, rework avoided) use documented constants in
`backend/shiftloop/actions.py`. Takt is 60 s, breaks are at 09:30 and 12:00 (`central/recommend.py`), and the
working-time limit is 10 h/day (`matching.py`).