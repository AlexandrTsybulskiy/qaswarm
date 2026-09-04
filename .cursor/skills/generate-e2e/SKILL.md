---
name: generate-e2e
description: Maps and runs Playwright UI tests for one testdoc suite via an external Playwright repo, storing map and verdict in git memory. Use when the user says сделай e2e, прогони playwright, or e2e для задачи. Does not write to Upservice or Testmo.
---

# generate-e2e

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/testdocs/md/<slug>.md` (ticket id → `task-<id>`). If missing or there is no UI-classifiable `active` case, stop. Tell the user to run `generate-testdocs` first. Do not start specifier/verifier or invent cases from chat. Use `tools/e2e_scan.classify_channel_class` (or the same rules) to detect UI-active.
3. Load `products/<id>/config.yaml`. Resolve playwright root via `tools/e2e_scan.resolve_playwright_root`. If none, stop and ask for `playwright.root_env` / `playwright.root`.
4. Launch `e2e-builder` with testdoc path, product id, playwright root, optional `run_command`. If the Task harness has no `e2e-builder` type, use `generalPurpose` instructed to follow `.cursor/agents/e2e-builder.md` verbatim. Builder writes `_incoming/` only.
5. After MANIFEST lists `e2e.md`:
   - If MANIFEST also lists `e2e-run.md`, launch `librarian` with goal covering both `e2e` and `e2e-run` (map first, then run).
   - If only `e2e.md`, launch `librarian` with goal `e2e` (draft map only).
6. Report paths, missing/written counts, and pass/fail/blocked/skipped if run exists. Say e2e is ready only if `e2e/<slug>.md` has `status: ready`, `e2e-runs/<slug>.md` exists, and `py -3 tools/memory_schema.py memory/<id>` would pass.

   If map is `draft` because UI cases are `map_status: missing`, report missing tc-ids and reasons from `## Gaps` (see `.cursor/reference/e2e-gaps-patterns.md`). Do not claim full e2e readiness.

   For date/TZ-sensitive suites, note that first pytest run should use single worker (`-n 1`) from playwright root.

7. Never write to Upservice or Testmo. Do not modify `runs/`. Do not start generate-testdocs, analyze-requirement, or verify-testdocs from this skill.
