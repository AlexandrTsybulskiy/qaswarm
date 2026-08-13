---
name: index-system
description: Builds a map of the external product (API catalog, short entity cards, gaps) into git memory. Use when the user says запомни систему, index the system, build the product map, or refresh the catalog of resources.
---

# index-system

## Steps

1. Resolve the single `product-id` under `products/`. If missing, stop and ask for `id` + `public_api.base_url`. Do not invent the host. Offer copying `docs/examples/product-config.yaml`.
2. If `memory/<id>/raw/_incoming/` is not empty, stop (lock).
3. Launch subagent `hunter` with written task: mode `index-system`, product-id, allowed channels public then internal if configured, browser forbidden.
4. After Hunter: `_incoming/MANIFEST.md` must exist. Launch `librarian` with goal `index`. Librarian must not downgrade `deep` cards.
5. Read `index.md` and `gaps.md`. Report entity count, gaps, file paths.
6. Forbidden success phrase if schema would fail: do not say the system is remembered. Run `python tools/memory_schema.py memory/<id>` or equivalent Read of frontmatter.

Map only: no record dumps, no browser crawl.
