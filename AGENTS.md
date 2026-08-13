# QA swarm

This workspace is the QA swarm kernel: remember an external product in git and answer from that memory.

## Roles

- You (this chat) are the coordinator. Follow `.cursor/rules/coordinator.mdc`.
- `hunter` fetches. Output only `memory/<id>/raw/_incoming/`.
- `librarian` writes canonical memory. Never calls the product.

## Do not do in v1

Test plans, tickets, Playwright/e2e, full API dumps, scheduled reindex, RAG, guessing product URLs.

## Spec

`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
