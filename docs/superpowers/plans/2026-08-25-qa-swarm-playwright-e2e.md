# QA Swarm Playwright E2E (Contour 6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить контур 6: `testdocs/md/<slug>.md` (UI-active) → маппинг/допись тестов во внешнем Playwright-репо → pytest → канон `e2e/` + `e2e-runs/` в git-памяти, без Upservice/Testmo и без записи в MCP `runs/`.

**Architecture:** Координатор skill `generate-e2e` при готовых testdocs и `playwright.root`/`root_env` запускает субагента `e2e-builder` (scan маркеров `qaswarm_tc` → write missing UI → pytest). Черновики в `_incoming/e2e.md` (+ `e2e-run.md` если UI закрыты). Librarian пишет `e2e/<slug>.md` и при полном прогоне `e2e-runs/<slug>.md`. Схема и опциональный `e2e_scan.py` — детерминированные хелперы. Код тестов только вне `qaswarm`.

**Tech Stack:** Cursor agents/skills/rules, Markdown/YAML память, Python 3.11+ stdlib, pytest/ruff. Прогон — CLI Playwright-репо (`run-tests.py` / pytest), не browser MCP qaswarm.

## Global Constraints

- В Upservice и Testmo агенты не пишут.
- Вход только `testdocs/md/<slug>.md` с ≥1 UI-`active`; иначе стоп.
- `generate-testdocs` / `analyze-requirement` / `verify-testdocs` из этого skill не запускать.
- Одна команда — один сюит; `orphan` не автоматизировать.
- Только UI-кейсы; API → `out_of_scope` в map; строк в `e2e-runs` на API нет.
- Код только под `playwright.root` (или путь из `playwright.root_env`).
- Маркер-источник правды: `@pytest.mark.qaswarm_tc("tc-…")`; зеркало `e2e/<slug>.md`.
- Вердикт только `e2e-runs/`; `runs/` не трогать.
- Если после Writer UI-`active` ещё `missing` — `e2e` draft, `e2e-runs` не писать.
- Builder не пишет канон; Librarian не ходит в продукт и не гоняет pytest.
- Координатор не пишет `memory/` канон.
- Замок: непустой `raw/_incoming/`.
- Frontmatter: одна строка `ключ: значение`; `fetched_at` со смещением.
- `e2e/` и `e2e-runs/` могут отсутствовать — дерево ядра валидно.
- На этом хосте CLI: `py -3`, не `python`.
- Не делать: тикеты (5), баги (7), traces/screenshots в qaswarm git, пакетный прогон, API-e2e из testdocs.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/e2e_scan.py` | Скан `qaswarm_tc`, resolve root из config, classify UI/API/unclear |
| `tools/memory_schema.py` | `validate_e2e_map_card`, `validate_e2e_run_card`, optional dirs |
| `tests/test_e2e_scan.py` | Скан, classify, resolve root |
| `tests/test_memory_schema.py` | Валидация e2e / e2e-runs + регрессия без папок |
| `fixtures/demo-e2e/` | Testdoc, sample py с маркером, incoming, expected канон |
| `.cursor/agents/e2e-builder.md` | Scan/write/run → `_incoming/` |
| `.cursor/agents/librarian.md` | Goals `e2e` / `e2e-run` |
| `.cursor/skills/generate-e2e/SKILL.md` | Поток команды |
| `.cursor/rules/coordinator.mdc` | Маршрутизация + субагент |
| `.cursor/rules/memory-card.mdc` | Пути e2e / e2e-runs |
| `docs/examples/product-config.yaml` | Закомментированный `playwright` |
| `AGENTS.md`, `README.md` | Роль и команда |

**Spec:** `docs/superpowers/specs/2026-08-25-qa-swarm-playwright-e2e-design.md`

---

### Task 1: `e2e_scan` — resolve root, classify, scan markers

**Files:**
- Create: `tools/e2e_scan.py`
- Create: `tests/test_e2e_scan.py`
- Test: `tests/test_e2e_scan.py`

**Interfaces:**
- Consumes: `products/<id>/config.yaml` text or dict; filesystem under playwright root
- Produces:
  - `MARKER_NAME = "qaswarm_tc"`
  - `resolve_playwright_root(config: dict[str, object], env: Mapping[str, str] | None = None) -> Path | None`
  - `classify_channel_class(action: str, expected: str) -> Literal["ui", "api", "unclear"]`
  - `TcBinding(tc_id: str, path: str, nodeid: str)` (dataclass frozen)
  - `scan_qaswarm_tc(root: Path) -> list[TcBinding]`
  - CLI: `py -3 tools/e2e_scan.py --root <path>` prints `tc_id\tpath\tnodeid` lines; exit 2 on duplicate tc_id

- [ ] **Step 1: Write the failing tests**

Create `tests/test_e2e_scan.py`:

```python
from __future__ import annotations

