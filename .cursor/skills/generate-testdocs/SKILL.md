---
name: generate-testdocs
description: Builds atomic test cases in git from a ready requirement card. Use when the user says сделай тест-доки, тест-кейсы для задачи, or сгенерируй кейсы. Does not write to Upservice or Testmo.
---

# generate-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/requirements/<slug>.md` (ticket id → `task-<id>`). If missing or `status` is not `ready`, stop. Tell the user to run `analyze-requirement` first. Do not start analyst, hunter, or invent Testable text.
3. Launch `scribe` with the requirement path. Scribe writes `_incoming/testdocs.md` without case ids. No Figma, no product API, no Testmo.
4. After MANIFEST lists `testdocs.md`, launch `librarian` with goal `testdoc`. Librarian runs `tools/testdoc_merge.py` (writes `testdocs/<slug>.md`) then `tools/testdoc_csv.py` (writes `testdocs/<slug>.csv`).
5. Report the suite path, CSV path, active count, orphan count, and gaps. Say testdocs are ready only if both files exist and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not use browser MCP or Figma MCP.
