---
name: trace-code
description: Finds where a feature is implemented in frontend/backend repos and optionally saves a trace card in git memory. Use when the user asks где реализовано, найди в коде, сверь с кодом, trace implementation, or how does X work in the codebase.
---

# trace-code

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Run `py -3 tools/code_roots.py products/<id>`. If both roots missing, stop and ask to fix `code.frontend` / `code.backend` in config or open `upservice.code-workspace`.
3. Launch `tracer` with `product-id` and:
   - `task_id` / `slug` when the user named a ticket or requirement;
   - `question` when the ask is free-form;
   - optional requirement path from `memory/<id>/requirements/`.
   If the Task harness has no `tracer` type, use `generalPurpose` instructed to follow `.cursor/agents/tracer.md` verbatim.
4. After MANIFEST lists `code-trace.md`, launch `librarian` with goal `code-trace`. One librarian invocation.
5. Answer from the trace card (or tracer report if librarian failed): cite `backend:…` / `frontend:…` paths. Cross-reference requirement Testable items when a slug was given.
6. Do not write to product repos. Do not start `index-system` or `analyze-requirement` unless the user asked separately.

Persisted path: `memory/<id>/traces/<slug>.md` (overwrites same slug).