import textwrap
from pathlib import Path

import e2e_scan


def test_resolve_root_prefers_env(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "pw"
    target.mkdir()
    monkeypatch.setenv("UPSERVICE_PLAYWRIGHT_ROOT", str(target))
    cfg = {"playwright": {"root_env": "UPSERVICE_PLAYWRIGHT_ROOT", "root": str(tmp_path / "other")}}
    assert e2e_scan.resolve_playwright_root(cfg) == target.resolve()


def test_resolve_root_falls_back_to_root(tmp_path: Path) -> None:
    target = tmp_path / "pw"
    target.mkdir()
    cfg = {"playwright": {"root": str(target)}}
    assert e2e_scan.resolve_playwright_root(cfg, env={}) == target.resolve()


def test_resolve_root_missing_returns_none() -> None:
    assert e2e_scan.resolve_playwright_root({}, env={}) is None
    assert e2e_scan.resolve_playwright_root({"playwright": {"root": "/no/such"}}, env={}) is None


def test_classify_api_vs_ui() -> None:
    assert e2e_scan.classify_channel_class("GET /v1/tasks", "200 and body has id") == "api"
    assert (
        e2e_scan.classify_channel_class(
            "Открыть личный дашборд Web", "отображается виджет"
        )
        == "ui"
    )
    assert e2e_scan.classify_channel_class("сделать что-то", "ok") == "unclear"


def test_scan_finds_marker(tmp_path: Path) -> None:
    tests = tmp_path / "tests" / "demo"
    tests.mkdir(parents=True)
    (tests / "test_widget.py").write_text(
        textwrap.dedent(
            '''
            import pytest

            @pytest.mark.qaswarm_tc("tc-1-1")
            def test_widget_visible():
                assert True
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    bindings = e2e_scan.scan_qaswarm_tc(tmp_path)
    assert len(bindings) == 1
    assert bindings[0].tc_id == "tc-1-1"
    assert bindings[0].path.replace("\\", "/").endswith("tests/demo/test_widget.py")
    assert bindings[0].nodeid.endswith("test_widget.py::test_widget_visible")


def test_scan_duplicate_tc_raises(tmp_path: Path) -> None:
    tests = tmp_path / "tests"
    tests.mkdir()
    for name in ("a.py", "b.py"):
        (tests / name).write_text(
            'import pytest\n@pytest.mark.qaswarm_tc("tc-1-1")\ndef test_x():\n    pass\n',
            encoding="utf-8",
        )
    try:
        e2e_scan.scan_qaswarm_tc(tmp_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "tc-1-1" in str(exc)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_e2e_scan.py -v`  
Expected: FAIL (module `e2e_scan` missing) or import error.

- [ ] **Step 3: Implement `tools/e2e_scan.py`**

```python
"""Scan Playwright repo for qaswarm_tc markers; classify testdoc channels."""

from __future__ import annotations

import argparse
import ast
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

MARKER_NAME = "qaswarm_tc"

_API_HINT = re.compile(
    r"(?i)\b(GET|POST|PUT|PATCH|DELETE)\b|\b/v1/|\bHTTP\b|\bstatus\s*code\b|\bendpoint\b"
)
_UI_HINT = re.compile(
    r"(?i)\b(открыть|нажать|клик|экран|страниц|виджет|поле|кнопк|дашборд|web|ui|"
    r"open|click|page|screen|widget|button|field|dropdown|modal)\b"
)


@dataclass(frozen=True)
class TcBinding:
    tc_id: str
    path: str
    nodeid: str


def resolve_playwright_root(
    config: dict[str, object], env: Mapping[str, str] | None = None
) -> Path | None:
    import os

    environ = env if env is not None else os.environ
    block = config.get("playwright")
    if not isinstance(block, dict):
        return None
    root_env = block.get("root_env")
    if isinstance(root_env, str) and root_env.strip():
        raw = environ.get(root_env.strip())
        if raw:
            path = Path(raw).expanduser()
            if path.is_dir():
                return path.resolve()
    root = block.get("root")
    if isinstance(root, str) and root.strip():
        path = Path(root.strip()).expanduser()
        if path.is_dir():
            return path.resolve()
    return None


def classify_channel_class(action: str, expected: str) -> Literal["ui", "api", "unclear"]:
    text = f"{action}\n{expected}"
    api = bool(_API_HINT.search(text))
    ui = bool(_UI_HINT.search(text))
    if api and not ui:
        return "api"
    if ui and not api:
        return "ui"
    if ui and api:
        # Prefer UI when both (e.g. "open page then GET") — e2e contour is UI-first.
        return "ui"
    return "unclear"


def _decorator_tc_id(node: ast.AST) -> str | None:
    if not isinstance(node, ast.Call):
        return None
    func = node.func
    # @pytest.mark.qaswarm_tc("id")
    if isinstance(func, ast.Attribute) and func.attr == MARKER_NAME:
        if node.args and isinstance(node.args[0], ast.Constant) and isinstance(
            node.args[0].value, str
        ):
            return node.args[0].value
    return None


def _function_tc_ids(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    found: list[str] = []
    for dec in fn.decorator_list:
        tc = _decorator_tc_id(dec)
        if tc:
            found.append(tc)
    return found


def scan_qaswarm_tc(root: Path) -> list[TcBinding]:
    root = root.resolve()
    tests_root = root / "tests"
    if not tests_root.is_dir():
        return []
    by_id: dict[str, TcBinding] = {}
    duplicates: set[str] = set()
    for path in sorted(tests_root.rglob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError:
            continue
        rel = path.relative_to(root).as_posix()
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if isinstance(node, ast.ClassDef):
                    for item in node.body:
                        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                            for tc_id in _function_tc_ids(item):
                                nodeid = f"{rel}::{node.name}::{item.name}"
                                binding = TcBinding(tc_id, rel, nodeid)
                                if tc_id in by_id and by_id[tc_id] != binding:
                                    duplicates.add(tc_id)
                                by_id[tc_id] = binding
                continue
            for tc_id in _function_tc_ids(node):
                nodeid = f"{rel}::{node.name}"
                binding = TcBinding(tc_id, rel, nodeid)
                if tc_id in by_id and by_id[tc_id] != binding:
                    duplicates.add(tc_id)
                by_id[tc_id] = binding
    if duplicates:
        raise ValueError(f"duplicate qaswarm_tc markers: {sorted(duplicates)}")
    return [by_id[k] for k in sorted(by_id)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        bindings = scan_qaswarm_tc(args.root)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    for b in bindings:
        print(f"{b.tc_id}\t{b.path}\t{b.nodeid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Ensure `tests/` can import `tools/` the same way other tool tests do (existing conftest/`sys.path` — mirror `tests/test_testdoc_merge.py`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_e2e_scan.py -v`  
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/e2e_scan.py tests/test_e2e_scan.py
git commit -m "$(cat <<'EOF'
Add e2e_scan helper for Playwright tc markers and channel class.

EOF
)"
```

---

### Task 2: Schema + fixtures for `e2e/` map cards

**Files:**
- Modify: `tools/memory_schema.py`
- Modify: `tests/test_memory_schema.py`
- Create: `fixtures/demo-e2e/testdocs/task-1.md`
- Create: `fixtures/demo-e2e/expected/e2e/task-1.md`
- Create: `fixtures/demo-e2e/incoming/e2e.md` (draft-ready map used later by Task 3 too)
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: card markdown; optional testdoc path for active id checks
- Produces:
  - `E2E_MAP_REQUIRED`, `E2E_MAP_STATUSES`, `E2E_MAP_CHANNEL_CLASSES`, `E2E_MAP_STATUSES_CASE`
  - `E2eMapCase` dataclass + `parse_e2e_map_cases(body) -> list[E2eMapCase]`
  - `validate_e2e_map_card(path, testdoc_path | None) -> list[str]`
  - `validate_memory_tree`: if `e2e/` exists, validate each `*.md` except `index.md`

- [ ] **Step 1: Write fixtures**

`fixtures/demo-e2e/testdocs/task-1.md`:

```markdown
---
slug: task-1
title: Show widget
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-25T12:00:00+03:00
next_id: 4
---

## Cases

### tc-1-1
title: Widget visible
action: Open personal dashboard Web
expected: widget title is visible
status: active

### tc-1-2
title: API list
action: GET /v1/tasks
expected: 200 and non-empty list
status: active

### tc-1-3
title: Orphan old
action: Old step
expected: Old expect
status: orphan
```

`fixtures/demo-e2e/expected/e2e/task-1.md`:

```markdown
---
slug: task-1
title: Show widget
product: demo
task_id: 1
testdoc: task-1
status: ready
fetched_at: 2026-08-25T12:05:00+03:00
playwright_root: /tmp/demo-playwright
---

## Cases

### tc-1-1
title: Widget visible
channel_class: ui
map_status: mapped
path: tests/demo/test_widget.py
nodeid: tests/demo/test_widget.py::test_widget_visible

### tc-1-2
title: API list
channel_class: api
map_status: out_of_scope
reason: api

### tc-1-3
title: Orphan old
channel_class: ui
map_status: out_of_scope
reason: orphan

## Gaps

- none

Did not write to Upservice or Testmo.
```

`fixtures/demo-e2e/incoming/e2e.md` — same body/frontmatter as expected but **omit** `status:` line (Librarian inserts `ready` or `draft`).

- [ ] **Step 2: Write failing schema tests**

Append to `tests/test_memory_schema.py`:

```python
E2E_EXPECTED_MAP = ROOT / "fixtures" / "demo-e2e" / "expected" / "e2e" / "task-1.md"
E2E_TESTDOC = ROOT / "fixtures" / "demo-e2e" / "testdocs" / "task-1.md"


def test_validate_e2e_map_fixture_ok() -> None:
    assert memory_schema.validate_e2e_map_card(E2E_EXPECTED_MAP, E2E_TESTDOC) == []


def test_validate_e2e_map_ready_requires_ui_closed(tmp_path: Path) -> None:
    text = E2E_EXPECTED_MAP.read_text(encoding="utf-8").replace(
        "map_status: mapped", "map_status: missing", 1
    )
    card = tmp_path / "task-1.md"
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_e2e_map_card(card, E2E_TESTDOC)
    assert any("ready" in e and "missing" in e for e in errors)


def test_demo_catalog_tree_still_valid_without_e2e() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []
```

(`EXPECTED` is the existing `fixtures/demo-catalog/expected` root used by `test_demo_catalog_tree_still_valid_without_runs`.)

- [ ] **Step 3: Run tests — expect FAIL**

Run: `py -3 -m pytest tests/test_memory_schema.py::test_validate_e2e_map_fixture_ok tests/test_memory_schema.py::test_validate_e2e_map_ready_requires_ui_closed -v`  
Expected: FAIL (`validate_e2e_map_card` missing).

- [ ] **Step 4: Implement validation in `memory_schema.py`**

Add constants and parsers next to run validators:

```python
E2E_MAP_REQUIRED = (
    "slug", "title", "product", "task_id", "testdoc", "status", "fetched_at", "playwright_root"
)
E2E_MAP_STATUSES = {"draft", "ready", "stale"}
E2E_MAP_CHANNEL_CLASSES = {"ui", "api", "unclear"}
E2E_MAP_CASE_STATUSES = {"mapped", "missing", "written", "out_of_scope"}


@dataclass
class E2eMapCase:
    case_id: str
    title: str
    channel_class: str
    map_status: str
    path: str
    nodeid: str
    reason: str
```

`parse_e2e_map_cases`: same heading style as run results (`### tc-…` + `ключ: значение` lines).

`validate_e2e_map_card` rules (from spec §7.3):
- required frontmatter; `status` ∈ map statuses; slug/filename; testdoc == slug; task_id rules like runs; fetched_at with tz; `playwright_root` non-empty; secrets check; `## Cases` + `## Gaps`; Upservice/Testmo notice
- each case: channel_class / map_status enums; if map_status in {mapped, written} → path and nodeid required; if missing/out_of_scope → reason recommended (require non-empty reason for missing and out_of_scope)
- if `status: ready`: every testdoc `active` with classify… wait — do **not** re-classify in schema. Instead: for each testdoc `active` id present in map, if that map row has `channel_class: ui` then `map_status` must be `mapped` or `written`. All testdoc `active` ids must appear in map. Orphan rows may be `out_of_scope`.
- Simpler ready rule matching spec: `status: ready` only if every case with `channel_class: ui` and corresponding testdoc status active has map_status in {mapped, written}. When testdoc_path given, every active id must have a map section; active+api must be out_of_scope; active+ui must be mapped|written for ready.

Wire into `validate_memory_tree`:

```python
e2e_dir = root / "e2e"
if e2e_dir.is_dir():
    for card in e2e_dir.glob("*.md"):
        if card.name == "index.md":
            continue
        meta, _ = parse_frontmatter(card.read_text(encoding="utf-8"))
        testdoc_name = meta.get("testdoc", card.stem)
        testdoc_file = testdoc_suite_path(root, testdoc_name)
        testdoc_path = testdoc_file if testdoc_file.is_file() else None
        errors.extend(validate_e2e_map_card(card, testdoc_path))
```

- [ ] **Step 5: Run tests — expect PASS**

Run: `py -3 -m pytest tests/test_memory_schema.py::test_validate_e2e_map_fixture_ok tests/test_memory_schema.py::test_validate_e2e_map_ready_requires_ui_closed -v`  
Expected: PASS. Full file still green: `py -3 -m pytest tests/test_memory_schema.py -v`.

- [ ] **Step 6: Commit**

```bash
git add tools/memory_schema.py tests/test_memory_schema.py fixtures/demo-e2e
git commit -m "$(cat <<'EOF'
Validate e2e mapping cards in memory_schema.

EOF
)"
```

---

### Task 3: Schema + fixtures for `e2e-runs/`

**Files:**
- Modify: `tools/memory_schema.py`
- Modify: `tests/test_memory_schema.py`
- Create: `fixtures/demo-e2e/expected/e2e-runs/task-1.md`
- Create: `fixtures/demo-e2e/incoming/e2e-run.md`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Produces:
  - `E2E_RUN_REQUIRED`, `E2E_RUN_SOURCES = {"playwright"}`, verdicts same as run minus smoke_gate
  - `E2eRunResult` + `parse_e2e_run_results` / `parse_e2e_run_summary`
  - `validate_e2e_run_card(path, e2e_map_path | None) -> list[str]`
  - tree hook for `e2e-runs/`

- [ ] **Step 1: Write fixtures**

`fixtures/demo-e2e/expected/e2e-runs/task-1.md`:

```markdown
---
slug: task-1
title: Show widget
product: demo
task_id: 1
testdoc: task-1
status: ready
fetched_at: 2026-08-25T12:10:00+03:00
source: playwright
e2e: task-1
---

## Summary

pass: 1
fail: 0
blocked: 0
skipped: 0

## Results

### tc-1-1
verdict: pass
nodeid: tests/demo/test_widget.py::test_widget_visible
observed: 1 passed

## Gaps

- none

Did not write to Upservice or Testmo. Did not modify MCP runs/.
```

Incoming `e2e-run.md`: same without `status:` line.

- [ ] **Step 2: Failing tests**

```python
E2E_EXPECTED_RUN = ROOT / "fixtures" / "demo-e2e" / "expected" / "e2e-runs" / "task-1.md"


def test_validate_e2e_run_fixture_ok() -> None:
    assert memory_schema.validate_e2e_run_card(E2E_EXPECTED_RUN, E2E_EXPECTED_MAP) == []


def test_validate_e2e_run_requires_ui_mapped_ids(tmp_path: Path) -> None:
    text = E2E_EXPECTED_RUN.read_text(encoding="utf-8").replace("### tc-1-1\n", "### tc-9-9\n")
    card = tmp_path / "task-1.md"
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_e2e_run_card(card, E2E_EXPECTED_MAP)
    assert any("result ids" in e or "tc-" in e for e in errors)
```

- [ ] **Step 3: Run — expect FAIL**

`py -3 -m pytest tests/test_memory_schema.py::test_validate_e2e_run_fixture_ok -v`

- [ ] **Step 4: Implement `validate_e2e_run_card`**

Rules (spec §7.4):
- required fields including `source: playwright`, `e2e` (== slug in v1)
- Summary integers pass/fail/blocked/skipped (no smoke_gate)
- Results: verdict enum; nodeid required; observed required unless skipped; reason if not pass
- notice must mention Upservice/Testmo; prefer also “MCP runs” / `runs/` as in fixture
- with e2e_map_path: result ids == set of map cases where `map_status in {mapped, written}` and `channel_class == ui` (order = checklist order of those ids in map file)
- counts match summary

Wire `e2e-runs/` in `validate_memory_tree` similarly to runs, pairing with `e2e/<slug>.md` when present.

- [ ] **Step 5: Run — expect PASS**

`py -3 -m pytest tests/test_memory_schema.py -v`  
`py -3 tools/memory_schema.py memory/upservice` → `OK` (no e2e dirs or valid if present).

- [ ] **Step 6: Commit**

```bash
git add tools/memory_schema.py tests/test_memory_schema.py fixtures/demo-e2e
git commit -m "$(cat <<'EOF'
Validate e2e-runs cards and demo fixtures.

EOF
)"
```

---

### Task 4: Subagent `e2e-builder`

**Files:**
- Create: `.cursor/agents/e2e-builder.md`
- Test: file present with frontmatter `name: e2e-builder`

**Interfaces:**
- Consumes: testdoc path, product id, playwright root, config run_command optional
- Produces: `_incoming/e2e.md`, optional `_incoming/e2e-run.md`, `MANIFEST.md`
- Does not write canonical `e2e/` or `e2e-runs/`

- [ ] **Step 1: Write `.cursor/agents/e2e-builder.md`**

```markdown
---
name: e2e-builder
description: Maps testdoc UI cases to Playwright tests, writes missing tests in the external repo, runs pytest, drafts e2e map and e2e-run under raw/_incoming. Never writes canonical memory or Upservice/Testmo.
---

You are the QA swarm e2e-builder. You edit only the external Playwright repo and `memory/<product-id>/raw/_incoming/`.

## When invoked

1. Read the task: product-id, testdoc path `memory/<id>/testdocs/md/<slug>.md`, playwright root, optional run_command.
2. Read testdocs cases. Skip `orphan`. Classify each active case with `py -3 tools/e2e_scan.py` helpers mentally or by running classify via a one-liner — prefer calling:

`py -3 -c "from e2e_scan import classify_channel_class; print(classify_channel_class(...))"`

   from repo root with tools on PYTHONPATH, or apply the same rules as `classify_channel_class` in `tools/e2e_scan.py`.
3. Scan markers:

`py -3 tools/e2e_scan.py --root <playwright_root>`

   Exit 2 → stop; write nothing canonical; report duplicate marker failure. Do not invent bindings.
4. For each active UI case without binding: write or extend a pytest test under playwright root following that repo's skills/rules (`write-ui-test` / `write-e2e-test`, page objects, fixtures). Every new/extended test MUST have `@pytest.mark.qaswarm_tc("<tc-id>")`.
5. Re-scan. If any active UI case still lacks a binding → write `_incoming/e2e.md` with `map_status: missing` for those, API as `out_of_scope`, **do not** write `e2e-run.md`. MANIFEST lists only `e2e.md`. Stop.
6. If all active UI cases are mapped/written: run pytest for those nodeids only. Default command if unset: from playwright root, `py -3 run-tests.py -q <nodeid> ...` or `py -3 -m pytest <nodeid> ...` — use `run_command` from config when provided. Parse pass/fail/blocked/skipped per tc-id.
7. Write `_incoming/e2e.md` (no `status` field) and `_incoming/e2e-run.md` (no `status`, `source: playwright`). MANIFEST lists both. Match shapes in `fixtures/demo-e2e/`.
8. Never write `e2e/`, `e2e-runs/`, `runs/`, Upservice, or Testmo. Do not call browser MCP for verification (Playwright repo MCP is allowed only if needed to author locators, not to fill e2e-run without pytest).

## Incoming shapes

Follow `fixtures/demo-e2e/incoming/`. Include `## Gaps` and the Upservice/Testmo notice. e2e-run notice must also say MCP runs were not modified.
```

- [ ] **Step 2: Commit**

```bash
git add .cursor/agents/e2e-builder.md
git commit -m "$(cat <<'EOF'
Add e2e-builder subagent for Playwright contour.

EOF
)"
```

---

### Task 5: Skill, librarian, coordinator, docs, config

**Files:**
- Create: `.cursor/skills/generate-e2e/SKILL.md`
- Modify: `.cursor/agents/librarian.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `.cursor/rules/memory-card.mdc`
- Modify: `docs/examples/product-config.yaml`
- Modify: `AGENTS.md`
- Modify: `README.md` (add generate-e2e one-liner if other skills listed)
- Test: manual checklist below; `py -3 -m pytest tests/test_e2e_scan.py tests/test_memory_schema.py -v`

**Interfaces:**
- Consumes: Task 1–4 artifacts
- Produces: end-to-end skill wiring; librarian goals `e2e` and `e2e-run`

- [ ] **Step 1: Create `.cursor/skills/generate-e2e/SKILL.md`**

```markdown
---
name: generate-e2e
description: Maps and runs Playwright UI tests for one testdoc suite via an external Playwright repo, storing map and verdict in git memory. Use when the user says сделай e2e, прогони playwright, or e2e для задачи. Does not write to Upservice or Testmo.
---

# generate-e2e

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/testdocs/md/<slug>.md` (ticket id → `task-<id>`). If missing or there is no UI-classifiable `active` case, stop. Tell the user to run `generate-testdocs` first. Do not start scribe/verifier or invent cases from chat.
3. Load `products/<id>/config.yaml`. Resolve playwright root via `tools/e2e_scan.resolve_playwright_root` (or equivalent). If none, stop and ask for `playwright.root_env` / `playwright.root`.
4. Launch `e2e-builder` with testdoc path, product id, playwright root, optional `run_command`. Builder writes `_incoming/` only.
5. After MANIFEST lists `e2e.md`:
   - If MANIFEST also lists `e2e-run.md`, launch `librarian` with goal `e2e` then ensure run written (goal `e2e-run` or single invocation handling both).
   - If only `e2e.md`, launch `librarian` with goal `e2e` (draft map only).
6. Report paths, missing/written counts, and pass/fail/blocked/skipped if run exists. Say e2e is ready only if `e2e/<slug>.md` has `status: ready`, `e2e-runs/<slug>.md` exists, and `py -3 tools/memory_schema.py memory/<id>` would pass.
7. Never write to Upservice or Testmo. Do not modify `runs/`. Do not start generate-testdocs, analyze-requirement, or verify-testdocs from this skill.
```

If Task tool enum in the harness does not yet list `e2e-builder`, launch with `subagent_type: generalPurpose` and instruct it to follow `.cursor/agents/e2e-builder.md` verbatim; still document the agent name as `e2e-builder` in coordinator/AGENTS.

- [ ] **Step 2: Extend librarian**

In `.cursor/agents/librarian.md`:

- Add paths `e2e/index.md`, `e2e/<slug>.md`, `e2e-runs/index.md`, `e2e-runs/<slug>.md` to Canonical paths.
- Extend “When invoked” goals list with `e2e` | `e2e-run`.
- New sections:

**E2e map incoming:** If MANIFEST lists `e2e.md`: do not invent bindings. Copy to `e2e/<slug>.md`. Set `status: ready` if every UI active (per incoming channel_class + testdoc active) is `mapped`|`written`; else `status: draft`. Update `e2e/index.md` table: Slug | Testdoc | Status | Mapped UI | Missing UI | Card. Redact secrets. If CSV/testdoc helpers are unrelated, skip them.

**E2e-run incoming:** If MANIFEST lists `e2e-run.md`: require matching `e2e/<slug>.md` ready (or write map first in same invocation). Do not recalculate verdicts. Result ids must equal UI mapped|written set from the map card. Insert `status: ready`, `source: playwright`. Overwrite `e2e-runs/<slug>.md`. Update `e2e-runs/index.md`: Slug | Testdoc | Pass | Fail | Blocked | Skipped | Source | Card. If only `e2e.md` in MANIFEST, do **not** create/update `e2e-runs/<slug>.md`.

Match `fixtures/demo-e2e/expected/`.

- [ ] **Step 3: Update coordinator + memory-card + AGENTS + example config + README**

`coordinator.mdc`:
- Skills include `generate-e2e`.
- Subagents include `e2e-builder`.
- New paragraph: For generate-e2e: only if testdocs has UI-active; e2e-builder drafts `_incoming/e2e.md` (+ `e2e-run.md`); librarian writes `e2e/` and `e2e-runs/`. Do not start verify-testdocs. Do not write Upservice/Testmo. Do not modify `runs/`.

`memory-card.mdc`: document `e2e/` and `e2e-runs/` like runs (run `source` note: e2e-run source is `playwright`).

`AGENTS.md`:
- Role bullet for `e2e-builder`.
- Spec link to `2026-08-25-qa-swarm-playwright-e2e-design.md`.
- Clarify Do not do in v1: writing tickets; self-contained Playwright suite inside qaswarm; (orchestrated generate-e2e is allowed).

`docs/examples/product-config.yaml` append:

```yaml
# playwright:
#   root_env: UPSERVICE_PLAYWRIGHT_ROOT
#   # root: C:/path/to/upservice_playwright_testing
#   # run_command: py -3 run-tests.py
```

README: one line under skills/commands for generate-e2e.

- [ ] **Step 4: Validate**

```bash
py -3 -m pytest tests/test_e2e_scan.py tests/test_memory_schema.py -v
py -3 tools/memory_schema.py memory/upservice
```

Expected: pytest all PASS; schema `OK`.

- [ ] **Step 5: Commit**

```bash
git add .cursor/skills/generate-e2e/SKILL.md .cursor/agents/librarian.md .cursor/rules/coordinator.mdc .cursor/rules/memory-card.mdc docs/examples/product-config.yaml AGENTS.md README.md
git commit -m "$(cat <<'EOF'
Wire generate-e2e skill and librarian for Playwright contour.

EOF
)"
```

---

### Task 6: Playwright-repo marker registration (outside qaswarm memory)

**Files (external repo `upservice_playwright_testing`):**
- Modify: `pytest.ini` or `tests/conftest.py` — register marker `qaswarm_tc(tc_id)`.
- Optional doc blurb in that repo’s `AGENTS.md`.

**Interfaces:**
- Produces: pytest accepts `@pytest.mark.qaswarm_tc("tc-…")` without unknown-marker warnings.

- [ ] **Step 1: Register marker in Playwright repo**

In `pytest.ini` under `[pytest]` `markers =`:

```ini
qaswarm_tc(tc_id): link to QA swarm testdoc case id (tc-…)
```

Or in `conftest.py`:

```python
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "qaswarm_tc(tc_id): QA swarm testdoc case id"
    )
```

- [ ] **Step 2: Smoke**

From Playwright root: `py -3 -m pytest --markers | findstr qaswarm_tc` (Windows) — marker listed.

- [ ] **Step 3: Commit in that repo** (separate git root; only if user wants)

Do not commit Playwright-repo changes into `qaswarm`.

---

## Spec coverage checklist (self-review)

| Spec section | Task |
|--------------|------|
| §2 generate+run, UI only, external repo | 4, 5 |
| §4 hybrid map + missing write | 4 |
| §5 architecture / lock incoming | 4, 5 |
| §6 paths e2e / e2e-runs | 2, 3, 5 |
| §7.1 marker `qaswarm_tc` | 1, 6 |
| §7.2 classify | 1, 4 |
| §7.3 map card | 2, 5 |
| §7.4 e2e-run card | 3, 5 |
| §7.5 incoming draft vs run | 4, 5 |
| §8 schema + demo fixture | 2, 3 |
| §9 skill flow | 5 |
| §10 errors | 1 (dup), 4–5 |
| §11 scenarios | fixtures 2–3; manual live optional |
| §12 config root_env | 1, 5 |
| §13 implementation list | all |
| §14 deferred | not implemented (YAGNI) |

**Placeholder scan:** none intentional; `run_command` fallback documented as `run-tests.py` / pytest in Task 4.

**Type consistency:** `TcBinding`, `MARKER_NAME`, `map_status` values, `source: playwright` aligned across tasks.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-25-qa-swarm-playwright-e2e.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — execute tasks in this session with executing-plans checkpoints  

Which approach?
