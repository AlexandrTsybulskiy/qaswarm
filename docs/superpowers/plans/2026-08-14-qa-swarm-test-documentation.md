# QA Swarm Test Documentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить контур тест-доков: `ready` карточка требований → канонический сюит атомарных кейсов в git-памяти, без записи в Upservice и Testmo.

**Architecture:** Координатор стартует только при `requirements/<slug>.md` со `status: ready`. Scribe пишет `_incoming/testdocs.md` без id. Python-хелпер мержит id по `action`+`expected`. Librarian записывает `testdocs/` и индекс. Схема расширяет `tools/memory_schema.py`. Карта сущностей и requirements не ломаются.

**Tech Stack:** Cursor agents/skills/rules, Markdown/YAML память, Python 3.11+ stdlib, pytest/ruff. Без HTTP-клиента и без клиента TMS.

## Global Constraints

- В Upservice и Testmo агенты не пишут.
- Вход только `ready` карточка требований; иначе стоп.
- `analyze-requirement` из этого skill не запускать.
- 1 пункт Testable с `→` = 1 кейс; текст `action`/`expected` дословный.
- Чек-лист — только id `active` в порядке Testable.
- Id ставит Python-хелпер; входящие `tc-…` игнорируются.
- Scribe не читает `testdocs/` и не пишет канон.
- Librarian не ходит в продукт и не в TMS.
- Координатор не пишет `memory/`.
- Замок: непустой `raw/_incoming/`.
- Slug сюита = slug требования; `task_id` не `none` → id `tc-<task_id>-<n>`.
- Frontmatter: одна строка `ключ: значение`.
- `fetched_at`: ISO-8601 со смещением.
- `testdocs/` может отсутствовать — дерево ядра валидно.
- Browser MCP и Figma MCP в этом контуре не используются.
- На этом хосте CLI: `py -3`, не `python`.
- Не делать: Testmo-клиент, тест-план, e2e, запись в тикет, пакетный спринт.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/testdoc_merge.py` | Parse incoming/canonical cases, merge id, render suite, CLI |
| `tools/memory_schema.py` | `validate_testdoc_suite`, optional `testdocs/` in tree |
| `tests/test_testdoc_merge.py` | Merge, orphan, duplicate keys, CLI |
| `tests/test_memory_schema.py` | Валидация сюита + регрессия дерева без testdocs |
| `fixtures/demo-testdoc/` | Incoming без id, existing сюит, expected канон |
| `.cursor/agents/scribe.md` | Черновик `_incoming/testdocs.md` |
| `.cursor/agents/librarian.md` | Канон `testdocs/` через хелпер |
| `.cursor/skills/generate-testdocs/SKILL.md` | Поток команды |
| `.cursor/rules/coordinator.mdc` | Маршрутизация |
| `.cursor/rules/memory-card.mdc` | Путь testdocs |
| `AGENTS.md`, `README.md` | Роль scribe и команда |

---

### Task 1: Хелпер merge id

**Files:**
- Create: `tools/testdoc_merge.py`
- Create: `tests/test_testdoc_merge.py`
- Test: `tests/test_testdoc_merge.py`

**Interfaces:**
- Consumes: `memory_schema.parse_frontmatter`
- Produces:
  - `TestdocCase(title: str, action: str, expected: str, status: str = "active", case_id: str | None = None)`
  - `match_key(action: str, expected: str) -> str`
  - `case_id_prefix(task_id: str, slug: str) -> str`
  - `format_case_id(prefix: str, n: int) -> str`
  - `parse_incoming_body(body: str) -> tuple[list[TestdocCase], list[str]]`
  - `parse_canonical_cases(body: str) -> list[TestdocCase]`
  - `merge_testdoc_cases(existing: list[TestdocCase], incoming: list[TestdocCase], prefix: str, next_id: int) -> tuple[list[TestdocCase], list[str], int]`
  - `render_testdoc(meta: dict[str, str], cases: list[TestdocCase], checklist: list[str], gaps: list[str]) -> str`
  - `merge_files(incoming_path: Path, existing_path: Path | None) -> str`
  - `main(argv: list[str] | None = None) -> int` with `--incoming`, `--existing`, `--output`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_testdoc_merge.py`:

