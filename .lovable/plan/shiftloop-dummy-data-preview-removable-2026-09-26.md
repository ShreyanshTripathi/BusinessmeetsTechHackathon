# ShiftLoop — dummy data preview (removable)

## Goal
Let you explore the full UI/UX now on realistic dummy data, with a clean single switch to remove it once the real backend is hosted.

## Current state
- The app already falls back to demo mode: if no backend answers within 5 seconds, it shows mock snapshots with a yellow "DEMO DATA" badge and a Start / Emergency scenario switch.
- Two mock snapshot files exist (start + emergency) with placeholder data I invented from your examples.

## What I'll do
1. **Make demo the instant default** — open straight into demo data (no 5-second wait) so the look and feel is immediate; live connection still takes over automatically when a backend is reachable.
2. **Enrich the dummy data** — flesh out both scenarios (stations, workers, notifications, expert queue, copilot suggestions, shift timeline) so every panel, page and severity state is visibly exercised, including one critical alert for voice/queue testing.
3. **Single removal switch** — centralise all mock data behind one flag in `src/config.ts` (e.g. `DEMO_ENABLED`). When your backend is hosted, flipping that one flag (or deleting the two mock files) removes every trace of dummy data; no other code changes needed.
4. **Verify visually** — drive the preview in a test browser across the main pages and both scenarios, confirming the demo badge shows and nothing errors.

## Technical notes
- Mock files stay in `src/lib/` (or `src/data/`), typed against the exact backend contract in `src/types.ts` — no field renames.
- No client-side business logic added; dummies only feed the existing rendering path.
- Nothing is persisted; the flag is compile-time, so production builds can exclude mocks entirely.
