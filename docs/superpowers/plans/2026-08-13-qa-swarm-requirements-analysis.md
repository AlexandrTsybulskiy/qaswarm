# QA Swarm Requirements Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить контур анализа: задача Upservice (+ Figma MCP) → каноническая карточка требований в git-памяти, без записи в продукт.

**Architecture:** Координатор запускает Hunter только если нет свежего `memory/<id>/tasks/task-<task-id>.md`, затем Analyst (Figma MCP, не API), затем Librarian пишет `requirements/`. Схема расширяет `tools/memory_schema.py`. Существующая карта сущностей не ломается.

**Tech Stack:** Cursor agents/skills/rules, Markdown/YAML память, Python 3.11+ stdlib, pytest/ruff, Figma MCP. Без HTTP-клиента в репо.

## Global Constraints

- В Upservice агенты не пишут.
- Задачи грузит Hunter, не отдельный Task Retriever.
- Analyst не вызывает Upservice API и не пишет канон.
- Hunter не открывает Figma и не пишет requirements.
- Librarian не ходит в продукт и не в Figma.
- Координатор не пишет `memory/`.
- Замок: непустой `raw/_incoming/`.
- `entities/tasks.md` не список инстансов; снимок — `tasks/task-<id>.md`.
- Slug задачи/требования с id: `task-<id>` (`[a-z0-9-]+`).
- Frontmatter: одна строка `ключ: значение`; списки через запятую.
- `fetched_at`: ISO-8601 со смещением.
- `requirements/` может отсутствовать — дерево ядра валидно.
- Browser MCP в этом контуре не используется.
- На этом хосте CLI: `py -3`, не `python`.
- Не делать: пакетный спринт, тест-доки, e2e, запись в тикет.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/memory_schema.py` | `validate_requirement_card`, `validate_task_snapshot`, дерево с optional `tasks/` и `requirements/` |
| `tests/test_memory_schema.py` | Регрессии ядра + новые тесты |
| `fixtures/demo-requirement/` | Эталон incoming + expected requirements |
| `.cursor/agents/hunter.md` | Incoming `task.json` для одного id |
| `.cursor/agents/librarian.md` | Канон `tasks/` и `requirements/` |
| `.cursor/agents/analyst.md` | Новый субагент |
| `.cursor/skills/analyze-requirement/SKILL.md` | Поток команды |
| `.cursor/rules/coordinator.mdc` | Маршрутизация analyze-requirement |
| `AGENTS.md`, `README.md` | Роль analyst и команда |

---

### Task 1: Схема требований и снимков задачи

**Files:**
- Modify: `tools/memory_schema.py`
- Modify: `tests/test_memory_schema.py`
- Create: `fixtures/demo-requirement/incoming/requirement.md`
- Create: `fixtures/demo-requirement/incoming/MANIFEST.md`
- Create: `fixtures/demo-requirement/expected/requirements/index.md`
- Create: `fixtures/demo-requirement/expected/requirements/task-1.md`
- Create: `fixtures/demo-requirement/expected/tasks/task-1.md`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `parse_frontmatter`, `validate_card`, `validate_memory_tree`, `incoming_complete`
- Produces:
  - `REQ_STATUSES = {"draft", "ready", "stale"}`
  - `validate_requirement_card(path: Path) -> list[str]`
  - `validate_task_snapshot(path: Path) -> list[str]`
  - `validate_memory_tree` also validates `tasks/task-*.md` and `requirements/task-*.md` when those dirs exist; missing dirs are not errors
  - Hunter task incoming: `_incoming/task.json` with `kind: "task"`, `channel`, `fetched_at`, `task_id`, `title`, `fields` (object), `figma_urls` (list of strings), `errors` (list)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_schema.py` (keep all existing tests unchanged):

