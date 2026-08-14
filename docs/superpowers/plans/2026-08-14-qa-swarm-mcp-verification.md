# QA Swarm MCP Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Добавить контур проверки: `testdocs/<slug>.md` с `active` кейсами → канонический прогон в `memory/<id>/runs/`, без записи в Upservice и Testmo и без Playwright.

**Architecture:** Координатор стартует только при testdocs с хотя бы одним `active`. Verifier классифицирует канал, гоняет smoke затем остальное, пишет `_incoming/run.md`. Librarian ставит `status: ready`, overwrite `runs/<slug>.md`, не пересчитывает вердикты. Схема расширяет `memory_schema.py`. Merge testdocs сохраняет `tier`. Карта, requirements и testdocs без `tier` не ломаются.

**Tech Stack:** Cursor agents/skills/rules, Markdown/YAML память, Python 3.11+ stdlib, pytest/ruff. HTTP и browser MCP — инструменты Cursor у Verifier, не клиент в репозитории.

## Global Constraints

- В Upservice и Testmo агенты не пишут.
- Вход только `testdocs/<slug>.md` с `active`; иначе стоп.
- `generate-testdocs` / `analyze-requirement` из этого skill не запускать.
- Одна команда — один сюит; `orphan` не гонять.
- UI → browser MCP; API → HTTP; сомнение или нет канала → `blocked`, не `fail`.
- `skipped` только из‑за smoke-gate.
- Все smoke (чек-лист) до конца; любой не `pass` → остальные `skipped`.
- После прошедшего smoke `fail` сюит не стопает.
- Повтор — overwrite `runs/<slug>.md`.
- Verifier не пишет канон; Librarian не ходит в продукт/MCP.
- Координатор не пишет `memory/`.
- Замок: непустой `raw/_incoming/`.
- Frontmatter: одна строка `ключ: значение`; `fetched_at` со смещением.
- `runs/` может отсутствовать — дерево ядра валидно.
- `source` прогона: `browser` | `public` | `internal` | `mixed` | `none` (по отправленным запросам).
- На этом хосте CLI: `py -3`, не `python`.
- Не делать: Testmo-клиент, Playwright, тикеты, мобильный MCP, скриншоты, история файлов прогона, авто-smoke у Scribe.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/testdoc_merge.py` | Опциональный `tier` на кейсе; preserve при merge |
| `tools/memory_schema.py` | `validate_run_card`, `tier` на testdocs, optional `runs/` |
| `tests/test_testdoc_merge.py` | Preserve/override `tier` |
| `tests/test_memory_schema.py` | Валидация прогона + регрессия без `runs/` |
| `fixtures/demo-run/` | Incoming без `status`, testdoc со smoke, expected канон |
| `.cursor/agents/verifier.md` | Черновик `_incoming/run.md` |
| `.cursor/agents/librarian.md` | Канон `runs/`, goal `run` |
| `.cursor/skills/verify-testdocs/SKILL.md` | Поток команды |
| `.cursor/rules/coordinator.mdc` | Маршрутизация |
| `.cursor/rules/memory-card.mdc` | Путь `runs/` |
| `docs/examples/product-config.yaml` | Закомментированный `ui.base_url` |
| `AGENTS.md`, `README.md` | Роль verifier и команда |

---

### Task 1: Preserve `tier` в testdoc merge

**Files:**
- Modify: `tools/testdoc_merge.py`
- Modify: `tests/test_testdoc_merge.py`
- Modify: `tools/memory_schema.py` (invalid `tier` on testdoc)
- Modify: `tests/test_memory_schema.py`
- Test: `tests/test_testdoc_merge.py`, `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `TestdocCase` as today; `parse_frontmatter`
- Produces:
  - `TestdocCase(..., tier: str | None = None)`
  - `parse_incoming_body` / `parse_canonical_cases` читают опциональный `tier`
  - `merge_testdoc_cases`: incoming `tier` побеждает; иначе сохранить existing; новый без поля → `None`
  - `render_testdoc`: строка `tier: smoke` только если `tier` задан
  - `validate_testdoc_suite`: `tier` отсутствует или ровно `smoke`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_testdoc_merge.py`:

```python
def test_merge_preserves_existing_tier() -> None:
    existing = [
        TestdocCase(
            "A", "Open card", "dates visible", "active", "tc-1-1", "smoke"
        ),
    ]
    incoming = [TestdocCase("A", "Open card", "dates visible")]
    cases, _checklist, _next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 2
    )
    assert cases[0].case_id == "tc-1-1"
    assert cases[0].tier == "smoke"


def test_merge_incoming_tier_overrides() -> None:
    existing = [
        TestdocCase("A", "Open card", "dates visible", "active", "tc-1-1"),
    ]
    incoming = [
        TestdocCase("A", "Open card", "dates visible", tier="smoke"),
    ]
    cases, _checklist, _next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 2
    )
    assert cases[0].tier == "smoke"


