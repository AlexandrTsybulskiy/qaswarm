# qaswarm

Cursor-native QA swarm kernel: map an external product into git memory and answer from that memory.

## What this is

Coordinator (this repo's chat) + `hunter` + `librarian`. Not a test runner. Not a ticket bot.

## Setup

1. Python 3.11+
2. `python -m pip install pytest ruff`
3. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`
4. Put API tokens in `products/<product-id>/.env` or Cursor MCP. Never commit them.
5. Open this folder as the Cursor workspace.

## Commands (natural language)

- «Запомни систему» → skill `index-system` (API map, not a data dump)
- A question about an entity → `recall`
- «Обнови user» → `refresh`

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

Spec: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