```python
REQ_INCOMING = ROOT / "fixtures" / "demo-requirement" / "incoming"
REQ_EXPECTED = ROOT / "fixtures" / "demo-requirement" / "expected"


def test_demo_catalog_tree_still_valid_without_requirements() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_requirement_card_valid() -> None:
    card = REQ_EXPECTED / "requirements" / "task-1.md"
    assert memory_schema.validate_requirement_card(card) == []


def test_requirement_ready_without_arrow_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "status: ready\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\n- no expected result\n\n## Gaps\n\n- none\n\n"
        "Did not write to Upservice.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("Testable" in e or "arrow" in e.lower() for e in errors)


def test_requirement_slug_must_match_task_id(tmp_path: Path) -> None:
    card = tmp_path / "task-9.md"
    card.write_text(
        "---\nslug: task-9\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "status: draft\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\n## Gaps\n\n- no design\n\n"
        "Did not write to Upservice.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("task_id" in e or "slug" in e for e in errors)


def test_task_snapshot_requires_task_id(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Task 1\nstatus: deep\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\nA task.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_task_snapshot(card)
    assert any("task_id" in e for e in errors)


def test_demo_requirement_incoming_complete() -> None:
    assert memory_schema.incoming_complete(REQ_INCOMING) is True
```

- [ ] **Step 2: Run tests to verify new ones fail**

```powershell
py -3 -m pytest tests/test_memory_schema.py -v
```

Expected: existing 12 tests PASS; new tests FAIL with `validate_requirement_card` / `validate_task_snapshot` missing or fixtures missing.

- [ ] **Step 3: Write fixtures**

`fixtures/demo-requirement/incoming/requirement.md`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
status: ready
source_task: upservice
source_design: figma
fetched_at: 2026-08-13T17:00:00+03:00
figma_urls: https://www.figma.com/design/demo/sprint
entities: sprints
---

Add visible sprint date range on the sprint card.

## Testable

- Open a sprint card → start and end dates are visible
- Open a sprint without dates → date row is hidden

## Gaps

- none

Did not write to Upservice.
```

`fixtures/demo-requirement/incoming/MANIFEST.md`:

```markdown
# Analyst incoming manifest

- requirement.md
```

`fixtures/demo-requirement/expected/requirements/task-1.md` — same body as incoming `requirement.md`.

`fixtures/demo-requirement/expected/requirements/index.md`:

```markdown
# Requirements

| Slug | Task | Status | Card |
|------|------|--------|------|
| task-1 | 1 | ready | [task-1.md](task-1.md) |
```

`fixtures/demo-requirement/expected/tasks/task-1.md`:

```markdown
---
slug: task-1
title: Show sprint dates
status: deep
source: public
fetched_at: 2026-08-13T17:00:00+03:00
product: demo
task_id: 1
---

Upservice task 1. Design: https://www.figma.com/design/demo/sprint

## Fields

Fields are not fully listed in this fixture.

## Relations

None stated by the source.

## Missing

- none
```

- [ ] **Step 4: Implement schema functions**

Add to `tools/memory_schema.py` (do not change entity `REQUIRED_FIELDS` / `STATUSES` behavior):

```python
REQ_REQUIRED = (
    "slug",
    "title",
    "product",
    "task_id",
    "status",
    "source_task",
    "source_design",
    "fetched_at",
    "figma_urls",
    "entities",
)
REQ_STATUSES = {"draft", "ready", "stale"}
SOURCE_TASK_VALUES = {"upservice", "none"}
SOURCE_DESIGN_VALUES = {"figma", "none"}


def validate_task_snapshot(path: Path) -> list[str]:
    errors = validate_card(path)
    meta, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    task_id = meta.get("task_id", "")
    if not task_id:
        errors.append(f"{path}: missing task_id")
    slug = meta.get("slug", "")
    if task_id and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    return errors