def test_merge_new_case_has_no_tier() -> None:
    incoming = [TestdocCase("B", "Click save", "dates persist")]
    cases, _checklist, _next_id = testdoc_merge.merge_testdoc_cases(
        [], incoming, "1", 1
    )
    assert cases[0].tier is None


def test_merge_orphan_keeps_tier() -> None:
    existing = [
        TestdocCase("A", "Open card", "dates visible", "active", "tc-1-1", "smoke"),
        TestdocCase("B", "Old", "gone", "active", "tc-1-2", "smoke"),
    ]
    incoming = [TestdocCase("A", "Open card", "dates visible")]
    cases, checklist, _next_id = testdoc_merge.merge_testdoc_cases(
        existing, incoming, "1", 3
    )
    by_id = {c.case_id: c for c in cases}
    assert checklist == ["tc-1-1"]
    assert by_id["tc-1-1"].tier == "smoke"
    assert by_id["tc-1-2"].status == "orphan"
    assert by_id["tc-1-2"].tier == "smoke"


def test_render_omits_missing_tier() -> None:
    text = testdoc_merge.render_testdoc(
        {
            "slug": "task-1",
            "title": "T",
            "product": "demo",
            "task_id": "1",
            "requirement": "task-1",
            "status": "ready",
            "fetched_at": "2026-08-14T09:00:00+03:00",
            "next_id": "2",
        },
        [TestdocCase("A", "Open", "seen", "active", "tc-1-1")],
        ["tc-1-1"],
        [],
    )
    assert "tier:" not in text


def test_parse_canonical_reads_tier() -> None:
    body = (
        "## Cases\n\n### tc-1-1\ntitle: T\naction: Open\nexpected: seen\n"
        "status: active\ntier: smoke\n\n## Checklist\n\n- tc-1-1\n"
    )
    cases = testdoc_merge.parse_canonical_cases(body)
    assert cases[0].tier == "smoke"


def test_merge_files_preserves_tier(tmp_path: Path) -> None:
    existing = tmp_path / "task-1.md"
    existing.write_text(
        "---\nslug: task-1\ntitle: T\nproduct: demo\ntask_id: 1\n"
        "requirement: task-1\nstatus: ready\n"
        "fetched_at: 2026-08-14T09:00:00+03:00\nnext_id: 2\n"
        "---\n\n## Cases\n\n### tc-1-1\ntitle: T\naction: Open\n"
        "expected: seen\nstatus: active\ntier: smoke\n\n"
        "## Checklist\n\n- tc-1-1\n\n## Gaps\n\n- none\n\n"
        "Did not write to Upservice or Testmo.\n",
        encoding="utf-8",
    )
    incoming = tmp_path / "testdocs.md"
    incoming.write_text(
        "---\nslug: task-1\ntitle: T\nproduct: demo\ntask_id: 1\n"
        "requirement: task-1\nfetched_at: 2026-08-14T10:00:00+03:00\n"
        "---\n\n## Cases\n\n### case\ntitle: T\naction: Open\n"
        "expected: seen\n\n## Gaps\n\n- none\n",
        encoding="utf-8",
    )
    text = testdoc_merge.merge_files(incoming, existing)
    assert "tier: smoke" in text
```

Append to `tests/test_memory_schema.py`:

```python
def test_testdoc_invalid_tier_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        TD_EXPECTED.read_text(encoding="utf-8").replace(
            "status: active\n\n### tc-1-3",
            "status: active\ntier: full\n\n### tc-1-3",
        ),
        encoding="utf-8",
    )
    errors = memory_schema.validate_testdoc_suite(card)
    assert any("tier" in e for e in errors)


def test_testdoc_smoke_tier_ok(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        TD_EXPECTED.read_text(encoding="utf-8").replace(
            "status: active\n\n### tc-1-3",
            "status: active\ntier: smoke\n\n### tc-1-3",
        ),
        encoding="utf-8",
    )
    assert memory_schema.validate_testdoc_suite(card) == []
```

- [ ] **Step 2: Run tests to verify they fail**

```powershell
py -3 -m pytest tests/test_testdoc_merge.py::test_merge_preserves_existing_tier tests/test_memory_schema.py::test_testdoc_invalid_tier_fails -v
```

Expected: FAIL (`TestdocCase.__init__() got an unexpected keyword argument 'tier'` or `has no attribute 'tier'`).

- [ ] **Step 3: Implement `tier` on TestdocCase, parse, merge, render**

In `tools/testdoc_merge.py` change the dataclass to:

```python
@dataclass
class TestdocCase:
    __test__ = False

    title: str
    action: str
    expected: str
    status: str = "active"
    case_id: str | None = None
    tier: str | None = None