```python
from pathlib import Path

import testdoc_merge
from testdoc_merge import TestdocCase


def test_match_key_trims() -> None:
    assert testdoc_merge.match_key("  Open", " visible ") == "Open\nvisible"


def test_prefix_uses_task_id() -> None:
    assert testdoc_merge.case_id_prefix("5210629", "task-5210629") == "5210629"
    assert testdoc_merge.case_id_prefix("none", "checkout-spec") == "checkout-spec"


def test_merge_keeps_id_on_same_text() -> None:
    existing = [
        TestdocCase("A", "Open card", "dates visible", "active", "tc-1-1"),
        TestdocCase("B", "Open empty", "row hidden", "active", "tc-1-2"),
    ]
    incoming = [
        TestdocCase("Sprint dates", "Open card", "dates visible"),
        TestdocCase("Save", "Click save", "dates persist"),
        TestdocCase("Placeholder", "Open empty", "placeholder shown"),
    ]
    cases, checklist, next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 3
    )
    by_id = {c.case_id: c for c in cases}
    assert by_id["tc-1-1"].status == "active"
    assert by_id["tc-1-2"].status == "orphan"
    assert by_id["tc-1-3"].action == "Click save"
    assert by_id["tc-1-3"].status == "active"
    assert checklist == ["tc-1-1", "tc-1-3"]
    assert next_id == 4


def test_merge_reactivates_orphan_on_same_text() -> None:
    existing = [
        TestdocCase("A", "Open card", "dates visible", "orphan", "tc-1-1"),
    ]
    incoming = [TestdocCase("A", "Open card", "dates visible")]
    cases, checklist, next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 2
    )
    assert cases[0].case_id == "tc-1-1"
    assert cases[0].status == "active"
    assert checklist == ["tc-1-1"]
    assert next_id == 2


def test_duplicate_incoming_gets_two_ids() -> None:
    existing = [TestdocCase("A", "Do x", "see y", "active", "tc-1-1")]
    incoming = [
        TestdocCase("A", "Do x", "see y"),
        TestdocCase("A2", "Do x", "see y"),
    ]
    cases, checklist, next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 2
    )
    assert checklist == ["tc-1-1", "tc-1-2"]
    assert next_id == 3
    assert [c.status for c in cases] == ["active", "active"]


def test_parse_incoming_ignores_heading_ids() -> None:
    body = (
        "## Cases\n\n### tc-9-99\ntitle: T\naction: Do x\nexpected: see y\n\n"
        "## Gaps\n\n- none\n"
    )
    cases, gaps = testdoc_merge.parse_incoming_body(body)
    assert cases[0].case_id is None
    assert cases[0].action == "Do x"
    assert gaps == ["none"]


def test_merge_files_first_run(tmp_path: Path) -> None:
    incoming = tmp_path / "testdocs.md"
    incoming.write_text(
        "---\nslug: task-1\ntitle: Sprint dates\nproduct: demo\ntask_id: 1\n"
        "requirement: task-1\nfetched_at: 2026-08-14T09:00:00+03:00\n"
        "---\n\n## Cases\n\n### case\ntitle: Visible\n"
        "action: Open a sprint card\nexpected: start and end dates are visible\n\n"
        "## Gaps\n\n- none\n",
        encoding="utf-8",
    )
    text = testdoc_merge.merge_files(incoming, None)
    assert "### tc-1-1" in text
    assert "next_id: 2" in text
    assert "status: ready" in text
    assert "- tc-1-1" in text
    assert "Did not write to Upservice or Testmo." in text


def test_cli_writes_output(tmp_path: Path) -> None:
    incoming = tmp_path / "testdocs.md"
    incoming.write_text(
        "---\nslug: checkout-spec\ntitle: Checkout\nproduct: demo\ntask_id: none\n"
        "requirement: checkout-spec\nfetched_at: 2026-08-14T09:00:00+03:00\n"
        "---\n\n## Cases\n\n### case\ntitle: Pay\n"
        "action: Click pay\nexpected: order is created\n\n## Gaps\n\n",
        encoding="utf-8",
    )
    output = tmp_path / "out" / "checkout-spec.md"
    code = testdoc_merge.main(
        [
            "--incoming",
            str(incoming),
            "--output",
            str(output),
        ]
    )
    assert code == 0
    text = output.read_text(encoding="utf-8")
    assert "### tc-checkout-spec-1" in text
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
py -3 -m pytest tests/test_testdoc_merge.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'testdoc_merge'` (or import error).