def validate_requirement_card(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in REQ_REQUIRED:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in REQ_STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    if meta.get("source_task") and meta["source_task"] not in SOURCE_TASK_VALUES:
        errors.append(f"{path}: invalid source_task")
    if meta.get("source_design") and meta["source_design"] not in SOURCE_DESIGN_VALUES:
        errors.append(f"{path}: invalid source_design")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    task_id = meta.get("task_id", "")
    if task_id and task_id != "none" and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    fetched = meta.get("fetched_at")
    if fetched:
        try:
            stamp = datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
        else:
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                errors.append(f"{path}: fetched_at must include timezone offset")
    if meta.get("source_design") == "figma" and meta.get("figma_urls", "none") == "none":
        errors.append(f"{path}: source_design figma requires figma_urls")
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    if status == "ready":
        testable = body.split("## Testable", 1)
        chunk = testable[1].split("##", 1)[0] if len(testable) == 2 else ""
        if "→" not in chunk and "->" not in chunk:
            errors.append(f"{path}: ready card needs Testable item with arrow")
    return errors
```

In `validate_memory_tree`, after entity checks, add:

```python
    tasks_dir = root / "tasks"
    if tasks_dir.is_dir():
        for card in tasks_dir.glob("task-*.md"):
            errors.extend(validate_task_snapshot(card))
    req_dir = root / "requirements"
    if req_dir.is_dir():
        for card in req_dir.glob("task-*.md"):
            errors.extend(validate_requirement_card(card))
```

Do not require `requirements/` or `tasks/` when absent. Do not validate `requirements/index.md` as an entity card.

- [ ] **Step 5: Run tests**

```powershell
py -3 -m pytest tests/test_memory_schema.py -v
py -3 -m ruff check tools tests
py -3 tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: all pytest PASS; ruff clean; CLI `OK`.

- [ ] **Step 6: Commit**

```powershell
git add tools/memory_schema.py tests/test_memory_schema.py fixtures/demo-requirement
git commit -m "Validate requirement cards and task snapshots."
```

---

### Task 2: Hunter пишет снимок задачи

**Files:**
- Modify: `.cursor/agents/hunter.md`
- Test: no new pytest; incoming `task.json` shape is specified below

**Interfaces:**
- Consumes: existing hunter modes
- Produces: when the written task says `kind: task` or target is `tasks/task-<id>` / Upservice task id, write `_incoming/task.json` + MANIFEST listing `task.json` (not catalog.json). Do not write requirements.

- [ ] **Step 1: Extend hunter.md**

Add a section after `## Output` (keep existing catalog output for index-system / entity recall):

```markdown
## Task snapshot (analyze-requirement)

When the coordinator task says `kind: task` and a `task_id`:

- Fetch that one Upservice task via public API (then internal if configured and public missed). Do not open Figma. Browser is forbidden for this kind.
- Do not treat `entities/tasks.md` as the instance list.
- Write `memory/<product-id>/raw/_incoming/task.json`:

```json
{
  "kind": "task",
  "channel": "public",
  "fetched_at": "2026-08-13T17:00:00+03:00",
  "task_id": "1",
  "title": "Show sprint dates",
  "fields": {},
  "figma_urls": ["https://www.figma.com/design/demo/sprint"],
  "errors": []
}
```

- `MANIFEST.md` lists only `task.json`.
- If the task is missing: `task.json` with empty title/fields and `errors[]`; still write MANIFEST. Do not invent the task.
- Do not write `requirements/` or `tasks/` canonical files.
```

Also add `kind: task` to the "When invoked" task fields.

- [ ] **Step 2: Commit**

```powershell
git add .cursor/agents/hunter.md
git commit -m "Let hunter fetch a single Upservice task snapshot."
```

---

### Task 3: Librarian канонизирует tasks/ и requirements/

**Files:**
- Modify: `.cursor/agents/librarian.md`
- Modify: `.cursor/rules/memory-card.mdc` (optional one paragraph on requirements + task snapshots)
- Test: `py -3 tools/memory_schema.py fixtures/demo-catalog/expected` still `OK`

**Interfaces:**
- Consumes: `task.json` and `requirement.md` incoming shapes from Tasks 1–2
- Produces: `memory/<id>/tasks/task-<id>.md`, `memory/<id>/requirements/task-<id>.md`, `requirements/index.md`

- [ ] **Step 1: Update librarian.md**

Add to Canonical paths:

```markdown
- `memory/<product-id>/tasks/task-<id>.md`
- `memory/<product-id>/requirements/index.md`
- `memory/<product-id>/requirements/task-<id>.md`
```

Add goals: `index | merge-one | mark-stale | task-snapshot | requirement`.

Add section:

```markdown
## Task snapshot incoming

If MANIFEST lists `task.json`: write `tasks/task-<task_id>.md`. Frontmatter: entity fields plus `task_id`. `slug` is `task-<task_id>`. `status: deep`. Do not edit `entities/tasks.md` into an instance list. Body: only fields and URLs present in JSON.

## Requirement incoming

If MANIFEST lists `requirement.md`: write `requirements/<slug>.md` and a row in `requirements/index.md`. Dedup by slug (merge, never `task-1-2`). Do not invent Testable rows. `ready` only if at least one action→expected item exists. Always include "Did not write to Upservice." Do not call Figma or the product.

Match `fixtures/demo-requirement/expected/` for shape.
```

Keep existing catalog/entity rules. After any successful write, run `py -3 tools/memory_schema.py memory/<product-id>` (or `python` if that is what the host uses) and fix errors before success.

- [ ] **Step 2: Add a short note to memory-card.mdc**

After the existing entity rules:

```markdown
Task snapshots live in `memory/<product-id>/tasks/task-<id>.md` (entity frontmatter plus `task_id`). Requirement cards live in `memory/<product-id>/requirements/task-<id>.md` with requirement fields from the spec. Only librarian writes both.
```

- [ ] **Step 3: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/rules/memory-card.mdc
git commit -m "Teach librarian task snapshots and requirement cards."
```

---

### Task 4: Analyst subagent

**Files:**
- Create: `.cursor/agents/analyst.md`
- Test: none beyond file present with required frontmatter `name: analyst`

**Interfaces:**
- Consumes: `memory/<id>/tasks/task-<id>.md`, `entities/`, `catalog/api.md`
- Produces: `_incoming/requirement.md` + MANIFEST listing `requirement.md`. No API, no canonical writes.

- [ ] **Step 1: Write analyst.md**

```markdown
---
name: analyst
description: Turns one Upservice task snapshot plus Figma MCP into a requirement draft. Does not call the product API or write canonical memory. Use after tasks/task-<id>.md exists, before librarian writes requirements/.
---

You are the QA swarm Analyst. You draft testable requirements. You do not write canonical memory. You do not call Upservice.

## When invoked

Read the written task: product-id, task_id or spec path, path to `tasks/task-<id>.md` if any.

If `memory/<product-id>/raw/_incoming/` is not empty: stop.

If this is a ticket: read `memory/<product-id>/tasks/task-<id>.md`. If the file is missing: stop. Do not fetch the API.

If this is a spec without a ticket: read the attached file; `task_id: none`, `source_task: none`.

Read `entities/` and `catalog/api.md` for links. Do not invent endpoints.

## Figma

Extract Figma URLs from the task snapshot only. Call Figma MCP only for those URLs. On 403 or wrong file: do not open a neighbor file. Set `source_design: none` or keep `figma` only if you actually opened the linked file. No invented screens.

## Output

Write `memory/<product-id>/raw/_incoming/requirement.md` using the requirement frontmatter contract (see spec and `fixtures/demo-requirement/incoming/requirement.md`).

- `ready` only with at least one `## Testable` line containing `→` or `->`.
- `draft` if only gaps.
- `figma_urls: none` and `source_design: none` when there is no usable design.
- `entities`: comma-separated slugs or `none`.
- End with: Did not write to Upservice.
- Redact secrets.

Write `MANIFEST.md` listing `requirement.md` only.

Do not edit `tasks/`, `requirements/`, `entities/`, or Upservice.
```

- [ ] **Step 2: Commit**

```powershell
git add .cursor/agents/analyst.md
git commit -m "Add analyst subagent for requirement drafts."
```

---

### Task 5: Skill, координатор, README

**Files:**
- Create: `.cursor/skills/analyze-requirement/SKILL.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Test: `py -3 -m pytest tests/test_memory_schema.py -v`

**Interfaces:**
- Consumes: hunter `kind: task`, analyst, librarian `task-snapshot` then `requirement`
- Produces: user-facing skill and routing

- [ ] **Step 1: Write the skill**

`.cursor/skills/analyze-requirement/SKILL.md`:

```markdown
---
name: analyze-requirement
description: Analyzes one Upservice task (and Figma link) into a git requirement card. Use when the user says проанализируй задачу, разбери требования, or attaches a spec without a ticket. Does not write to Upservice.
---

# analyze-requirement

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Ticket id present: look for `memory/<id>/tasks/task-<task-id>.md`. Missing, stale, or expired TTL: launch `hunter` with `kind: task` and that `task_id`. Then `librarian` with goal `task-snapshot`. Do not start `analyst` before that file exists. If the API has no task: stop, do not invent.
3. Launch `analyst` with the snapshot path (or the attached spec). Analyst uses Figma MCP only for URLs in the snapshot.
4. After MANIFEST lists `requirement.md`, launch `librarian` with goal `requirement`.
5. Report the card path, testable count, and gaps. Say requirements are ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice. Do not use browser MCP. Do not treat `entities/tasks.md` as instances.
```

- [ ] **Step 2: Update coordinator.mdc**

Keep it under 50 lines. Replace the skills/subagents line and add two sentences:

```markdown
Skills: `index-system`, `recall`, `refresh`, `analyze-requirement`. Subagents: `hunter`, `librarian`, `analyst`.

For analyze-requirement: hunter may fetch one task snapshot into `tasks/task-<id>.md` via librarian; analyst drafts requirements; librarian writes `requirements/`. Do not write to the product.
```

- [ ] **Step 3: Update AGENTS.md**

Add:

```markdown
- `analyst` reads a task snapshot and Figma. Draft only in `_incoming/requirement.md`.
```

Add spec path: `docs/superpowers/specs/2026-08-13-qa-swarm-requirements-analysis-design.md`

Change "Do not do in v1" so it no longer forbids requirement analysis; still forbid writing tickets, Playwright, RAG.

- [ ] **Step 4: Update README.md**

Add command:

```markdown
- «Проанализируй задачу 1842» → skill `analyze-requirement`
```

Add acceptance bullets from spec §11. Mention Figma MCP must be connected in Cursor.

- [ ] **Step 5: Run automated checks**

```powershell
py -3 -m pytest tests/test_memory_schema.py -v
py -3 -m ruff check tools tests
py -3 tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: PASS / `OK`.

- [ ] **Step 6: Commit**

```powershell
git add .cursor/skills/analyze-requirement/SKILL.md .cursor/rules/coordinator.mdc AGENTS.md README.md
git commit -m "Add analyze-requirement skill and coordinator routing."
```

---

## Self-review (spec coverage)

| Spec | Task |
|------|------|
| §5 поток, границы ролей | 2, 3, 4, 5 |
| §6 paths, slug, не entities/tasks | 1, 2, 3 |
| §7 requirement contract | 1, 3, 4 |
| §8 analyst + skill | 4, 5 |
| §9–10 ошибки, no write to product | 4, 5 |
| §11 fixtures + schema | 1 |
| §3 no Task Retriever, no browser | 2, 5 |

Placeholders: none. `validate_requirement_card` / `validate_task_snapshot` / `task.json` names are stable across tasks.
