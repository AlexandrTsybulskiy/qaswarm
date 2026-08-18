# Testmo CSV Export Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a testdoc merge, write `testdocs/<slug>.csv` for manual Testmo import, keep markdown as canon, and fail the memory schema if the CSV is missing or out of sync.

**Architecture:** `tools/testdoc_csv.py` reads a canonical suite `.md` and renders CSV from `active` cases in checklist order. Librarian calls it after `testdoc_merge.py`. `memory_schema.py` checks sibling CSV files by parsed fields. Agents still do not call Testmo.

**Tech Stack:** Python 3.11+ stdlib (`csv`, `argparse`), pytest, ruff. Host CLI: `py -3`.

## Global Constraints

- Agents do not write to Upservice or Testmo (CSV in git is not a TMS write).
- Canonical suite remains `testdocs/<slug>.md`; CSV is a derived sibling, not a card.
- Columns are exactly `Name,Folder,Steps,Expected,Id`.
- `Name` = case `title`, `Folder` = suite frontmatter `title`, `Steps` = `action`, `Expected` = `expected`, `Id` = case id.
- Only `status: active` rows, checklist order; never export `orphan`.
- UTF-8 without BOM, comma delimiter, `csv.QUOTE_MINIMAL`, lineterminator `\n`.
- Empty/`draft` suite: header-only CSV.
- Empty case `title` copies through as empty `Name`; do not invent a title.
- Scribe does not write CSV or assign `tc-…` ids.
- Librarian invokes the helper; it does not hand-build CSV rows.
- Coordinator does not write `memory/`.
- Incoming lock unchanged: if CSV write fails, do not delete `_incoming/`.
- `testdocs/index.md` is not a suite; `index.csv` is always an error.
- No Testmo API, no folder hierarchy `product > slug`, no multi-row steps.
- Host CLI: `py -3`, not `python`.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/testdoc_csv.py` | Parse suite, render/write CSV, CLI |
| `tests/test_testdoc_csv.py` | Helper, quoting, orphan skip, CLI |
| `fixtures/demo-testdoc/expected/testdocs/task-1.csv` | Expected CSV for demo suite |
| `tools/memory_schema.py` | Sibling CSV + stray CSV checks |
| `tests/test_memory_schema.py` | Missing/mismatch/stray CSV |
| `.cursor/agents/librarian.md` | Call `testdoc_csv.py` after merge |
| `.cursor/skills/generate-testdocs/SKILL.md` | Report CSV path |
| `.cursor/rules/coordinator.mdc` | Testdocs writes include CSV |
| `.cursor/rules/memory-card.mdc` | CSV sibling note |
| `AGENTS.md`, `README.md` | Spec link and checks |
| `memory/upservice/testdocs/task-5210629.csv` | Backfill existing suite |

---

### Task 1: CSV helper

**Files:**
- Create: `tools/testdoc_csv.py`
- Create: `tests/test_testdoc_csv.py`
- Create: `fixtures/demo-testdoc/expected/testdocs/task-1.csv`
- Test: `tests/test_testdoc_csv.py`

**Interfaces:**
- Consumes: `memory_schema.parse_frontmatter`, `testdoc_merge.parse_canonical_cases`, `testdoc_merge.TestdocCase`
- Produces:
  - `CSV_COLUMNS: tuple[str, ...] = ("Name", "Folder", "Steps", "Expected", "Id")`
  - `checklist_ids(body: str) -> list[str]`
  - `csv_rows(folder: str, cases: list[TestdocCase], checklist: list[str]) -> list[dict[str, str]]`
  - `render_csv(rows: list[dict[str, str]]) -> str`
  - `export_suite(suite_path: Path) -> str`
  - `write_csv(path: Path, content: str) -> None`
  - `main(argv: list[str] | None = None) -> int` with `--suite` and `--output`

- [ ] **Step 1: Write the failing tests and expected fixture**

Create `fixtures/demo-testdoc/expected/testdocs/task-1.csv` (UTF-8, `\n`, no BOM):

```csv
Name,Folder,Steps,Expected,Id
Sprint dates visible,Show sprint dates,Open a sprint card,start and end dates are visible,tc-1-1
Save persists dates,Show sprint dates,Click save,dates persist,tc-1-3
Missing dates placeholder,Show sprint dates,Open a sprint without dates,placeholder shown,tc-1-4
```

Create `tests/test_testdoc_csv.py`:

```python
from pathlib import Path

