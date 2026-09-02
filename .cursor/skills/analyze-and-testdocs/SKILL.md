---
name: analyze-and-testdocs
description: Analyzes one Upservice task (and Figma) into a requirement card and atomic test cases in one pass. Use when the user says разбери задачу и сделай кейсы, требования и тест-доки для задачи, or full pipeline for one ticket. Does not write to Upservice or Testmo.
---

# analyze-and-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Ticket id present: launch `specifier` with `mode: full` and that `task_id`. Spec without ticket: launch `specifier` with `mode: full` and the attached spec path. If the Task harness has no `specifier` type, use `generalPurpose` instructed to follow `.cursor/agents/specifier.md` verbatim with `mode: full`. Specifier **searches frontend/backend when `code_roots` resolve** before drafting requirements and testdocs.
3. After MANIFEST is complete, launch `librarian` with goals covering every listed file: `task-snapshot` if `task.json` is listed, `code-trace` if `code-trace.md` is listed, then `requirement` if `requirement.md` is listed, then `testdoc` if `testdocs.md` is listed. One librarian invocation.
4. If `task.json` had fetch errors (empty title, non-empty `errors`): stop after librarian task-snapshot failure; do not claim testdocs are ready.
5. Report requirement path, trace path (if any), implementation summary, testable count, suite path, CSV path, active count, and gaps. Say the pipeline is ready only if canonical files exist and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not use browser MCP.

## When requirement is draft only

Specifier writes only `requirement.md` and optional `code-trace.md` (no `testdocs.md`). Librarian writes requirements/traces only. Tell the user testdocs were skipped because the requirement is not `ready`; fix gaps and run `generate-testdocs`.
