# qaswarm

Cursor-native QA swarm kernel: map an external product into git memory and answer from that memory.

## What this is

Coordinator (this repo's chat) + `hunter` + `analyst` + `scribe` + `librarian`. Not a test runner. Not a ticket bot.

## Setup

1. Python 3.11+
2. `python -m pip install pytest ruff`
3. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`
4. Put API tokens in `products/<product-id>/.env` or Cursor MCP. Never commit them.
5. Open this folder as the Cursor workspace.
6. Connect Figma MCP in Cursor to analyze task design links.

## Commands (natural language)

- «Запомни систему» → skill `index-system` (API map, not a data dump)
- A question about an entity → `recall`
- «Обнови user» → `refresh`
- «Проанализируй задачу 1842» → skill `analyze-requirement`
- «Сделай тест-доки для 1842» → skill `generate-testdocs`

## Checks

```powershell
python -m pytest tests/test_memory_schema.py -v
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
7. Testdocs from ready requirements: `testdocs/task-<id>.md` has one active case per Testable arrow, a checklist of those ids, schema `OK`; Upservice and Testmo are not called.
8. Testdocs without a ready card: stop; `_incoming` stays empty; no testdocs file is created.
9. Testdocs repeat: same `action`+`expected` keeps the id; new text gets `next_id`; unmatched old cases become `orphan` and drop off the checklist.

Spec: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`

Requirements analysis spec: `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`

Test documentation spec: `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`