import testdoc_csv
from testdoc_merge import TestdocCase

ROOT = Path(__file__).resolve().parents[1]
TD_EXPECTED = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "task-1.md"
TD_CSV = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "task-1.csv"


def test_csv_rows_skip_orphan_and_follow_checklist() -> None:
    cases = [
        TestdocCase("A", "Open", "visible", "active", "tc-1-1"),
        TestdocCase("B", "Save", "ok", "active", "tc-1-3"),
        TestdocCase("Hidden", "Open", "hidden", "orphan", "tc-1-2"),
    ]
    rows = testdoc_csv.csv_rows("Show sprint dates", cases, ["tc-1-1", "tc-1-3"])
    assert [row["Id"] for row in rows] == ["tc-1-1", "tc-1-3"]
    assert rows[0] == {
        "Name": "A",
        "Folder": "Show sprint dates",
        "Steps": "Open",
        "Expected": "visible",
        "Id": "tc-1-1",
    }


def test_render_csv_header_only_when_no_rows() -> None:
    text = testdoc_csv.render_csv([])
    assert text == "Name,Folder,Steps,Expected,Id\n"


def test_render_csv_quotes_comma_and_quote() -> None:
    rows = [
        {
            "Name": "N",
            "Folder": "F",
            "Steps": "do",
            "Expected": 'hello, "world"',
            "Id": "tc-1-1",
        }
    ]
    text = testdoc_csv.render_csv(rows)
    import csv
    import io

    parsed = list(csv.DictReader(io.StringIO(text)))
    assert parsed[0]["Expected"] == 'hello, "world"'


def test_export_suite_matches_fixture() -> None:
    text = testdoc_csv.export_suite(TD_EXPECTED)
    assert "tc-1-2" not in text
    assert text == TD_CSV.read_text(encoding="utf-8")


def test_empty_title_copies_through() -> None:
    rows = testdoc_csv.csv_rows(
        "Folder",
        [TestdocCase("", "Open", "ok", "active", "tc-1-1")],
        ["tc-1-1"],
    )
    assert rows[0]["Name"] == ""


def test_cli_writes_output(tmp_path: Path) -> None:
    output = tmp_path / "out" / "task-1.csv"
    code = testdoc_csv.main(
        ["--suite", str(TD_EXPECTED), "--output", str(output)]
    )
    assert code == 0
    assert output.read_text(encoding="utf-8") == TD_CSV.read_text(encoding="utf-8")


def test_cli_missing_suite_does_not_write(tmp_path: Path) -> None:
    output = tmp_path / "out.csv"
    code = testdoc_csv.main(
        ["--suite", str(tmp_path / "missing.md"), "--output", str(output)]
    )
    assert code == 1
    assert not output.exists()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_testdoc_csv.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'testdoc_csv'` (or import error).

- [ ] **Step 3: Write `tools/testdoc_csv.py`**

```python
from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import testdoc_merge
from memory_schema import parse_frontmatter
from testdoc_merge import TestdocCase

CSV_COLUMNS: tuple[str, ...] = ("Name", "Folder", "Steps", "Expected", "Id")


def checklist_ids(body: str) -> list[str]:
    chunk = body.split("## Checklist", 1)
    check_body = chunk[1].split("##", 1)[0] if len(chunk) == 2 else ""
    ids: list[str] = []
    for line in check_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            ids.append(stripped[2:].strip())
    return ids


def csv_rows(
    folder: str,
    cases: list[TestdocCase],
    checklist: list[str],
) -> list[dict[str, str]]:
    active = {
        case.case_id: case
        for case in cases
        if case.status == "active" and case.case_id
    }
    rows: list[dict[str, str]] = []
    for case_id in checklist:
        case = active.get(case_id)
        if case is None:
            continue
        rows.append(
            {
                "Name": case.title,
                "Folder": folder,
                "Steps": case.action,
                "Expected": case.expected,
                "Id": case.case_id or "",
            }
        )
    return rows


def render_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(CSV_COLUMNS),
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_COLUMNS})
    return buffer.getvalue()


