# Simplify the ShiftLoop supervisor dashboard

## Direction
Use the selected **Direct action hierarchy** composition: one dominant decision area with a narrow, visually separate status rail. Keep the chosen **Paper & charcoal** palette and **Archivo Black / Hind** typography, rather than the prototype’s unrelated blue accents and invented workforce metrics. Preserve red, orange, and amber solely for actual severity.

## Changes
1. Remove the “No one in danger right now” statement. The current page derives it from `kpis.open_safety === 0`, which reports an issue count but cannot establish that nobody is in danger. Show a prominent safety state only when the backend reports an emergency, an open safety issue, or a critical notification; otherwise leave safety claims out of the main view.
2. Recompose Decide so the first backend-ranked active incident dominates the page: large zone/station and event, clear recommendation, then Accept / Change / Dismiss. Keep the complete recommendation, assignments, escalations, confidence, evidence, and other backend-ranked incidents accessible through expansion or a quieter continuation below; do not reorder incidents.
3. Put unconfirmed calls and a compact line-versus-plan summary in the separate rail. Move in-progress work, copilot proposals, and secondary shift details out of the initial visual competition while keeping their actions reachable.
4. Improve legibility across the shared header and decision view: larger text where supervisors scan, less condensed typography, fewer simultaneous labels and borders, generous touch targets, and a clean light surface. Keep the demo badge, connection state, emergency takeover, critical notification banner, and existing live behavior intact.
5. Check the normal and emergency demo scenarios at desktop and tablet widths, and verify that safety wording never overclaims, actions remain available as designed, and no content overlaps.

## Technical notes
Frontend presentation only. Use the existing backend fields and their given ordering; no new endpoints, calculations, or fabricated safety status. Update semantic color/font tokens and matching UI styles without changing the backend contract. The prototype supplies layout hierarchy, not its sample data or invented features.
