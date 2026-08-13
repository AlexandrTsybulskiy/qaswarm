---
name: recall
description: Answers product questions from QA swarm git memory, citing source and fetched_at. Use when the user asks what an entity is, how the API works, or what the product contains. Fetches only on miss, stale, or expired TTL.
---

# recall

## Steps

1. Resolve `product-id`. Grep/Read `memory/<id>/index.md` and `entities/`.
2. Hit and fresh (`fetched_at` within `ttl_hours`, default 168): answer with source and date. Do not launch hunter. Do not write files.
3. Miss, `status: stale`, or expired TTL: if `_incoming/` not empty, stop. Else one `hunter` task with a single target and allowed ladder (browser only if `mcp.browser` is true and APIs fail). Then `librarian` merge (status `deep` if new detail). Then answer from the file.
4. If channels fail: say memory is missing or only old `fetched_at` exists; what to check in config. Do not present expired data as current.
5. Never quote secrets or `raw/`.
