---
name: analyze-requirement
description: Analyzes one Upservice task (and Figma link) into a git requirement card. Use when the user says проанализируй задачу, разбери требования, or attaches a spec without a ticket. Does not write to Upservice.
---

# analyze-requirement

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Ticket id present: look for `memory/<id>/tasks/task-<task-id>.md`. Missing, stale, or expired TTL: launch `hunter` with `kind: task` and that `task_id`. Then `librarian` with goal `task-snapshot`. Do not start `analyst` before that file exists. If the API has no task: stop, do not invent.
3. Launch `analyst` with the snapshot path (or the attached spec). Analyst uses Figma MCP only for URLs in the snapshot.
4. After MANIFEST lists `requirement.md`, launch `librarian` with goal `requirement`.
5. Report the card path, testable count, and gaps. Say requirements are ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice. Do not use browser MCP. Do not treat `entities/tasks.md` as instances.