def export_suite(suite_path: Path) -> str:
    text = suite_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    title = meta.get("title", "")
    if not meta:
        raise ValueError(f"{suite_path}: not a testdoc suite")
    cases = testdoc_merge.parse_canonical_cases(body)
    return render_csv(csv_rows(title, cases, checklist_ids(body)))


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export testdoc suite to Testmo CSV")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.suite.is_file():
            raise FileNotFoundError(args.suite)
        text = export_suite(args.suite)
        write_csv(args.output, text)
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(f"{args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_testdoc_csv.py -v`

Expected: PASS (7 tests).

Run: `py -3 -m ruff check tools/testdoc_csv.py tests/test_testdoc_csv.py`

Expected: no issues. If ruff wants import order (`I`), apply its order; keep `CSV_COLUMNS` public.

- [ ] **Step 5: Commit**

```powershell
git add tools/testdoc_csv.py tests/test_testdoc_csv.py fixtures/demo-testdoc/expected/testdocs/task-1.csv docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md docs/superpowers/plans/2026-08-17-qa-swarm-testmo-csv-export.md
git commit -m "Add testdoc CSV helper for Testmo import."
```

---

### Task 2: Schema checks for sibling CSV

**Files:**
- Modify: `tools/memory_schema.py` (`validate_testdoc_csv`, `parse_testdoc_csv`, walk in `validate_memory_tree`)
- Modify: `tests/test_memory_schema.py` (append CSV tests after testdoc tests)
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `testdoc_csv.CSV_COLUMNS`, `testdoc_csv.export_suite` is not required; use `testdoc_csv.csv_rows`, `testdoc_csv.checklist_ids`, `testdoc_merge.parse_canonical_cases`, `parse_frontmatter`
- Produces:
  - `parse_testdoc_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]`
  - `validate_testdoc_csv(suite_path: Path) -> list[str]`
  - `validate_memory_tree` also flags stray `*.csv`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_memory_schema.py` (keep existing testdoc tests; `validate_testdoc_suite` stays markdown-only):

```python
def test_testdoc_csv_valid_for_fixture() -> None:
    assert memory_schema.validate_testdoc_csv(TD_EXPECTED) == []


def test_testdoc_csv_missing_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(TD_EXPECTED.read_text(encoding="utf-8"), encoding="utf-8")
    errors = memory_schema.validate_testdoc_csv(card)
    assert any("missing testdoc CSV" in error for error in errors)


def test_testdoc_csv_wrong_id_fails(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(TD_EXPECTED.read_text(encoding="utf-8"), encoding="utf-8")
    csv_path = tmp_path / "task-1.csv"
    csv_path.write_text(
        TD_CSV.read_text(encoding="utf-8").replace("tc-1-1", "tc-1-99", 1),
        encoding="utf-8",
        newline="\n",
    )
    errors = memory_schema.validate_testdoc_csv(card)
    assert any("Id" in error or "mismatch" in error.lower() for error in errors)


def test_memory_tree_stray_csv_fails(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    testdocs.mkdir()
    (testdocs / "index.md").write_text("# Testdocs\n", encoding="utf-8")
    (testdocs / "index.csv").write_text(
        "Name,Folder,Steps,Expected,Id\n", encoding="utf-8"
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("index.csv" in error for error in errors)


def test_memory_tree_suite_without_csv_fails(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    testdocs.mkdir()
    (testdocs / "task-1.md").write_text(
        TD_EXPECTED.read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("task-1.csv" in error and "missing testdoc CSV" in error for error in errors)
```

Add next to `TD_EXPECTED`:

```python
TD_CSV = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "task-1.csv"
```

`test_testdoc_csv_valid_for_fixture` needs the sibling `task-1.csv` beside `task-1.md` in the fixture dir (created in Task 1). `validate_testdoc_csv` looks at `suite_path.with_suffix(".csv")`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_memory_schema.py::test_testdoc_csv_valid_for_fixture tests/test_memory_schema.py::test_testdoc_csv_missing_fails tests/test_memory_schema.py::test_testdoc_csv_wrong_id_fails tests/test_memory_schema.py::test_memory_tree_stray_csv_fails tests/test_memory_schema.py::test_memory_tree_suite_without_csv_fails -v`

Expected: FAIL with `AttributeError: module 'memory_schema' has no attribute 'validate_testdoc_csv'` (or similar).

- [ ] **Step 3: Implement schema helpers and tree walk**

Add after `validate_testdoc_suite` in `tools/memory_schema.py`:

```python
def parse_testdoc_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    import csv

    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        rows = [{key: (row.get(key) or "") for key in header} for row in reader]
    return header, rows


def validate_testdoc_csv(suite_path: Path) -> list[str]:
    import testdoc_csv
    import testdoc_merge

    errors: list[str] = []
    if suite_path.name == "index.md":
        return errors
    csv_path = suite_path.with_suffix(".csv")
    if not csv_path.is_file():
        errors.append(f"{csv_path}: missing testdoc CSV")
        return errors
    header, rows = parse_testdoc_csv(csv_path)
    if header != list(testdoc_csv.CSV_COLUMNS):
        errors.append(f"{csv_path}: header must be Name,Folder,Steps,Expected,Id")
        return errors
    meta, body = parse_frontmatter(suite_path.read_text(encoding="utf-8"))
    want = testdoc_csv.csv_rows(
        meta.get("title", ""),
        testdoc_merge.parse_canonical_cases(body),
        testdoc_csv.checklist_ids(body),
    )
    got_ids = [row.get("Id", "") for row in rows]
    want_ids = [row["Id"] for row in want]
    if got_ids != want_ids:
        errors.append(f"{csv_path}: Id mismatch {got_ids!r} != {want_ids!r}")
    for index, expected_row in enumerate(want):
        if index >= len(rows):
            break
        for key in testdoc_csv.CSV_COLUMNS:
            if rows[index].get(key, "") != expected_row.get(key, ""):
                errors.append(f"{csv_path}: {key} mismatch for {expected_row['Id']}")
    if len(rows) != len(want):
        errors.append(
            f"{csv_path}: row count {len(rows)} != active {len(want)}"
        )
    return errors
```

In `validate_memory_tree`, replace the testdocs loop with:

```python
    testdocs_dir = root / "testdocs"
    if testdocs_dir.is_dir():
        suite_stems: set[str] = set()
        for card in testdocs_dir.glob("*.md"):
            if card.name == "index.md":
                continue
            suite_stems.add(card.stem)
            errors.extend(validate_testdoc_suite(card))
            errors.extend(validate_testdoc_csv(card))
        for csv_file in testdocs_dir.glob("*.csv"):
            if csv_file.stem == "index" or csv_file.stem not in suite_stems:
                errors.append(f"{csv_file}: csv without testdoc suite")
```

Do not treat `*.csv` as cards. Do not change `validate_testdoc_suite`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_csv.py tests/test_testdoc_merge.py -v`

Expected: PASS. Do **not** run `memory_schema.py memory/upservice` yet (existing suite has no CSV until Task 4).

Run: `py -3 -m ruff check tools/memory_schema.py tests/test_memory_schema.py`

Expected: no issues.

- [ ] **Step 5: Commit**

```powershell
git add tools/memory_schema.py tests/test_memory_schema.py
git commit -m "Validate testdoc CSV siblings in memory schema."
```

---

### Task 3: Librarian and generate-testdocs routing

**Files:**
- Modify: `.cursor/agents/librarian.md` (testdoc incoming section)
- Modify: `.cursor/skills/generate-testdocs/SKILL.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `.cursor/rules/memory-card.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Test: no new pytest; ruff unchanged. Verify by reading the inserted command blocks.

**Interfaces:**
- Consumes: CLI from Task 1 (`testdoc_csv.py --suite --output`)
- Produces: Librarian writes CSV after merge; coordinator reports CSV path; schema still required before calling testdocs ready

- [ ] **Step 1: Update librarian testdoc incoming**

In `.cursor/agents/librarian.md`, after the `testdoc_merge.py` command and the `testdocs/index.md` table, before `Do not invent cases`, insert this block (command on its own line):

Then export CSV (do not build rows by hand):

`py -3 tools/testdoc_csv.py --suite memory/<product-id>/testdocs/<slug>.md --output memory/<product-id>/testdocs/<slug>.csv`

If the CSV command fails, write nothing further, do not delete `_incoming/`, and report failure.

Keep: Do not call Figma, Upservice, or Testmo. Match `fixtures/demo-testdoc/expected/` for shape (ids, sections, and `task-1.csv`).

Leave the existing merge command unchanged. CSV comes after index update, before schema (schema is already "after any successful write").

- [ ] **Step 2: Update generate-testdocs skill**

Replace steps 4–5 in `.cursor/skills/generate-testdocs/SKILL.md` with:

```markdown
4. After MANIFEST lists `testdocs.md`, launch `librarian` with goal `testdoc`. Librarian runs `tools/testdoc_merge.py` (writes `testdocs/<slug>.md`) then `tools/testdoc_csv.py` (writes `testdocs/<slug>.csv`).
5. Report the suite path, CSV path, active count, orphan count, and gaps. Say testdocs are ready only if both files exist and `py -3 tools/memory_schema.py memory/<id>` would pass.
```

Keep step 6: never write to Upservice or Testmo.

- [ ] **Step 3: Update coordinator, memory-card, AGENTS, README**

In `.cursor/rules/coordinator.mdc` replace the generate-testdocs sentence with:

```
For generate-testdocs: only if `requirements/<slug>.md` is `ready`; scribe drafts `_incoming/testdocs.md`; librarian writes `testdocs/` via the merge helper and `testdoc_csv.py`. Do not start analyze-requirement from this skill. Do not write to the product or Testmo.
```

In `.cursor/rules/memory-card.mdc` replace the testdocs paragraph with:

```
Testdoc suites live in `memory/<product-id>/testdocs/<slug>.md` with testdoc fields from the spec. Only librarian writes them (via `tools/testdoc_merge.py`). After merge, librarian also writes sibling `testdocs/<slug>.csv` via `tools/testdoc_csv.py`. `testdocs/index.md` is not a card. `*.csv` is not a card.
```

In `AGENTS.md` add after the MCP verification spec line:

```
`docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md`
```

In `README.md` Checks block, add `tests/test_testdoc_csv.py` to pytest:

```powershell
python -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py -v
```

Add after the test documentation spec line:

```
Testmo CSV export spec: `docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md`
```

Change acceptance item 7 to:

```
7. Testdocs from ready requirements: `testdocs/task-<id>.md` has one active case per Testable arrow, a checklist of those ids, sibling `testdocs/task-<id>.csv` with those active rows, schema `OK`; Upservice and Testmo are not called.
```

- [ ] **Step 4: Confirm pytest still passes**

Run: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/skills/generate-testdocs/SKILL.md .cursor/rules/coordinator.mdc .cursor/rules/memory-card.mdc AGENTS.md README.md
git commit -m "Wire testdoc CSV export into librarian and generate-testdocs."
```

---

### Task 4: Backfill existing Upservice suite

**Files:**
- Create: `memory/upservice/testdocs/task-5210629.csv` (generated, not hand-edited)
- Test: `py -3 tools/memory_schema.py memory/upservice`

**Interfaces:**
- Consumes: `testdoc_csv.main` from Task 1, suite `memory/upservice/testdocs/task-5210629.md`
- Produces: sibling CSV with 21 active rows; Folder = `[Story] - Настройка нижнего меню в мобильном приложении`

- [ ] **Step 1: Generate the CSV**

Run:

```powershell
py -3 tools/testdoc_csv.py --suite memory/upservice/testdocs/task-5210629.md --output memory/upservice/testdocs/task-5210629.csv
```

Expected stdout: `memory\upservice\testdocs\task-5210629.csv` (or POSIX path). Exit 0.

Do not hand-write rows. Do not call Testmo.

- [ ] **Step 2: Spot-check**

- File starts with `Name,Folder,Steps,Expected,Id`
- First data `Id` is `tc-5210629-1`
- File does not contain `orphan`
- Row count = 21 data rows (22 lines including header)

- [ ] **Step 3: Validate live memory**

Run: `py -3 tools/memory_schema.py memory/upservice`

Expected: `OK`

- [ ] **Step 4: Run the full test set from the spec**

Run: `py -3 -m pytest tests/test_testdoc_csv.py tests/test_memory_schema.py tests/test_testdoc_merge.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add memory/upservice/testdocs/task-5210629.csv
git commit -m "Export existing testdoc suite 5210629 to Testmo CSV."
```

---

## Spec coverage

| Spec section | Task |
|--------------|------|
| Columns, UTF-8, active-only, header-only draft | 1 |
| CLI `--suite` / `--output`, no partial file | 1 |
| Schema sibling / stray / mismatch | 2 |
| Librarian after merge, incoming stays on CSV failure | 3 |
| generate-testdocs report includes CSV | 3 |
| Scenario 1 generate-testdocs | 3 (wiring) + 1 (helper) |
| Scenario 2 repeat overwrite | 1 (`export_suite` rebuilds from current md; merge already replaces md) |
| Scenario 3 backfill | 4 |
| `memory/upservice` schema OK | 4 |
| Out of scope (API, hierarchy, Scribe CSV) | Global constraints; no tasks |

## Placeholder / type check

Names used everywhere: `CSV_COLUMNS`, `checklist_ids`, `csv_rows`, `render_csv`, `export_suite`, `write_csv`, `parse_testdoc_csv`, `validate_testdoc_csv`. No TBD. Host CLI is `py -3`.
