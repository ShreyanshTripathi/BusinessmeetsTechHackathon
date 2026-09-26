<!-- LOVABLE:BEGIN -->
> [!IMPORTANT]
> This project is connected to [Lovable](https://lovable.dev). Avoid rewriting
> published git history — force pushing, or rebasing/amending/squashing commits
> that are already pushed — as it rewrites history on Lovable's side and the
> user will likely lose their project history.
>
> Commits you push to the connected branch sync back to Lovable and show up in
> the editor, so keep the branch in a working state.
<!-- LOVABLE:END -->

# ShiftLoop frontend rules

- Frontend only, talking to an external FastAPI backend (`src/lib/api.ts`, `src/config.ts`). Why: the backend is final; no Cloud or server functions.
- `src/types.ts` mirrors the backend contract exactly; never rename or add fields. Why: hard integration rule.
- All live state flows through `LiveProvider` (`src/lib/live.tsx`): WS + polling fallback + demo mocks. Why: single source of truth for snapshot, actions and voice.
- Never rank, score or compute business logic on the client; render backend order. Why: the backend owns decisions.
- Time is plant time: use `src/lib/time.ts` (relative to `snapshot.clock`, no timezone conversion). Why: simulated clock.
- Colour tokens `critical`/`high`/`medium` are for severity only. Why: calm-by-default design.
- Keep the Decide page decision-first with an independent status rail and never infer that people are safe from a zero issue count. Why: supervisors need a trustworthy first glance.
