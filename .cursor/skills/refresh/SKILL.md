---
name: refresh
description: Marks selected memory cards stale and re-fetches them into git. Use when the user says обнови, refresh X, or update the map. Deep cards update only if listed or the user said including deep.
---

# refresh

## Steps

1. Resolve `product-id` and the target: one slug, several slugs, or all map cards. `deep` only if listed or user said including deep.
2. If `_incoming/` not empty, stop.
3. Launch `librarian` with goal `mark-stale` and the slug list.
4. Launch one `hunter` with mode `refresh`; never invent a second parallel Hunter:
   - One slug: one targeted fetch. Browser only if `mcp.browser` is true and APIs fail.
   - Multiple slugs or all map cards: one catalog map pass like `index-system` (public, then internal if needed). Browser is forbidden on this catalog pass.
   Then launch `librarian` merge.
5. Answer from updated canonical files with new `fetched_at`.
6. Refresh-all in v1 = re-run catalog + map cards (same as index-system plus stale mark on those map cards), not a silent wipe of `deep`.
