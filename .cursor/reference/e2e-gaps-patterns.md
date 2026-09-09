# E2E gaps patterns — qaswarm reference

Patterns for `e2e-builder` when drafting `_incoming/e2e.md` and for the `## Gaps` section on canonical `memory/<id>/e2e/<slug>.md`.

**Canonical example:** `memory/upservice/e2e/task-5228268.md` (Week Plan widget).

Implementation details (PO, fixtures, scroll code) live in the **Playwright repo** under `<playwright.root>/.cursor/` — qaswarm documents *what was decided*, not duplicate algorithms.

## Pattern table

| Pattern | e2e-builder action | Document in `## Gaps` | Playwright repo |
|---------|-------------------|----------------------|-----------------|
| **Virtuoso / virtual scroll** | Search frontend for `Virtuoso`, `customScrollParent`. Implement scroll on Widget PO, not in tests. | «List uses Virtuoso; scroll via PO per reference» | `.cursor/reference/virtuoso-scroll.md` |
| **ISO week / TZ-sensitive** | Dynamic due dates in module seed; `pytest.skip` for calendar edges (e.g. Sunday → Tomorrow). | Skip rules and TZ assumption (browser local) | Neighbor `*_helpers.py` + module `conftest.py` |
| **EN UI on staging** | Assert EN labels or regex when staging locale is EN; testdoc may be RU. | «Dashboard chrome EN; widget title/badges EN\|regex» | Test asserts, not qaswarm |
| **Celery / async list row** | After message/mention/inbound, poll confirmed list API before dashboard UI assert. | Poll endpoint + lag note if internal-only | `.cursor/reference/dashboard-widgets.md` |
| **Preview list cap** | Assert badge/list matrix in View-all / modal when preview shows N rows. | «Preview limit N; asserts in modal» | Widget PO `open_view_all_modal` |
| **Visual-only case** | `map_status: missing` + `reason:` — scrollbar thickness, decorative SVG icon. | Bullet per missing tc-id with reason | Do not add fragile CSS asserts |
| **Heavy multi-case suite** | One module-scoped seed dataclass; one test file; `@pytest.mark.qaswarm_tc` per case; parametrize kind/badge variants. | Seed scope and shared fixture name | `tests/<domain>/<feature>/conftest.py` |
| **Same seed, two tc-ids** | One test may carry **multiple different** `@pytest.mark.qaswarm_tc` when one assert covers two atomic cases (e.g. Contact badge + entity-is-contact). | Note dual markers on that nodeid | Allowed; scan binds each tc-id once |
| **Task kind API seed** | agreement / acquaintance / meeting / ticket / lead / asset — kind-specific factory kwargs. | Only if non-obvious (PATCH dateEnd, ticket flags) | `build-api-precondition` skill in playwright |
| **Product bug suspected** | `blocked` or `fail` in e2e-run with evidence; do not silent `xfail`. | Reproduction note | Playwright test + optional bug skill |
| **Duplicate qaswarm_tc markers** | Same **tc-id** on two nodeids → fix before re-scan; `e2e_scan.py` exit 2 | «Unblocked scan by deduping markers on …» | One binding per tc-id |

## `map_status: missing` — when allowed

Use for UI-`active` testdoc cases that should **not** get an automated test in v1:

```markdown
### tc-5228268-31
title: Вертикальная прокрутка
channel_class: ui
map_status: missing
reason: pure visual (Virtuoso scrollbar thinness); fragile CSS/style asserts avoided
```

Do **not** write `e2e-run.md` while any UI-`active` case remains `missing` (map may be `draft`).

## `## Gaps` — what to include

Always include the Upservice/Testmo notice (see `fixtures/demo-e2e/incoming/`).

Bullets should capture **decisions the next agent cannot infer from code alone**:

- Virtuoso / virtual list behaviour
- Celery/async poll before UI; preview cap → modal asserts
- Locale (EN vs RU) assumptions on staging
- API seed quirks (PATCH after create, factory flags)
- Intentionally missing visual cases (tc-id + reason)
- Dual `qaswarm_tc` on one nodeid (allowed) vs duplicate same tc-id (forbidden)
- Scan blockers fixed (duplicate markers)
- Product gaps discovered during run (with tc-id)

Do **not** paste full PO scroll algorithms — link playwright reference path instead.

## Cross-repo read order (e2e-builder)

1. Testdoc `memory/<id>/testdocs/md/<slug>.md`
2. Requirement / trace if present (`requirements/`, `traces/`)
3. Frontend search for component + Virtuoso
4. `<playwright.root>/.cursor/skills/` (`write-e2e-test`, …)
5. `<playwright.root>/.cursor/reference/` (e.g. `virtuoso-scroll.md`, `dashboard-widgets.md`)
6. Neighbor test suite in playwright root (same domain folder)

## Coordinator reporting

When librarian writes `e2e/<slug>.md` with `status: draft` because UI cases are `missing`:

- Report missing count and reasons from `## Gaps`
- Do not claim «e2e ready» until `status: ready` **and** `e2e-runs/<slug>.md` exists

For date-sensitive suites, suggest first run: `run-tests.py <path> -n 1` from playwright root.
