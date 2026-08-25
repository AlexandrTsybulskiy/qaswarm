# QA swarm

This workspace is the QA swarm kernel: remember an external product in git and answer from that memory.

## Roles

- You (this chat) are the coordinator. Follow `.cursor/rules/coordinator.mdc`.
- `hunter` fetches. Output only `memory/<id>/raw/_incoming/`.
- `analyst` reads a task snapshot and Figma. Draft only in `_incoming/requirement.md`.
- `scribe` reads a ready requirement card. Draft only in `_incoming/testdocs.md`.
- `verifier` executes one testdoc suite via browser MCP or HTTP. Draft only in `_incoming/run.md`.
- `e2e-builder` maps/writes/runs Playwright UI tests in an external repo. Draft only in `_incoming/e2e.md` and `_incoming/e2e-run.md`.
- `librarian` writes canonical memory. Never calls the product.

## Do not do in v1

Writing tickets; a Playwright suite inside this repo; full API dumps; scheduled reindex; RAG; guessing product URLs. Orchestrated `generate-e2e` against an external Playwright root is allowed.

## Spec

`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`

`docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`

`docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`

`docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`

`docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md`

`docs/superpowers/specs/2026-08-18-qa-swarm-upservice-get-task-mcp-design.md`

`docs/superpowers/specs/2026-08-18-qa-swarm-upservice-entity-mcp-tools-design.md`

`docs/superpowers/specs/2026-08-19-qa-swarm-testdocs-md-csv-folders-design.md`

`docs/superpowers/specs/2026-08-25-qa-swarm-playwright-e2e-design.md`
