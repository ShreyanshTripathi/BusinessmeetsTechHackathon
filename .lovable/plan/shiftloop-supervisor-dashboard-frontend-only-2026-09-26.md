# ShiftLoop — Supervisor Dashboard (frontend only)

A calm, severity-driven control screen for a line supervisor. It connects to your existing FastAPI backend, and when no backend is reachable it falls back to demo data. There is no login, no database and no server code.

## Navigation (3 primary places + secondary menu)

```text
[Top bar]  Plant time 10:20 | Live/Reconnecting/DEMO | Voice on/off | Copilot mode | Menu
[Critical banner: unacked critical notification or EMERGENCY -> links back]
Primary tabs:  Decide  |  Line  |  People        (+ Copilot slide-over, always reachable)
Menu (one level down): Oversight, Handover, Notifications log, Expert queue, Demo controls, Backend settings
```

### 1. Decide (home)
The page answers the supervisor's four questions in order:
1. **Danger strip**: open safety count, unacknowledged critical notifications with a large monospace `code`, and Acknowledge.
2. **Decision cards** (up to 3, in the order the backend sends, never re-sorted). Each card shows: action label, where (zone/station shown large), severity colour, the Safety/Quality rule badge, the agent chips (a "cross-function" tag when several agents flag it), confidence % with an "unsure" mark below 60%, summary, assignments, "Will call: …" and the linked notification code. Evidence and the full step list open on tap. The three actions:
   - **Accept**: one tap.
   - **Change**: a sheet where you remove or replace workers. Each replacement runs the what-if check and shows its warnings and benefits. A reason is required.
   - **Dismiss**: a reason is required.
   After each action, a message you can close lists what the backend applied.
3. **Waiting on confirmation**: unconfirmed calls to other teams, with "waiting N min" (counted from plant time), the reminder count and a "Confirmed" button.
4. **Pending copilot proposals**: Confirm / Reject.
5. **In progress** incidents and "N more held back" (both expandable).
6. **Compact KPI row**: cars built vs plan, output %, downtime and its top causes, defects, and "Saved by decisions" for the savings figures present. Also the counter "18,985 signals filtered → 2 decisions".
- When nothing is waiting: "Nothing needs you right now".

### 2. Line
- 4 zone columns (A→D, upstream to downstream), each with 6 station tiles showing: large ID, status, operator or **UNCOVERED**, a trainee/untrained flag, cycle time vs takt, the alert colour and a marker for safety-critical stations.
- Each zone footer shows: headcount, wardens and first aiders ("none" flagged), exits, assembly point, and sensors with value and unit (normal/warning/critical from comparing value to warn/crit).

### 3. People
- A worker list you can filter by zone, status or role. Each worker shows: station, role, hours worked out of 10, busy flag, warden and first-aider badges, qualifications with expiry dates, and languages.
- **What-if panel**: pick a worker + station and see the ok/warnings/benefits. It is labelled "Check only, changes nothing".

### Emergency takeover
- While an emergency is on, the Decide tab becomes the emergency view:
  - zone, reason and elapsed minutes
  - large "accounted X / total"
  - **unaccounted people first**, as big tap targets that check the person in
  - wardens, exits and assembly point
  - "All clear" with a confirm step
- On other tabs, a red banner that stays visible links back to it.
- After All clear, the restart plan (duration, cars to recover, steps) stays in view until you dismiss it.

### Copilot (slide-over)
- Chat history kept in the browser, with EN/DE/PL language selection and starter chips.
- A pending state that allows up to 60 s.
- Proposals appear as cards you confirm or reject, and "offline mode" is shown when the backend reports it.

### Secondary pages
- **Oversight**: decision totals, override %, "100% decided by a human", per-agent stats, the decision log, data use per agent and works-council flags.
- **Handover**: generate in the chosen language, edit, Copy.
- **Demo controls**: play/pause, +15 min, speed 1/2/5/10/30, Reset with confirm. A clear PAUSED state.
- **Backend settings**: current URL, change or clear it, connection state.

### Voice alerts
- A one-tap "Enable voice alerts" prompt on first use; the choice is remembered in the browser.
- A mute toggle and a Test voice button.
- New warning and critical alerts are spoken once. Critical alerts repeat every 60 s until acknowledged.
- Announcements are queued (critical ones jump the queue) and never talk over each other.
- Notifications from before the first update are never announced.

## Visual direction
- Dark neutral slate background with high-contrast off-white text.
- Colour only for severity: red for critical, orange for high, amber for medium.
- Large condensed font for IDs, times and counts (e.g. Barlow Condensed + IBM Plex Mono for codes) and clean sans body text.
- Touch targets of at least 44px, laid out for tablet landscape first and scaling up to desktop.

## Technical details
- The project runs on TanStack Start (the template), used here as a React/Vite app. Only the client side is used; no server functions and no Cloud.
- Files:
  - `src/types.ts` (spec types exactly, plus `code`/`spoken` on Notification)
  - `src/config.ts` (API base resolution: ?api → localStorage → env → ""; WS URL derivation)
  - `src/lib/api.ts` (fetch wrappers for only the listed endpoints; `{detail}` → toast; 60 s timeout for chat/handover)
  - `src/lib/live.tsx` (context: WS with 1.5 s reconnect, 3 s polling while down, 5 s demo fallback, auto-switch to live, refetch snapshot after each POST)
  - `src/lib/voice.ts` (speechSynthesis queue)
  - `src/lib/time.ts` (HH:MM slice, minutes relative to `snapshot.clock`)
  - `src/mocks/snapshot_start.json`, `src/mocks/snapshot_emergency.json` (placeholders built from section 7 that match the types)
- Routes: `/` (Decide/Emergency), `/line`, `/people`, `/oversight`, `/handover`, `/settings` (includes demo controls). Each route gets its own head metadata.
- Demo mode: action buttons are disabled with the tooltip "Connect a backend to act", and a start/emergency toggle is available.
- Workers and oversight data are fetched when their page opens and again when the plant clock changes.
- Other rules: no ranking or business logic on the client, and every nullable field is guarded.
- The GitHub repo connection is not used by this dashboard.
