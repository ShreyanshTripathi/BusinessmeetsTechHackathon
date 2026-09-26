# Connect ShiftLoop to the live backend and report issues

The backend at https://shiftloop.onrender.com is reachable. The AI runs inside the backend, and there is no database. That setup stays as it is for the MVP.

## Steps
1. **Make the live backend the default.** The app opens on the Render URL, so nobody needs to add `?api=`. Demo data only shows if the backend can't be reached. The switch that turns demo mode off stays in one place.
2. **Save real samples.** Record real responses from health, snapshot, workers and oversight at several plant times: start, mid-shift, during the emergency and after the emergency. The sim is advanced only through the existing sim endpoint, and then reset to paused at the start of the demo shift.
3. **Compare every field against the frontend contract.** Check each field for missing keys, extra keys, wrong types, unexpected empty (null) values and enum values the UI doesn't handle. One extra field is already visible: `ml` on health (staffing, assembly and safety models loaded; the vision models aren't loaded).
4. **Map the data onto every page:** Decide, Line, People, Alerts, Handover, Record and Emergency. Each thing on screen gets its data straight from the backend. Nothing is guessed on the client. The Line and People pages show exactly what the backend's AI sends.
5. **Check live behaviour.** Test the live updates connection, the fallback to regular refreshing, and each action (accept, change, dismiss, acknowledge, confirm a call, what-if, check-in, all clear, chat, handover, proposals). Each action's confirmation must match the backend's reply.
6. **Report the issues in a strict list.** Each entry states:
   - **What** is missing or doesn't match
   - **Where**: which endpoint and field, and which page
   - **How** it affects the supervisor
   - **Fix**: whether the change belongs in the backend or the frontend

## Out of scope
- No database, no login and no new endpoints.
- No business logic on the client.
- Fields the frontend contract doesn't list aren't added unless you approve them after reading the issue list.