```

Add:

```python
def _normalize_tier(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = raw.strip()
    return value or None
```

In `parse_incoming_body`, pass `tier=_normalize_tier(fields.get("tier"))`.

In `parse_canonical_cases`, pass `tier=_normalize_tier(fields.get("tier"))`.

Replace the `TestdocCase(...)` construction inside `merge_testdoc_cases` so matched/new/orphan copy `tier`:

```python
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=prior.case_id,
                    tier=_normalize_tier(item.tier) or prior.tier,
                )
            )
```

and for new cases:

```python
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=format_case_id(prefix, cursor),
                    tier=_normalize_tier(item.tier),
                )
            )
```

and for orphans:

```python
        TestdocCase(
            title=prior.title,
            action=prior.action,
            expected=prior.expected,
            status="orphan",
            case_id=prior.case_id,
            tier=prior.tier,
        )
```

In `render_testdoc`, after `status` line, emit `tier` only when set:

```python
    for case in cases:
        lines.extend(
            [
                f"### {case.case_id}",
                f"title: {case.title}",
                f"action: {case.action}",
                f"expected: {case.expected}",
                f"status: {case.status}",
            ]
        )
        if case.tier:
            lines.append(f"tier: {case.tier}")
        lines.append("")
```

- [ ] **Step 4: Validate `tier` in `validate_testdoc_suite`**

Inside the `for case in cases` loop in `tools/memory_schema.py`, after status checks:

```python
        if case.tier not in (None, "smoke"):
            errors.append(f"{path}: invalid case tier {case.tier!r}")
