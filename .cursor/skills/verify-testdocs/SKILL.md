---
name: verify-testdocs
description: Runs one testdoc suite against the live product via browser MCP or HTTP and stores the verdict in git. Use when the user says проверь сюит, прогони кейсы, or verify testdocs. Does not write to Upservice or Testmo.
---

# verify-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/testdocs/md/<slug>.md` (ticket id → `task-<id>`). If missing or there is no `status: active` case, stop. Tell the user to run `generate-testdocs` first. Do not start specifier, hunter, or invent cases from chat.
3. Launch `verifier` with the testdoc path. Verifier writes `_incoming/run.md` with ids and verdicts. No Figma, no Upservice write, no Testmo, no canonical `runs/`.
4. After MANIFEST lists `run.md`, launch `librarian` with goal `run`. Librarian inserts `status: ready`, overwrites `runs/<slug>.md`, updates `runs/index.md`. If incoming ids ≠ testdoc `active` set, librarian writes nothing.
5. Report the run path, pass/fail/blocked/skipped counts, and whether `smoke_gate` tripped. Say the run is ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not start generate-testdocs or analyze-requirement from this skill.
