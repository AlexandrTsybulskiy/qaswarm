# qaswarm

Cursor-native QA swarm kernel: map an external product into git memory and answer from that memory.

## What this is

Coordinator (this repo's chat) + `hunter` + `analyst` + `scribe` + `verifier` + `e2e-builder` + `librarian`. Live MCP checks write git `runs/`. Playwright e2e is orchestrated into an external repo (`generate-e2e` → `e2e/` + `e2e-runs/`). Not a ticket bot.

## Setup

1. Python 3.11+
2. `python -m pip install pytest ruff`
3. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`
4. Put API tokens in `products/<product-id>/.env` or Cursor MCP. Never commit them.
5. Open this folder as the Cursor workspace.
6. Connect Figma MCP in Cursor to analyze task design links.
7. Copy `docs/examples/mcp.json` into `.cursor/mcp.json` (gitignored) so Hunter can call Upservice GET MCP tools (`get_task`, `get_project`, `list_employees`, …). Reload MCP in Cursor. Token stays in `products/upservice/.env`, not in mcp.json.

## Commands (natural language)

- «Запомни систему» → skill `index-system` (API map, not a data dump)
- A question about an entity → `recall`
- «Обнови user» → `refresh`
- «Проанализируй задачу 1842» → skill `analyze-requirement`
- «Сделай тест-доки для 1842» → skill `generate-testdocs`
- «Проверь сюит 1842» → skill `verify-testdocs`
- «Сделай e2e для 1842» → skill `generate-e2e` (needs `playwright.root` / `root_env` in product config)

## Checks

```powershell
python -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py tests/test_e2e_scan.py tests/test_get_task_mcp.py tests/test_entity_mcp.py -v
python tools/memory_schema.py fixtures/demo-catalog/expected
python tools/memory_schema.py memory/<product-id>
```

## Acceptance (spec)

1. Map: after index, cards exist with `status: map`, `source`, `fetched_at`; no secrets; coordinator lists gaps.
2. Recall hit: second question about a known entity does not launch hunter; answer cites source and date.
3. Recall miss: one targeted fetch; one new/updated card; no second hunter while `_incoming/` is busy.
4. Requirement with Figma: `task-<id>.md` records `source_design: figma`, the URL, action→expected-result items, and does not change Upservice.
5. Requirement without design: the card records `source_design: none`, a design gap, and only requirements supported by the task text.
6. Requirement repeat: analyzing the same task id merges into the same file and does not create a second slug.
7. Testdocs from ready requirements: `testdocs/md/task-<id>.md` has one active case per Testable arrow, a checklist of those ids, `testdocs/csv/task-<id>.csv` with those active rows, schema `OK`; Upservice and Testmo are not called.
8. Testdocs without a ready card: stop; `_incoming` stays empty; no testdocs file is created.
9. Testdocs repeat: same `action`+`expected` keeps the id; new text gets `next_id`; unmatched old cases become `orphan` and drop off the checklist.
10. Verify from testdocs: `runs/task-<id>.md` has one result per `active` case, schema `OK`; Upservice and Testmo are not called.
11. Verify without testdocs: stop; `_incoming` stays empty; no runs file is created.
12. Smoke gate and repeat: non-pass smoke skips the rest with `skipped` / `smoke-gate`; a second run overwrites the same `runs/<slug>.md`.

Spec: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`

Requirements analysis spec: `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`

Test documentation spec: `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`

MCP verification spec: `docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`

Testmo CSV export spec: `docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md`

Upservice get_task MCP spec: `docs/superpowers/specs/2026-08-18-qa-swarm-upservice-get-task-mcp-design.md`

Upservice entity GET/list MCP spec: `docs/superpowers/specs/2026-08-18-qa-swarm-upservice-entity-mcp-tools-design.md`