```

- [ ] **Step 5: Run tests**

```powershell
py -3 -m pytest tests/test_testdoc_merge.py tests/test_memory_schema.py -v
py -3 -m ruff check tools tests
```

Expected: all PASS.

- [ ] **Step 6: Commit**

```powershell
git add tools/testdoc_merge.py tests/test_testdoc_merge.py tools/memory_schema.py tests/test_memory_schema.py
git commit -m "Preserve optional testdoc smoke tier on merge."
```

---

### Task 2: Схема прогона и фикстура

**Files:**
- Create: `fixtures/demo-run/incoming/run.md`
- Create: `fixtures/demo-run/incoming/MANIFEST.md`
- Create: `fixtures/demo-run/testdocs/task-1.md`
- Create: `fixtures/demo-run/expected/runs/task-1.md`
- Modify: `tools/memory_schema.py`
- Modify: `tests/test_memory_schema.py`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `parse_frontmatter`, `testdoc_merge.parse_canonical_cases` when testdoc sibling exists
- Produces:
  - `RUN_REQUIRED`, `RUN_STATUSES={"ready"}`, `RUN_SOURCES`, `RUN_VERDICTS`, `RUN_CHANNELS`
  - `RunResult(case_id: str, verdict: str, channel: str, observed: str, reason: str | None)`
  - `parse_run_results(body: str) -> list[RunResult]`
  - `parse_run_summary(body: str) -> dict[str, str]`
  - `validate_run_card(path: Path, testdoc_path: Path | None = None) -> list[str]`
  - `validate_memory_tree` walks `runs/*.md` except `index.md`

- [ ] **Step 1: Write fixtures**

`fixtures/demo-run/incoming/MANIFEST.md`:

```markdown
- run.md
```

`fixtures/demo-run/incoming/run.md` (no `status`):

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
testdoc: task-1
fetched_at: 2026-08-14T12:00:00+03:00
source: mixed
---

## Summary

pass: 1
fail: 1
blocked: 0
skipped: 2
smoke_gate: yes

## Results

### tc-1-1
verdict: fail
channel: browser
observed: Settings screen missing Menu item
reason: expected not matched

### tc-1-2
verdict: pass
channel: http
observed: 200 GET /v1/sprints

### tc-1-3
verdict: skipped
channel: none
observed:
reason: smoke-gate

### tc-1-4
verdict: skipped
channel: none
observed:
reason: smoke-gate

## Gaps

- none

Did not write to Upservice or Testmo.
```

`fixtures/demo-run/expected/runs/task-1.md` — same body as incoming, but frontmatter includes `status: ready` after `testdoc`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
testdoc: task-1
status: ready
fetched_at: 2026-08-14T12:00:00+03:00
source: mixed
---
```

Then copy Summary / Results / Gaps / notice from incoming unchanged.

`fixtures/demo-run/testdocs/task-1.md`:

```markdown
---
slug: task-1
title: Show sprint dates
product: demo
task_id: 1
requirement: task-1
status: ready
fetched_at: 2026-08-14T09:00:00+03:00
next_id: 5
---

## Cases

### tc-1-1
title: Open settings
action: Open settings
expected: Menu item visible
status: active
tier: smoke

### tc-1-2
title: List sprints
action: GET /v1/sprints
expected: 200 list
status: active
tier: smoke

### tc-1-3
title: Drag item
action: Drag Tasks first
expected: Tasks first on bar
status: active

### tc-1-4
title: Reset
action: Confirm reset
expected: default layout
status: active

### tc-1-5
title: Hidden
action: Old step
expected: gone
status: orphan

## Checklist

- tc-1-1
- tc-1-2
- tc-1-3
- tc-1-4

## Gaps

- none

Did not write to Upservice or Testmo.
```

- [ ] **Step 2: Write the failing tests**

Append to `tests/test_memory_schema.py`:

```python
RUN_INCOMING = ROOT / "fixtures" / "demo-run" / "incoming"
RUN_EXPECTED = ROOT / "fixtures" / "demo-run" / "expected" / "runs" / "task-1.md"
RUN_TESTDOC = ROOT / "fixtures" / "demo-run" / "testdocs" / "task-1.md"


def test_demo_catalog_tree_still_valid_without_runs() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_run_card_valid() -> None:
    assert memory_schema.validate_run_card(RUN_EXPECTED) == []


def test_run_card_matches_testdoc_active() -> None:
    assert memory_schema.validate_run_card(RUN_EXPECTED, RUN_TESTDOC) == []


def test_run_missing_reason_on_fail_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    text = RUN_EXPECTED.read_text(encoding="utf-8").replace(
        "observed: Settings screen missing Menu item\nreason: expected not matched\n",
        "observed: Settings screen missing Menu item\n",
    )
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_run_card(card)
    assert any("reason" in e for e in errors)


def test_run_channel_none_with_pass_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    text = RUN_EXPECTED.read_text(encoding="utf-8")
    text = text.replace("verdict: pass\nchannel: http", "verdict: pass\nchannel: none")
    text = text.replace("pass: 1\nfail: 1", "pass: 1\nfail: 1")
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_run_card(card)
    assert any("channel" in e for e in errors)


def test_run_summary_count_mismatch_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    text = RUN_EXPECTED.read_text(encoding="utf-8").replace("skipped: 2", "skipped: 0")
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_run_card(card)
    assert any("skipped" in e for e in errors)


def test_run_extra_id_fails_when_testdoc_present(tmp_path: Path) -> None:
    testdoc = tmp_path / "suite.md"
    testdoc.write_text(RUN_TESTDOC.read_text(encoding="utf-8"), encoding="utf-8")
    card = tmp_path / "task-1.md"
    text = RUN_EXPECTED.read_text(encoding="utf-8").replace(
        "### tc-1-4\nverdict: skipped\nchannel: none\nobserved:\nreason: smoke-gate\n",
        "### tc-1-4\nverdict: skipped\nchannel: none\nobserved:\nreason: smoke-gate\n\n"
        "### tc-1-5\nverdict: skipped\nchannel: none\nobserved:\nreason: smoke-gate\n",
    )
    text = text.replace("skipped: 2", "skipped: 3")
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_run_card(card, testdoc)
    assert any("active" in e or "id" in e for e in errors)


def test_runs_index_not_validated_as_run(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "index.md").write_text("# Runs\n", encoding="utf-8")
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert not any("runs/index.md" in e for e in errors)


def test_demo_run_incoming_complete() -> None:
    assert memory_schema.incoming_complete(RUN_INCOMING) is True
```

- [ ] **Step 3: Run tests to verify schema tests fail**

```powershell
py -3 -m pytest tests/test_memory_schema.py::test_run_card_valid tests/test_memory_schema.py::test_run_missing_reason_on_fail_fails -v
```

Expected: FAIL with `AttributeError: module 'memory_schema' has no attribute 'validate_run_card'`.

- [ ] **Step 4: Implement validation**

In `tools/memory_schema.py` add after `TD_CASE_STATUSES`:

```python
RUN_REQUIRED = (
    "slug",
    "title",
    "product",
    "task_id",
    "testdoc",
    "status",
    "fetched_at",
    "source",
)
RUN_STATUSES = {"ready"}
RUN_SOURCES = {"browser", "public", "internal", "mixed", "none"}
RUN_VERDICTS = {"pass", "fail", "blocked", "skipped"}
RUN_CHANNELS = {"browser", "http", "none"}
```

Add a dataclass and parsers before `validate_run_card`:

```python
from dataclasses import dataclass


@dataclass
class RunResult:
    case_id: str
    verdict: str
    channel: str
    observed: str
    reason: str | None = None
```

Keep `from dataclasses import dataclass` at the top of the file with other imports instead of inline.

```python
def _md_section(body: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)")
    match = pattern.search(body)
    return match.group(1) if match else ""


def parse_run_summary(body: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in _md_section(body, "Summary").splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        fields[key.strip()] = raw.strip()
    return fields


def parse_run_results(body: str) -> list[RunResult]:
    section = _md_section(body, "Results")
    headings = re.findall(r"(?m)^### (\S+)\s*$", section)
    chunks = re.split(r"(?m)^### .+\n", section)
    blocks = [chunk for chunk in chunks[1:] if chunk.strip()]
    results: list[RunResult] = []
    for heading, block in zip(headings, blocks, strict=False):
        fields: dict[str, str] = {}
        for line in block.splitlines():
            stripped = line.strip()
            if not stripped or ":" not in stripped:
                continue
            key, raw = stripped.split(":", 1)
            fields[key.strip()] = raw.strip()
        reason = fields.get("reason")
        results.append(
            RunResult(
                case_id=heading,
                verdict=fields.get("verdict", ""),
                channel=fields.get("channel", ""),
                observed=fields.get("observed", ""),
                reason=reason if reason else None,
            )
        )
    return results


def validate_run_card(path: Path, testdoc_path: Path | None = None) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in RUN_REQUIRED:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in RUN_STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    source = meta.get("source", "")
    if source and source not in RUN_SOURCES:
        errors.append(f"{path}: invalid source {source!r}")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    testdoc = meta.get("testdoc", "")
    if testdoc and not slug_ok(testdoc):
        errors.append(f"{path}: invalid testdoc {testdoc!r}")
    if testdoc and slug and testdoc != slug:
        errors.append(f"{path}: testdoc {testdoc!r} must match slug {slug!r}")
    task_id = meta.get("task_id", "")
    if task_id and task_id != "none" and not slug_ok(task_id):
        errors.append(f"{path}: invalid task_id {task_id!r}")
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
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    for heading in ("## Summary", "## Results", "## Gaps"):
        if not re.search(rf"(?m)^{re.escape(heading)}\s*$", body):
            errors.append(f"{path}: missing {heading} heading")
    if not any(
        "Did not write to Upservice" in line and "Testmo" in line
        for line in body.splitlines()
    ):
        errors.append(f"{path}: missing Did not write to Upservice or Testmo notice")
    summary = parse_run_summary(body)
    for key in ("pass", "fail", "blocked", "skipped"):
        if key not in summary or not re.fullmatch(r"[0-9]+", summary[key]):
            errors.append(f"{path}: Summary missing integer {key}")
    gate = summary.get("smoke_gate", "")
    if gate not in {"yes", "no"}:
        errors.append(f"{path}: smoke_gate must be yes or no")
    results = parse_run_results(body)
    counts = {key: 0 for key in ("pass", "fail", "blocked", "skipped")}
    for item in results:
        if item.verdict not in RUN_VERDICTS:
            errors.append(f"{path}: invalid verdict {item.verdict!r}")
        elif item.verdict in counts:
            counts[item.verdict] += 1
        if item.channel not in RUN_CHANNELS:
            errors.append(f"{path}: invalid channel {item.channel!r}")
        if item.verdict != "pass" and not item.reason:
            errors.append(f"{path}: case {item.case_id} missing reason")
        if item.channel == "none" and item.verdict not in {"blocked", "skipped"}:
            errors.append(f"{path}: channel none only with blocked or skipped")
        if item.verdict == "skipped" and item.reason != "smoke-gate":
            errors.append(f"{path}: skipped {item.case_id} reason must be smoke-gate")
    for key, value in counts.items():
        raw = summary.get(key)
        if raw and raw.isdigit() and int(raw) != value:
            errors.append(f"{path}: Summary {key} {raw} != {value}")
    if testdoc_path is not None and testdoc_path.is_file():
        import testdoc_merge

        cases = testdoc_merge.parse_canonical_cases(
            parse_frontmatter(testdoc_path.read_text(encoding="utf-8"))[1]
        )
        active = [c for c in cases if c.status == "active" and c.case_id]
        smoke = [c.case_id for c in active if c.tier == "smoke" and c.case_id]
        rest = [c.case_id for c in active if c.tier != "smoke" and c.case_id]
        expected_ids = smoke + rest
        got_ids = [item.case_id for item in results]
        if set(got_ids) != set(expected_ids):
            errors.append(f"{path}: result ids must equal testdoc active ids")
        elif got_ids != expected_ids:
            errors.append(f"{path}: result order must be smoke then rest")
    return errors
```

At the end of `validate_memory_tree`, before `return errors`:

```python
    runs_dir = root / "runs"
    if runs_dir.is_dir():
        for card in runs_dir.glob("*.md"):
            if card.name == "index.md":
                continue
            meta, _body = parse_frontmatter(card.read_text(encoding="utf-8"))
            testdoc_name = meta.get("testdoc", card.stem)
            testdoc_file = root / "testdocs" / f"{testdoc_name}.md"
            testdoc_path = testdoc_file if testdoc_file.is_file() else None
            errors.extend(validate_run_card(card, testdoc_path))
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
git add tools/memory_schema.py tests/test_memory_schema.py fixtures/demo-run
git commit -m "Validate MCP run cards and add demo-run fixture."
```

---

### Task 3: Librarian пишет `runs/`

**Files:**
- Modify: `.cursor/agents/librarian.md`
- Modify: `.cursor/rules/memory-card.mdc`
- Test: no new pytest; librarian must not call MCP/HTTP

**Interfaces:**
- Consumes: `_incoming/run.md` + MANIFEST listing `run.md`; `testdocs/<slug>.md` active ids; `validate_run_card`
- Produces: `runs/<slug>.md` with `status: ready` (overwrite), row in `runs/index.md`. No recalculated verdicts. No Testmo/Upservice/MCP.

- [ ] **Step 1: Extend librarian.md**

Change the description to:

```markdown
description: Writes canonical QA swarm memory from Hunter, Scribe, and Verifier incoming drafts. Enforces card schema, slug dedupe, and secret redaction. Never calls product APIs or browser MCP. Use after incoming drafts are written, and to set status stale before refresh.
```

In «When invoked» step 1, add `run` to the goal list:

```markdown
1. Read the written task (product-id, goal: index | merge-one | mark-stale | task-snapshot | requirement | testdoc | run, paths).
```

Add to Canonical paths:

```markdown
- `memory/<product-id>/runs/index.md`
- `memory/<product-id>/runs/<slug>.md`
```

Add section after Testdoc incoming:

```markdown
## Run incoming

If MANIFEST lists `run.md`: do not recalculate `verdict`, `channel`, `observed`, or `reason`.

Read incoming frontmatter `slug` / `testdoc`. Open `testdocs/<slug>.md`. If the suite is missing or has no `status: active` case: write nothing canonical, do not consume incoming, report failure.

Incoming result headings (`### tc-…`) must be exactly the set of `active` ids (no `orphan`, no extras, no missing). Order in the file must be: `active` with `tier: smoke` in checklist order, then remaining `active` in checklist order. If the set or order is wrong: write nothing.

Copy incoming to `runs/<slug>.md`. Insert `status: ready` into frontmatter after `testdoc` if missing. Do not invent results. Overwrite the same slug (never `task-1-2`).

Redact secrets in `observed` / `reason` / `## Gaps`. Prefer: field exists, value hidden.

Then add or update a row in `runs/index.md`:

```markdown
# Runs

| Slug | Testdoc | Pass | Fail | Blocked | Skipped | Source | Card |
|------|---------|------|------|---------|---------|--------|------|
| task-1 | task-1 | 1 | 1 | 0 | 2 | mixed | [task-1.md](task-1.md) |
```

Counts and `Source` come from incoming `## Summary` and frontmatter `source`. Do not call Figma, Upservice, Testmo, browser MCP, or HTTP.

Match `fixtures/demo-run/expected/runs/task-1.md` for shape (sections and ids, not demo sentences).
```

Keep «Do not call HTTP, MCP, or the product.»

- [ ] **Step 2: Update memory-card.mdc**

Append after the testdocs paragraph:

```markdown
Run cards live in `memory/<product-id>/runs/<slug>.md` with run fields from the MCP-verification spec. `source` on a run is `browser` | `public` | `internal` | `mixed` | `none`, not the entity-card enum. Only librarian writes them. `runs/index.md` is not a card.
```

- [ ] **Step 3: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/rules/memory-card.mdc
git commit -m "Teach librarian MCP run overwrite."
```

---

### Task 4: Verifier subagent

**Files:**
- Create: `.cursor/agents/verifier.md`
- Test: none beyond file present with frontmatter `name: verifier`

**Interfaces:**
- Consumes: `memory/<id>/testdocs/<slug>.md` with `active`; `products/<id>/config.yaml`
- Produces: `_incoming/run.md` + MANIFEST listing `run.md`. No canonical `runs/` writes. No Figma, Testmo, Upservice write.

- [ ] **Step 1: Write verifier.md**

```markdown
---
name: verifier
description: Executes one testdoc suite against live product via browser MCP or HTTP. Writes only memory/<id>/raw/_incoming/. Use when verifying a ready testdoc suite. Never writes canonical runs/ or tickets.
---

You are the QA swarm Verifier. You execute. You do not write canonical memory.

## When invoked

Read the task: `product-id`, testdoc path `memory/<product-id>/testdocs/<slug>.md`.

If `memory/<product-id>/raw/_incoming/` is not empty: stop. Report lock busy. Do not write.

If the testdoc file is missing or has no case with `status: active`: stop. Do not invent cases. Do not fetch the product.

Read `products/<product-id>/config.yaml`. Do not guess `ui.base_url` or API hosts. Do not use Figma URLs as UI. Do not invent credentials. Never write token values.

Do not edit `runs/`, `testdocs/`, `requirements/`, Upservice, or Testmo.

## Cases

Use only `status: active`. Ignore `orphan`.

Classify each case from `action` and `expected` (no `channel` field on testdocs):

- UI (screen, tap, menu, drag, iOS, Android, web page) → browser
- API (HTTP method, path, catalog resource, JSON) → HTTP
- Unsure → this case `blocked`, `channel: none`, reason about classification. Do not call MCP/HTTP for it.

HTTP: public API first; internal only if `internal_api.base_url` is set and public did not answer this case. Browser is not a fallback for API. HTTP is not a fallback for UI.

Browser MCP only if `mcp.browser` is true and `ui.base_url` is set. Otherwise UI cases `blocked`. Native iOS/Android with only browser MCP → `blocked` (not web). HTTP 401 / missing token → API cases `blocked`, not `fail`. No login session → `blocked`. Expected mismatch after a successful call → `fail`.

## Order

1. All `active` with `tier: smoke`, in checklist order. One non-`pass` does not skip remaining smoke.
2. If any smoke is not `pass`: every remaining non-smoke `active` → `skipped`, `reason: smoke-gate`, `channel: none`, no MCP/HTTP. `smoke_gate: yes`.
3. If every smoke `pass` (or there is no smoke): run remaining `active` to the end. `fail` / `blocked` do not stop the suite. `smoke_gate: no`.

If MCP fails mid-suite: keep already recorded verdicts; current case `blocked`; continue with the same rules. If MCP stays down, later non-smoke cases are `blocked`, not `skipped`.

## source frontmatter

Count channels you actually requested (browser MCP, public HTTP, internal HTTP), including failed requests:

- no requests → `none`
- only browser → `browser`
- only public HTTP → `public`
- only internal HTTP → `internal`
- more than one of those → `mixed`

Classification and per-case `channel` are not the same as file `source`. Case `channel` is `browser` | `http` | `none`.

## Output

Write `memory/<product-id>/raw/_incoming/run.md` matching `fixtures/demo-run/incoming/run.md` shape.

Frontmatter: `slug`, `title`, `product`, `task_id`, `testdoc`, `fetched_at` (ISO-8601 with offset, now), `source`. No `status`.

Body:

1. `## Summary` with integer `pass`, `fail`, `blocked`, `skipped` and `smoke_gate: yes` or `no` (key: value lines).
2. `## Results` — one `### <id>` per `active` id, execution order (smoke then rest). Fields: `verdict`, `channel`, `observed`, and `reason` if verdict is not `pass`. `skipped` reason is exactly `smoke-gate`. `channel: none` only with `blocked` or `skipped`.
3. `## Gaps` (heading required; `- none` allowed).
4. Line: `Did not write to Upservice or Testmo.`

No screenshots. No secrets. Short `observed` (UI quote or HTTP status/body snippet).

Write `MANIFEST.md` listing `run.md` only.
```

- [ ] **Step 2: Commit**

```powershell
git add .cursor/agents/verifier.md
git commit -m "Add verifier subagent for MCP suite runs."
```

---

### Task 5: Skill, координатор, README, пример конфига

**Files:**
- Create: `.cursor/skills/verify-testdocs/SKILL.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/examples/product-config.yaml`
- Test: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py -v`

**Interfaces:**
- Consumes: testdocs with `active`, verifier, librarian goal `run`
- Produces: user-facing skill and routing. Does not start `generate-testdocs`. Does not write tickets.

- [ ] **Step 1: Write the skill**

`.cursor/skills/verify-testdocs/SKILL.md`:

```markdown
---
name: verify-testdocs
description: Runs one testdoc suite against the live product via browser MCP or HTTP and stores the verdict in git. Use when the user says проверь сюит, прогони кейсы, or verify testdocs. Does not write to Upservice or Testmo.
---

# verify-testdocs

## Steps

1. Resolve the single product id (v1: `upservice` if that is the only folder). If `raw/_incoming/` is not empty, stop.
2. Find `memory/<id>/testdocs/<slug>.md` (ticket id → `task-<id>`). If missing or there is no `status: active` case, stop. Tell the user to run `generate-testdocs` first. Do not start scribe, hunter, or invent cases from chat.
3. Launch `verifier` with the testdoc path. Verifier writes `_incoming/run.md` with ids and verdicts. No Figma, no Upservice write, no Testmo, no canonical `runs/`.
4. After MANIFEST lists `run.md`, launch `librarian` with goal `run`. Librarian inserts `status: ready`, overwrites `runs/<slug>.md`, updates `runs/index.md`. If incoming ids ≠ testdoc `active` set, librarian writes nothing.
5. Report the run path, pass/fail/blocked/skipped counts, and whether `smoke_gate` tripped. Say the run is ready only if the file exists and `py -3 tools/memory_schema.py memory/<id>` would pass.
6. Never write to Upservice or Testmo. Do not start generate-testdocs or analyze-requirement from this skill.
```

- [ ] **Step 2: Update coordinator.mdc**

Keep it under 50 lines. Replace the skills/subagents line and add a verify paragraph after generate-testdocs:

```markdown
Skills: `index-system`, `recall`, `refresh`, `analyze-requirement`, `generate-testdocs`, `verify-testdocs`. Subagents: `hunter`, `librarian`, `analyst`, `scribe`, `verifier`.

For analyze-requirement: hunter may fetch one task snapshot into `tasks/task-<id>.md` via librarian; analyst drafts requirements; librarian writes `requirements/`. Do not write to the product.

For generate-testdocs: only if `requirements/<slug>.md` is `ready`; scribe drafts `_incoming/testdocs.md`; librarian writes `testdocs/` via the merge helper. Do not start analyze-requirement from this skill. Do not write to the product or Testmo.

For verify-testdocs: only if `testdocs/<slug>.md` has an `active` case; verifier drafts `_incoming/run.md`; librarian overwrites `runs/<slug>.md`. Do not start generate-testdocs from this skill. Do not write to the product or Testmo.
```

- [ ] **Step 3: Update AGENTS.md**

Add under Roles:

```markdown
- `verifier` executes one testdoc suite via browser MCP or HTTP. Draft only in `_incoming/run.md`.
```

Add spec path:

```markdown
`docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`
```

Keep "Do not do in v1" as writing tickets, Playwright/e2e, full API dumps, scheduled reindex, RAG, guessing product URLs. Do not list MCP verification as forbidden.

- [ ] **Step 4: Update README.md**

In What this is:

```markdown
Coordinator (this repo's chat) + `hunter` + `analyst` + `scribe` + `verifier` + `librarian`. Live MCP checks write git runs. Not Playwright. Not a ticket bot.
```

Add command:

```markdown
- «Проверь сюит 1842» → skill `verify-testdocs`
```

In Checks, keep existing pytest files (now including run tests inside `test_memory_schema.py`).

Add acceptance bullets:

```markdown
10. Verify from testdocs: `runs/task-<id>.md` has one result per `active` case, schema `OK`; Upservice and Testmo are not called.
11. Verify without testdocs: stop; `_incoming` stays empty; no runs file is created.
12. Smoke gate and repeat: non-pass smoke skips the rest with `skipped` / `smoke-gate`; a second run overwrites the same `runs/<slug>.md`.
```

Add spec line:

```markdown
MCP verification spec: `docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md`
```

- [ ] **Step 5: Update example product config**

In `docs/examples/product-config.yaml`, after `mcp.browser`, add:

```yaml
# ui.base_url: https://app.example.com
```

Do not enable `mcp.browser: true` in `products/upservice/config.yaml` in this task.

- [ ] **Step 6: Run automated checks**

```powershell
py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py -v
py -3 -m ruff check tools tests
py -3 tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: PASS / `OK`.

- [ ] **Step 7: Commit**

```powershell
git add .cursor/skills/verify-testdocs/SKILL.md .cursor/rules/coordinator.mdc AGENTS.md README.md docs/examples/product-config.yaml
git commit -m "Add verify-testdocs skill and coordinator routing."
```

---

## Self-review (spec coverage)

| Spec | Task |
|------|------|
| §5 поток, Verifier + Librarian, замок incoming | 3, 4, 5 |
| §6 paths, slug, optional `runs/` | 2, 3 |
| §7.1 `tier: smoke`, merge preserve | 1 |
| §7.2 контракт прогона, source enum, verdicts, Summary | 2, 4 |
| §7.3 incoming без `status`, id = active | 2, 3, 4 |
| §8 роли, классификация, smoke order, MCP crash | 3, 4, 5 |
| §9 стоп без testdocs, не запускать generate-testdocs | 4, 5 |
| §10 ошибки blocked vs fail vs skipped | 2, 4 |
| §11 фикстура demo-run, три сценария | 2, 5 |
| §12 `ui.base_url`, `mcp.browser` | 4, 5 |
| §13 verifier.md, skill, librarian, schema, example config | 1–5 |
| §3/§14 out of scope (Playwright, tickets, screenshots, history) | Global Constraints, 4, 5 |

Placeholder scan: no TBD. Types: `TestdocCase.tier`, `RunResult`, `validate_run_card(path, testdoc_path=None)` used consistently. Librarian goal `run` matches skill step 4.
