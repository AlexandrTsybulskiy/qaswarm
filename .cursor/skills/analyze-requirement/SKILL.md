---
name: analyze-requirement
description: Analyzes one Upservice task (and Figma link) into a git requirement card. Use when the user says проанализируй задачу, разбери требования, or attaches a spec without a ticket. Does not write to Upservice.
---

# analyze-requirement

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Ticket id present: launch `specifier` with `mode: requirement` and that `task_id`. Spec without ticket: launch `specifier` with `mode: requirement` and the attached spec path. If the Task harness has no `specifier` type, use `generalPurpose` instructed to follow `.cursor/agents/specifier.md` verbatim with `mode: requirement`. Specifier fetches the task when the snapshot is missing, stale, or past TTL; **searches frontend/backend when `code_roots` resolve**; drafts `requirement.md` with `## Implementation status` and `code-trace.md`. If the API has no task: stop after librarian, do not invent.
3. After MANIFEST is complete, launch `librarian` with goals covering every listed file: `task-snapshot` if `task.json` is listed, `code-trace` if `code-trace.md` is listed, then `requirement` if `requirement.md` is listed. One librarian invocation.
4. Report the card path, trace path (if any), implementation summary, testable count, and gaps. Say requirements are ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
5. Never write to Upservice. Do not use browser MCP. Do not treat `entities/tasks.md` as instances.
