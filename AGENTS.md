# QA swarm

This workspace is the QA swarm kernel: remember an external product in git and answer from that memory.

## Roles

- You (this chat) are the coordinator. Follow `.cursor/rules/coordinator.mdc`.
- `hunter` fetches. Output only `memory/<id>/raw/_incoming/`.
- `analyst` reads a task snapshot and Figma. Draft only in `_incoming/requirement.md`.
- `librarian` writes canonical memory. Never calls the product.

## Do not do in v1

Writing tickets, Playwright/e2e, full API dumps, scheduled reindex, RAG, guessing product URLs.

## Spec

`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`

`docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`