- [ ] **Step 3: Write `tools/testdoc_merge.py`**

```python
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from memory_schema import parse_frontmatter


@dataclass
class TestdocCase:
    title: str
    action: str
    expected: str
    status: str = "active"
    case_id: str | None = None


def match_key(action: str, expected: str) -> str:
    return f"{action.strip()}\n{expected.strip()}"


def case_id_prefix(task_id: str, slug: str) -> str:
    if task_id and task_id != "none":
        return task_id
    return slug


def format_case_id(prefix: str, n: int) -> str:
    return f"tc-{prefix}-{n}"


def _section_body(body: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)")
    match = pattern.search(body)
    return match.group(1) if match else ""


def _parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        fields[key.strip()] = raw.strip()
    return fields


def _case_blocks(section: str) -> list[str]:
    chunks = re.split(r"(?m)^### .+\n", section)
    return [chunk for chunk in chunks[1:] if chunk.strip()]


def parse_incoming_body(body: str) -> tuple[list[TestdocCase], list[str]]:
    cases: list[TestdocCase] = []
    for block in _case_blocks(_section_body(body, "Cases")):
        fields = _parse_fields(block)
        cases.append(
            TestdocCase(
                title=fields.get("title", ""),
                action=fields.get("action", ""),
                expected=fields.get("expected", ""),
            )
        )
    gaps: list[str] = []
    for line in _section_body(body, "Gaps").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            gaps.append(stripped[2:].strip())
    return cases, gaps


def parse_canonical_cases(body: str) -> list[TestdocCase]:
    cases: list[TestdocCase] = []
    section = _section_body(body, "Cases")
    headings = re.findall(r"(?m)^### (\S+)\s*$", section)
    blocks = _case_blocks(section)
    for heading, block in zip(headings, blocks, strict=False):
        fields = _parse_fields(block)
        cases.append(
            TestdocCase(
                title=fields.get("title", ""),
                action=fields.get("action", ""),
                expected=fields.get("expected", ""),
                status=fields.get("status", "active"),
                case_id=heading,
            )
        )
    return cases


def _case_number(case_id: str | None) -> int:
    if not case_id:
        return 0
    _, _, last = case_id.rpartition("-")
    return int(last) if last.isdigit() else 0


def merge_testdoc_cases(
    existing: list[TestdocCase],
    incoming: list[TestdocCase],
    prefix: str,
    next_id: int,
) -> tuple[list[TestdocCase], list[str], int]:
    claimed: set[int] = set()
    active: list[TestdocCase] = []
    cursor = next_id
    for item in incoming:
        key = match_key(item.action, item.expected)
        found: int | None = None
        for index, prior in enumerate(existing):
            if index in claimed:
                continue
            if match_key(prior.action, prior.expected) == key:
                found = index
                break
        if found is not None:
            claimed.add(found)
            prior = existing[found]
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=prior.case_id,
                )
            )
        else:
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=format_case_id(prefix, cursor),
                )
            )
            cursor += 1
    orphans = [
        TestdocCase(
            title=prior.title,
            action=prior.action,
            expected=prior.expected,
            status="orphan",
            case_id=prior.case_id,
        )
        for index, prior in enumerate(existing)
        if index not in claimed
    ]
    cases = active + orphans
    checklist = [case.case_id for case in active if case.case_id]
    max_n = max([_case_number(case.case_id) for case in cases] + [cursor - 1, 0])
    return cases, checklist, max_n + 1


def render_testdoc(
    meta: dict[str, str],
    cases: list[TestdocCase],
    checklist: list[str],
    gaps: list[str],
) -> str:
    lines = ["---"]
    for key in (
        "slug",
        "title",
        "product",
        "task_id",
        "requirement",
        "status",
        "fetched_at",
        "next_id",
    ):
        lines.append(f"{key}: {meta[key]}")
    lines.extend(["---", "", "## Cases", ""])
    for case in cases:
        lines.extend(
            [
                f"### {case.case_id}",
                f"title: {case.title}",
                f"action: {case.action}",
                f"expected: {case.expected}",
                f"status: {case.status}",
                "",
            ]
        )
    lines.extend(["## Checklist", ""])
    for case_id in checklist:
        lines.append(f"- {case_id}")
    if not checklist:
        lines.append("")
    lines.extend(["", "## Gaps", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "Did not write to Upservice or Testmo.", ""])
    return "\n".join(lines)


def merge_files(incoming_path: Path, existing_path: Path | None) -> str:
    incoming_meta, incoming_body = parse_frontmatter(
        incoming_path.read_text(encoding="utf-8")
    )
    incoming_cases, gaps = parse_incoming_body(incoming_body)
    existing_cases: list[TestdocCase] = []
    next_id = 1
    if existing_path is not None and existing_path.is_file():
        existing_meta, existing_body = parse_frontmatter(
            existing_path.read_text(encoding="utf-8")
        )
        existing_cases = parse_canonical_cases(existing_body)
        next_id = int(existing_meta.get("next_id", "1"))
    prefix = case_id_prefix(incoming_meta["task_id"], incoming_meta["slug"])
    cases, checklist, new_next = merge_testdoc_cases(
        existing_cases, incoming_cases, prefix, next_id
    )
    status = "ready" if any(case.status == "active" for case in cases) else "draft"
    meta = {
        "slug": incoming_meta["slug"],
        "title": incoming_meta["title"],
        "product": incoming_meta["product"],
        "task_id": incoming_meta["task_id"],
        "requirement": incoming_meta["requirement"],
        "status": status,
        "fetched_at": incoming_meta["fetched_at"],
        "next_id": str(new_next),
    }
    return render_testdoc(meta, cases, checklist, gaps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge testdoc incoming into a suite")
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--existing", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        text = merge_files(args.incoming, args.existing)
    except (KeyError, ValueError, OSError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(f"{args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

```powershell
py -3 -m pytest tests/test_testdoc_merge.py -v
py -3 -m ruff check tools/testdoc_merge.py tests/test_testdoc_merge.py
```

Expected: all PASS; ruff clean.

- [ ] **Step 5: Commit**

```powershell
git add tools/testdoc_merge.py tests/test_testdoc_merge.py
git commit -m "Add testdoc id merge helper."
```

---

### Task 2: Схема сюита и фикстура

**Files:**
- Modify: `tools/memory_schema.py`
- Modify: `tests/test_memory_schema.py`
- Create: `fixtures/demo-testdoc/incoming/testdocs.md`
- Create: `fixtures/demo-testdoc/incoming/MANIFEST.md`
- Create: `fixtures/demo-testdoc/existing/testdocs/task-1.md`
- Create: `fixtures/demo-testdoc/expected/testdocs/task-1.md`
- Create: `fixtures/demo-testdoc/expected/testdocs/index.md`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `testdoc_merge.parse_canonical_cases`, `testdoc_merge.case_id_prefix`, `testdoc_merge.match_key`, `testdoc_merge._case_number` (do not import `_case_number`; parse n with `rsplit("-", 1)` in the validator)
- Produces:
  - `TD_REQUIRED = ("slug", "title", "product", "task_id", "requirement", "status", "fetched_at", "next_id")`
  - `TD_STATUSES = {"draft", "ready", "stale"}`
  - `validate_testdoc_suite(path: Path) -> list[str]`
  - `validate_memory_tree` validates `testdocs/*.md` except `index.md` when the dir exists; missing dir is not an error

- [ ] **Step 1: Write fixtures**

`fixtures/demo-testdoc/incoming/MANIFEST.md`:

```markdown
# Scribe incoming manifest

- testdocs.md
```

`fixtures/demo-testdoc/incoming/testdocs.md`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
requirement: task-1
fetched_at: 2026-08-14T09:00:00+03:00
---

## Cases

### case
title: Sprint dates visible
action: Open a sprint card
expected: start and end dates are visible

### case
title: Save persists dates
action: Click save
expected: dates persist

### case
title: Missing dates placeholder
action: Open a sprint without dates
expected: placeholder shown

## Gaps

- none
```

`fixtures/demo-testdoc/existing/testdocs/task-1.md`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-13T17:00:00+03:00
next_id: 3
---

## Cases

### tc-1-1
title: Visible
action: Open a sprint card
expected: start and end dates are visible
status: active

### tc-1-2
title: Hidden
action: Open a sprint without dates
expected: date row is hidden
status: active

## Checklist

- tc-1-1
- tc-1-2

## Gaps

- none

Did not write to Upservice or Testmo.
```

`fixtures/demo-testdoc/expected/testdocs/task-1.md`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-14T09:00:00+03:00
next_id: 4
---

## Cases

### tc-1-1
title: Sprint dates visible
action: Open a sprint card
expected: start and end dates are visible
status: active

### tc-1-3
title: Save persists dates
action: Click save
expected: dates persist
status: active

### tc-1-2
title: Hidden
action: Open a sprint without dates
expected: date row is hidden
status: orphan

## Checklist

- tc-1-1
- tc-1-3

## Gaps

- none

Did not write to Upservice or Testmo.
```

`fixtures/demo-testdoc/expected/testdocs/index.md`:

```markdown
# Testdocs

| Slug | Task | Status | Active | Card |
|------|------|--------|--------|------|
| task-1 | 1 | ready | 2 | [task-1.md](task-1.md) |
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_memory_schema.py` (do not change existing tests):

```python
TD_INCOMING = ROOT / "fixtures" / "demo-testdoc" / "incoming"
TD_EXISTING = ROOT / "fixtures" / "demo-testdoc" / "existing" / "testdocs" / "task-1.md"
TD_EXPECTED = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "task-1.md"


def test_demo_catalog_tree_still_valid_without_testdocs() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_testdoc_suite_valid() -> None:
    assert memory_schema.validate_testdoc_suite(TD_EXPECTED) == []


def test_testdoc_ready_without_active_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "requirement: task-1\nstatus: ready\n"
        "fetched_at: 2026-08-14T09:00:00+03:00\nnext_id: 1\n"
        "---\n\n## Cases\n\n## Checklist\n\n## Gaps\n\n- none\n\n"
        "Did not write to Upservice or Testmo.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_testdoc_suite(card)
    assert any("active" in e for e in errors)


def test_testdoc_orphan_not_in_checklist(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        TD_EXPECTED.read_text(encoding="utf-8").replace(
            "- tc-1-1\n- tc-1-3\n",
            "- tc-1-1\n- tc-1-3\n- tc-1-2\n",
        ),
        encoding="utf-8",
    )
    errors = memory_schema.validate_testdoc_suite(card)
    assert any("checklist" in e.lower() for e in errors)


def test_testdoc_merge_fixture_matches_expected() -> None:
    import testdoc_merge

    text = testdoc_merge.merge_files(TD_INCOMING / "testdocs.md", TD_EXISTING)
    assert memory_schema.parse_frontmatter(text)[0]["next_id"] == "4"
    got = testdoc_merge.parse_canonical_cases(memory_schema.parse_frontmatter(text)[1])
    want = testdoc_merge.parse_canonical_cases(
        memory_schema.parse_frontmatter(TD_EXPECTED.read_text(encoding="utf-8"))[1]
    )
    assert [(c.case_id, c.status, c.action, c.expected) for c in got] == [
        (c.case_id, c.status, c.action, c.expected) for c in want
    ]


def test_testdocs_index_not_validated_as_suite(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    testdocs.mkdir()
    (testdocs / "index.md").write_text("# Testdocs\n", encoding="utf-8")
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert not any("testdocs/index.md" in e for e in errors)


def test_demo_testdoc_incoming_complete() -> None:
    assert memory_schema.incoming_complete(TD_INCOMING) is True
```

- [ ] **Step 3: Run tests to verify schema tests fail**

```powershell
py -3 -m pytest tests/test_memory_schema.py::test_testdoc_suite_valid tests/test_memory_schema.py::test_testdoc_ready_without_active_fails -v
```

Expected: FAIL with `AttributeError: module 'memory_schema' has no attribute 'validate_testdoc_suite'`.

- [ ] **Step 4: Implement validation**

In `tools/memory_schema.py` add constants after `SOURCE_DESIGN_VALUES`:

```python
TD_REQUIRED = (
    "slug",
    "title",
    "product",
    "task_id",
    "requirement",
    "status",
    "fetched_at",
    "next_id",
)
TD_STATUSES = {"draft", "ready", "stale"}
TD_CASE_STATUSES = {"active", "orphan"}
```

Add `validate_testdoc_suite` after `validate_requirement_card` (import testdoc_merge inside the function to keep module import of memory_schema usable from testdoc_merge):

```python
def validate_testdoc_suite(path: Path) -> list[str]:
    import testdoc_merge

    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in TD_REQUIRED:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in TD_STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    task_id = meta.get("task_id", "")
    if task_id and task_id != "none" and not slug_ok(task_id):
        errors.append(f"{path}: invalid task_id {task_id!r}")
    if task_id and task_id != "none" and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    requirement = meta.get("requirement", "")
    if requirement and not slug_ok(requirement):
        errors.append(f"{path}: invalid requirement {requirement!r}")
    fetched = meta.get("fetched_at")
    if fetched:
        try:
            stamp = datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
        else:
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                errors.append(f"{path}: fetched_at must include timezone offset")
    next_raw = meta.get("next_id", "")
    next_id = 0
    if next_raw:
        if not re.fullmatch(r"[1-9][0-9]*", next_raw):
            errors.append(f"{path}: next_id must be an integer >= 1")
        else:
            next_id = int(next_raw)
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    for heading in ("## Cases", "## Checklist", "## Gaps"):
        if not re.search(rf"(?m)^{re.escape(heading)}\s*$", body):
            errors.append(f"{path}: missing {heading} heading")
    if not any("Did not write to Upservice" in line and "Testmo" in line for line in body.splitlines()):
        errors.append(f"{path}: missing Did not write to Upservice or Testmo notice")
    cases = testdoc_merge.parse_canonical_cases(body)
    prefix = testdoc_merge.case_id_prefix(task_id or "none", slug)
    active_ids: list[str] = []
    max_n = 0
    for case in cases:
        if not case.case_id or not case.case_id.startswith(f"tc-{prefix}-"):
            errors.append(f"{path}: invalid case id {case.case_id!r}")
        elif not re.fullmatch(rf"tc-{re.escape(prefix)}-[1-9][0-9]*", case.case_id):
            errors.append(f"{path}: invalid case id {case.case_id!r}")
        if case.status not in TD_CASE_STATUSES:
            errors.append(f"{path}: invalid case status {case.status!r}")
        if not case.action or not case.expected:
            errors.append(f"{path}: case {case.case_id} missing action or expected")
        if case.case_id:
            _, _, last = case.case_id.rpartition("-")
            if last.isdigit():
                max_n = max(max_n, int(last))
        if case.status == "active" and case.case_id:
            active_ids.append(case.case_id)
    if status == "ready" and not active_ids:
        errors.append(f"{path}: ready suite needs an active case")
    checklist: list[str] = []
    chunk = body.split("## Checklist", 1)
    check_body = chunk[1].split("##", 1)[0] if len(chunk) == 2 else ""
    for line in check_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            checklist.append(stripped[2:].strip())
    if checklist != active_ids:
        errors.append(f"{path}: checklist must list active ids in case order")
    if next_id and max_n and next_id != max_n + 1:
        errors.append(f"{path}: next_id {next_id} must be {max_n + 1}")
    if next_id and not cases and next_id != 1:
        errors.append(f"{path}: empty suite next_id must be 1")
    return errors
```

At the end of `validate_memory_tree`, before `return errors`, add:

```python
    testdocs_dir = root / "testdocs"
    if testdocs_dir.is_dir():
        for card in testdocs_dir.glob("*.md"):
            if card.name == "index.md":
                continue
            errors.extend(validate_testdoc_suite(card))
```

- [ ] **Step 5: Run tests**

```powershell
py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py -v
py -3 -m ruff check tools tests
py -3 tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: all PASS; CLI prints `OK`.

- [ ] **Step 6: Commit**

```powershell
git add tools/memory_schema.py tests/test_memory_schema.py fixtures/demo-testdoc
git commit -m "Validate testdoc suites and add merge fixture."
```

---

### Task 3: Librarian пишет testdocs/

**Files:**
- Modify: `.cursor/agents/librarian.md`
- Modify: `.cursor/rules/memory-card.mdc`
- Test: no new pytest; librarian must call the CLI from Task 1

**Interfaces:**
- Consumes: `_incoming/testdocs.md` + MANIFEST listing `testdocs.md`; `testdoc_merge.main`
- Produces: `testdocs/<slug>.md` via CLI, row in `testdocs/index.md`. No invented cases. No Testmo/Upservice calls.

- [ ] **Step 1: Extend librarian.md**

Add to Canonical paths:

```markdown
- `memory/<product-id>/testdocs/index.md`
- `memory/<product-id>/testdocs/<slug>.md`
```

Add section after Requirement incoming:

```markdown
## Testdoc incoming

If MANIFEST lists `testdocs.md`: do not assign case ids yourself.

Run (host CLI `py -3` or `python`):

```
py -3 tools/testdoc_merge.py --incoming memory/<product-id>/raw/_incoming/testdocs.md --existing memory/<product-id>/testdocs/<slug>.md --output memory/<product-id>/testdocs/<slug>.md
```

If the existing suite file does not exist, omit `--existing`. `<slug>` is the incoming `slug` (same as the requirement slug). Dedup by slug (merge, never `task-1-2`).

Then add or update a row in `testdocs/index.md`:

```markdown
# Testdocs

| Slug | Task | Status | Active | Card |
|------|------|--------|--------|------|
| task-1 | 1 | ready | 2 | [task-1.md](task-1.md) |
```

`Task` is `task_id` or empty when `none`. `Active` is the number of `status: active` cases. Do not invent cases or rewrite action/expected. Do not call Figma, Upservice, or Testmo.

Match `fixtures/demo-testdoc/expected/` for shape (ids and sections, not demo titles).
```

Also add testdocs to the "Do not write" list nowhere — librarian is allowed to write them. Keep "Do not call HTTP, MCP, or the product."

- [ ] **Step 2: Update memory-card.mdc**

Append after the requirements paragraph:

```markdown
Testdoc suites live in `memory/<product-id>/testdocs/<slug>.md` with testdoc fields from the spec. Only librarian writes them (via `tools/testdoc_merge.py`). `testdocs/index.md` is not a card.
```

- [ ] **Step 3: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/rules/memory-card.mdc
git commit -m "Teach librarian testdoc suites via merge helper."
```

---

### Task 4: Scribe subagent

**Files:**
- Create: `.cursor/agents/scribe.md`
- Test: none beyond file present with frontmatter `name: scribe`

**Interfaces:**
- Consumes: `memory/<id>/requirements/<slug>.md` with `status: ready`
- Produces: `_incoming/testdocs.md` + MANIFEST listing `testdocs.md`. No API, no canonical writes, no testdocs read, no case ids.

- [ ] **Step 1: Write scribe.md**

```markdown
---
name: scribe
description: Turns one ready requirement card into a testdoc draft of atomic cases. Does not call the product API or write canonical memory. Use after requirements/<slug>.md is ready, before librarian writes testdocs/.
---

You are the QA swarm Scribe. You draft atomic test cases from requirements. You do not write canonical memory. You do not call Upservice, Figma, or Testmo.

## When invoked

Read the written task: product-id, requirement path `memory/<product-id>/requirements/<slug>.md`.

If `memory/<product-id>/raw/_incoming/` is not empty: stop.

If the requirement file is missing or `status` is not `ready`: stop. Do not invent Testable items. Do not fetch the API.

Do not read `testdocs/`. Do not assign `tc-…` ids.

## Cases

Read only `## Testable` on the requirement card. For each list item:

- If the line contains `→` or `->`, split on the **first** arrow. Copy `action` (left) and `expected` (right) verbatim. Do not paraphrase. `title` is a short label, not a replacement for the steps.
- If there is no arrow: add the line to Gaps, not to Cases.
- Do not turn the requirement `## Gaps` section into cases.
- Do not add checks that are not in Testable.

## Output

Write `memory/<product-id>/raw/_incoming/testdocs.md` using the incoming contract (see spec and `fixtures/demo-testdoc/incoming/testdocs.md`).

Frontmatter: `slug`, `title`, `product`, `task_id`, `requirement`, `fetched_at` (ISO-8601 with offset, copy from the requirement card). No `status`, no `next_id`.

Body: `## Cases` with `### case` sections (`title`, `action`, `expected` only), then `## Gaps`.

Write `MANIFEST.md` listing `testdocs.md` only.

Do not edit `testdocs/`, `requirements/`, `tasks/`, `entities/`, Upservice, or Testmo.
```

- [ ] **Step 2: Commit**

```powershell
git add .cursor/agents/scribe.md
git commit -m "Add scribe subagent for testdoc drafts."
```

---

### Task 5: Skill, координатор, README

**Files:**
- Create: `.cursor/skills/generate-testdocs/SKILL.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Test: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py -v`

**Interfaces:**
- Consumes: ready `requirements/<slug>.md`, scribe, librarian testdoc incoming
- Produces: user-facing skill and routing. Does not start `analyze-requirement`.

- [ ] **Step 1: Write the skill**

`.cursor/skills/generate-testdocs/SKILL.md`:

```markdown
---
name: generate-testdocs
description: Builds atomic test cases in git from a ready requirement card. Use when the user says сделай тест-доки, тест-кейсы для задачи, or сгенерируй кейсы. Does not write to Upservice or Testmo.
---

# generate-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/requirements/<slug>.md` (ticket id → `task-<id>`). If missing or `status` is not `ready`, stop. Tell the user to run `analyze-requirement` first. Do not start analyst, hunter, or invent Testable text.
3. Launch `scribe` with the requirement path. Scribe writes `_incoming/testdocs.md` without case ids. No Figma, no product API, no Testmo.
4. After MANIFEST lists `testdocs.md`, launch `librarian` with goal `testdoc`. Librarian runs `tools/testdoc_merge.py` and writes `testdocs/<slug>.md`.
5. Report the suite path, active count, orphan count, and gaps. Say testdocs are ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not use browser MCP or Figma MCP.
```

- [ ] **Step 2: Update coordinator.mdc**

Keep it under 50 lines. Replace the skills/subagents line and add two sentences after the analyze-requirement paragraph:

```markdown
Skills: `index-system`, `recall`, `refresh`, `analyze-requirement`, `generate-testdocs`. Subagents: `hunter`, `librarian`, `analyst`, `scribe`.

For analyze-requirement: hunter may fetch one task snapshot into `tasks/task-<id>.md` via librarian; analyst drafts requirements; librarian writes `requirements/`. Do not write to the product.

For generate-testdocs: only if `requirements/<slug>.md` is `ready`; scribe drafts `_incoming/testdocs.md`; librarian writes `testdocs/` via the merge helper. Do not start analyze-requirement from this skill. Do not write to the product or Testmo.
```

- [ ] **Step 3: Update AGENTS.md**

Add under Roles:

```markdown
- `scribe` reads a ready requirement card. Draft only in `_incoming/testdocs.md`.
```

Add spec path:

```markdown
`docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`
```

Keep "Do not do in v1" as writing tickets, Playwright/e2e, full API dumps, scheduled reindex, RAG, guessing product URLs. Do not list testdoc generation as forbidden.

- [ ] **Step 4: Update README.md**

In What this is, mention `scribe`. Add command:

```markdown
- «Сделай тест-доки для 1842» → skill `generate-testdocs`
```

Add acceptance bullets:

```markdown
7. Testdocs from ready requirements: `testdocs/task-<id>.md` has one active case per Testable arrow, a checklist of those ids, schema `OK`; Upservice and Testmo are not called.
8. Testdocs without a ready card: stop; `_incoming` stays empty; no testdocs file is created.
9. Testdocs repeat: same `action`+`expected` keeps the id; new text gets `next_id`; unmatched old cases become `orphan` and drop off the checklist.
```

Add spec line:

```markdown
Test documentation spec: `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md`
```

- [ ] **Step 5: Run automated checks**

```powershell
py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py -v
py -3 -m ruff check tools tests
py -3 tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: PASS / `OK`.

- [ ] **Step 6: Commit**

```powershell
git add .cursor/skills/generate-testdocs/SKILL.md .cursor/rules/coordinator.mdc AGENTS.md README.md
git commit -m "Add generate-testdocs skill and coordinator routing."
```

---

## Self-review (spec coverage)

| Spec | Task |
|------|------|
| §5 поток, Scribe + Librarian, замок incoming | 3, 4, 5 |
| §6 paths, slug, optional testdocs/ | 2, 3 |
| §7 контракт кейса, match key, 1:1 claim, orphan, next_id | 1, 2 |
| §7 incoming без id | 1, 4 |
| §8 роли и skill | 3, 4, 5 |
| §9 стоп без ready, не запускать анализ | 4, 5 |
| §10 ошибки, no Testmo/Upservice | 3, 4, 5 |
| §11 фикстура merge + schema | 1, 2 |
| §3 нет TMS-клиента, нет плана, нет Figma | 3, 4, 5 |
| §13 отложенный TMS external id = `tc-…` | схема полей в 1–2, клиента нет |

Placeholders: none. Names `TestdocCase`, `merge_testdoc_cases`, `validate_testdoc_suite`, `scribe`, `generate-testdocs` are stable across tasks.
