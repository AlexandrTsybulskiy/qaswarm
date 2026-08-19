# Testdocs md/csv folders Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store canonical testdoc suites in `testdocs/md/` and Testmo CSV exports in `testdocs/csv/`, fail the schema on leftover sibling files, and migrate existing Upservice suites in the same change.

**Architecture:** Path helpers in `tools/memory_schema.py` are the single layout contract. `validate_testdoc_csv` and `validate_memory_tree` pair `md/<slug>.md` with `csv/<slug>.csv`. Librarian still calls `testdoc_merge.py` then `testdoc_csv.py`; only the path arguments change. `testdoc_csv.py` flags stay `--suite` / `--output`.

**Tech Stack:** Python 3.11+ stdlib, pytest, ruff. Host CLI: `py -3`.

## Global Constraints

- Canonical suite is `testdocs/md/<slug>.md`; CSV is `testdocs/csv/<slug>.csv`, not a card.
- Index stays `testdocs/index.md`; Card column is `[<slug>.md](md/<slug>.md)`.
- Hard cut: any `testdocs/<slug>.md` except `index.md`, or any `testdocs/<slug>.csv` in the testdocs root, is `legacy testdoc path`.
- No fallback to sibling `.csv` next to the suite file.
- CSV columns, active-only rows, merge ids, and the Upservice/Testmo write ban do not change.
- `testdocs/` may be absent. Empty `md/` and `csv/` may be absent until the first suite.
- `fixtures/demo-run/testdocs/task-1.md` stays a lone file for run unit tests; product memory and `validate_memory_tree` use `testdocs/md/`.
- Coordinator does not write `memory/` during generate-testdocs; the engineer migrates existing files in Task 4.
- Host CLI: `py -3`, not `python`.
- Do not edit historical plans under `docs/superpowers/plans/2026-08-14-*` or `2026-08-17-*`.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/memory_schema.py` | Path helpers; CSV lookup; testdocs walk; run→testdoc lookup; legacy errors |
| `tests/test_memory_schema.py` | Helpers, layout, legacy, missing CSV, run missing testdoc |
| `tests/test_testdoc_csv.py` | Fixture path constants after move |
| `fixtures/demo-testdoc/expected/testdocs/md/task-1.md` | Expected suite |
| `fixtures/demo-testdoc/expected/testdocs/csv/task-1.csv` | Expected CSV |
| `fixtures/demo-testdoc/expected/testdocs/index.md` | Card link `md/task-1.md` |
| `fixtures/demo-testdoc/existing/testdocs/md/task-1.md` | Merge existing suite |
| `.cursor/agents/librarian.md` | Merge/CSV/run paths under `md/` and `csv/` |
| `.cursor/agents/verifier.md` | Testdoc path `testdocs/md/<slug>.md` |
| `.cursor/skills/generate-testdocs/SKILL.md` | Report new paths |
| `.cursor/skills/verify-testdocs/SKILL.md` | Find suite in `md/` |
| `.cursor/rules/coordinator.mdc` | Verify gate path |
| `.cursor/rules/memory-card.mdc` | Canonical testdoc paths |
| `AGENTS.md`, `README.md` | Spec link and check 7 |
| Parent design specs | Path sections only |
| `memory/upservice/testdocs/` | Move existing suites |

---

### Task 1: Path helpers

**Files:**
- Modify: `tools/memory_schema.py` (after `TD_CASE_STATUSES`, before testdoc validation helpers)
- Modify: `tests/test_memory_schema.py`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: `pathlib.Path`
- Produces:
  - `TESTDOCS_MD_DIR: str = "md"`
  - `TESTDOCS_CSV_DIR: str = "csv"`
  - `testdoc_suite_path(root: Path, slug: str) -> Path`
  - `testdoc_csv_path(root: Path, slug: str) -> Path`
  - `testdoc_csv_for_suite(suite_path: Path) -> Path`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_memory_schema.py` (near the testdoc section, after `TD_CSV`):

```python
def test_testdoc_path_helpers() -> None:
    root = Path("/tmp/memory/upservice")
    assert memory_schema.testdoc_suite_path(root, "task-1") == (
        root / "testdocs" / "md" / "task-1.md"
    )
    assert memory_schema.testdoc_csv_path(root, "task-1") == (
        root / "testdocs" / "csv" / "task-1.csv"
    )
    suite = root / "testdocs" / "md" / "task-1.md"
    assert memory_schema.testdoc_csv_for_suite(suite) == (
        root / "testdocs" / "csv" / "task-1.csv"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `py -3 -m pytest tests/test_memory_schema.py::test_testdoc_path_helpers -v`

Expected: FAIL with `AttributeError: testdoc_suite_path`

- [ ] **Step 3: Write minimal implementation**

In `tools/memory_schema.py`, immediately after `TD_CASE_STATUSES = {"active", "orphan"}`:

```python
TESTDOCS_MD_DIR = "md"
TESTDOCS_CSV_DIR = "csv"


def testdoc_suite_path(root: Path, slug: str) -> Path:
    return root / "testdocs" / TESTDOCS_MD_DIR / f"{slug}.md"


def testdoc_csv_path(root: Path, slug: str) -> Path:
    return root / "testdocs" / TESTDOCS_CSV_DIR / f"{slug}.csv"


def testdoc_csv_for_suite(suite_path: Path) -> Path:
    return suite_path.parent.parent / TESTDOCS_CSV_DIR / f"{suite_path.stem}.csv"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `py -3 -m pytest tests/test_memory_schema.py::test_testdoc_path_helpers -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add tools/memory_schema.py tests/test_memory_schema.py
git commit -m "Add testdoc md and csv path helpers."
```

---

### Task 2: Schema layout, fixtures, and tests

**Files:**
- Modify: `tools/memory_schema.py` (`validate_testdoc_csv`, testdocs walk in `validate_memory_tree`, run testdoc lookup)
- Modify: `tests/test_memory_schema.py`
- Modify: `tests/test_testdoc_csv.py` (path constants only)
- Move: `fixtures/demo-testdoc/expected/testdocs/task-1.md` → `md/task-1.md`
- Move: `fixtures/demo-testdoc/expected/testdocs/task-1.csv` → `csv/task-1.csv`
- Move: `fixtures/demo-testdoc/existing/testdocs/task-1.md` → `md/task-1.md`
- Modify: `fixtures/demo-testdoc/expected/testdocs/index.md`
- Test: `tests/test_memory_schema.py`, `tests/test_testdoc_csv.py`, `tests/test_testdoc_merge.py`

**Interfaces:**
- Consumes: `testdoc_suite_path`, `testdoc_csv_path`, `testdoc_csv_for_suite` from Task 1
- Produces: schema that only accepts `testdocs/md/*.md` + `testdocs/csv/<stem>.csv`; legacy root files error with `legacy testdoc path`; runs look up `testdocs/md/<slug>.md`

- [ ] **Step 1: Move fixtures and update path constants (tests will fail until schema matches)**

From repo root:

```powershell
New-Item -ItemType Directory -Force fixtures/demo-testdoc/expected/testdocs/md, fixtures/demo-testdoc/expected/testdocs/csv, fixtures/demo-testdoc/existing/testdocs/md | Out-Null
git mv fixtures/demo-testdoc/expected/testdocs/task-1.md fixtures/demo-testdoc/expected/testdocs/md/task-1.md
git mv fixtures/demo-testdoc/expected/testdocs/task-1.csv fixtures/demo-testdoc/expected/testdocs/csv/task-1.csv
git mv fixtures/demo-testdoc/existing/testdocs/task-1.md fixtures/demo-testdoc/existing/testdocs/md/task-1.md
```

Replace `fixtures/demo-testdoc/expected/testdocs/index.md` with:

```markdown
# Testdocs

| Slug | Task | Status | Active | Card |
|------|------|--------|--------|------|
| task-1 | 1 | ready | 3 | [task-1.md](md/task-1.md) |
```

In `tests/test_memory_schema.py` change constants:

```python
TD_EXISTING = ROOT / "fixtures" / "demo-testdoc" / "existing" / "testdocs" / "md" / "task-1.md"
TD_EXPECTED = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "md" / "task-1.md"
TD_CSV = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "csv" / "task-1.csv"
```

In `tests/test_testdoc_csv.py`:

```python
TD_EXPECTED = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "md" / "task-1.md"
TD_CSV = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "csv" / "task-1.csv"
```

`TD_INDEX` stays `expected/testdocs/index.md`.

Add this helper in `tests/test_memory_schema.py` next to the testdoc constants:

```python
def _write_testdoc_tree(
    root: Path, md_text: str, csv_text: str | None
) -> Path:
    md_dir = root / "testdocs" / "md"
    csv_dir = root / "testdocs" / "csv"
    md_dir.mkdir(parents=True)
    csv_dir.mkdir(parents=True)
    card = md_dir / "task-1.md"
    card.write_text(md_text, encoding="utf-8")
    if csv_text is not None:
        (csv_dir / "task-1.csv").write_text(
            csv_text, encoding="utf-8", newline="\n"
        )
    return card
```

Replace `test_testdoc_csv_valid_for_fixture`, `test_testdoc_csv_missing_fails`, `test_testdoc_csv_wrong_id_fails`, `test_memory_tree_stray_csv_fails`, `test_memory_tree_suite_without_csv_fails`, `test_testdoc_csv_draft_requires_header_only`, and `test_memory_tree_run_requires_existing_testdoc` with:

```python
def test_testdoc_csv_valid_for_fixture() -> None:
    assert memory_schema.validate_testdoc_csv(TD_EXPECTED) == []


def test_testdoc_csv_missing_fails(tmp_path: Path) -> None:
    card = _write_testdoc_tree(
        tmp_path, TD_EXPECTED.read_text(encoding="utf-8"), None
    )
    errors = memory_schema.validate_testdoc_csv(card)
    assert any("missing testdoc CSV" in error for error in errors)
    assert any("csv" in error and "task-1.csv" in error for error in errors)


def test_testdoc_csv_wrong_id_fails(tmp_path: Path) -> None:
    card = _write_testdoc_tree(
        tmp_path,
        TD_EXPECTED.read_text(encoding="utf-8"),
        TD_CSV.read_text(encoding="utf-8").replace("tc-1-1", "tc-1-99", 1),
    )
    errors = memory_schema.validate_testdoc_csv(card)
    assert any("Id" in error or "mismatch" in error.lower() for error in errors)


def test_memory_tree_stray_csv_fails(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    csv_dir = testdocs / "csv"
    csv_dir.mkdir(parents=True)
    (testdocs / "index.md").write_text("# Testdocs\n", encoding="utf-8")
    (csv_dir / "index.csv").write_text(
        "Name,Folder,Steps,Expected,Id\n", encoding="utf-8"
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("index.csv" in error and "csv without testdoc suite" in error for error in errors)


def test_memory_tree_legacy_testdoc_md_fails(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    testdocs.mkdir()
    (testdocs / "task-1.md").write_text(
        TD_EXPECTED.read_text(encoding="utf-8"), encoding="utf-8"
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("legacy testdoc path" in error and "task-1.md" in error for error in errors)


def test_memory_tree_legacy_testdoc_csv_fails(tmp_path: Path) -> None:
    testdocs = tmp_path / "testdocs"
    testdocs.mkdir()
    (testdocs / "index.md").write_text("# Testdocs\n", encoding="utf-8")
    (testdocs / "task-1.csv").write_text(
        "Name,Folder,Steps,Expected,Id\n", encoding="utf-8"
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("legacy testdoc path" in error and "task-1.csv" in error for error in errors)


def test_memory_tree_suite_without_csv_fails(tmp_path: Path) -> None:
    _write_testdoc_tree(tmp_path, TD_EXPECTED.read_text(encoding="utf-8"), None)
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("missing testdoc CSV" in error for error in errors)


def test_memory_tree_testdocs_md_csv_ok(tmp_path: Path) -> None:
    _write_testdoc_tree(
        tmp_path,
        TD_EXPECTED.read_text(encoding="utf-8"),
        TD_CSV.read_text(encoding="utf-8"),
    )
    (tmp_path / "testdocs" / "index.md").write_text("# Testdocs\n", encoding="utf-8")
    assert memory_schema.validate_memory_tree(tmp_path) == []


def test_testdoc_csv_draft_requires_header_only(tmp_path: Path) -> None:
    text = TD_EXPECTED.read_text(encoding="utf-8").replace(
        "status: ready", "status: draft", 1
    )
    card = _write_testdoc_tree(
        tmp_path, text, "Name,Folder,Steps,Expected,Id\n"
    )
    assert memory_schema.validate_testdoc_csv(card) == []


def test_memory_tree_run_requires_existing_testdoc(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    (runs / "task-1.md").write_text(
        RUN_EXPECTED.read_text(encoding="utf-8"), encoding="utf-8"
    )

    errors = memory_schema.validate_memory_tree(tmp_path)

    assert any("missing testdoc testdocs/md/task-1.md" in error for error in errors)
```

Leave `test_testdoc_csv_skips_index` as-is (still skips by filename `index.md`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_csv.py tests/test_testdoc_merge.py -v`

Expected: FAIL. Typical failures: `validate_testdoc_csv` still looks for a sibling `.csv` next to `md/task-1.md`; `validate_memory_tree` still globs `testdocs/*.md`; run missing path is still `testdocs/task-1.md`. `test_testdoc_merge_fixture_matches_expected` should already PASS after the existing-file move.

- [ ] **Step 3: Implement schema**

In `validate_testdoc_csv`, replace `csv_path = suite_path.with_suffix(".csv")` with:

```python
    csv_path = testdoc_csv_for_suite(suite_path)
```

Keep the `if suite_path.name == "index.md": return errors` guard.

Replace the `testdocs_dir` block in `validate_memory_tree` with:

```python
    testdocs_dir = root / "testdocs"
    if testdocs_dir.is_dir():
        for leftover in list(testdocs_dir.glob("*.md")) + list(
            testdocs_dir.glob("*.csv")
        ):
            if leftover.name == "index.md":
                continue
            errors.append(f"{leftover}: legacy testdoc path")
        suite_stems: set[str] = set()
        md_dir = testdocs_dir / TESTDOCS_MD_DIR
        if md_dir.is_dir():
            for card in md_dir.glob("*.md"):
                if card.name == "index.md":
                    continue
                suite_stems.add(card.stem)
                errors.extend(validate_testdoc_suite(card))
                errors.extend(validate_testdoc_csv(card))
        csv_dir = testdocs_dir / TESTDOCS_CSV_DIR
        if csv_dir.is_dir():
            for csv_file in csv_dir.glob("*.csv"):
                if csv_file.stem == "index" or csv_file.stem not in suite_stems:
                    errors.append(f"{csv_file}: csv without testdoc suite")
```

In the `runs_dir` block, replace the testdoc file lookup:

```python
            testdoc_name = meta.get("testdoc", card.stem)
            testdoc_file = testdoc_suite_path(root, testdoc_name)
            testdoc_path = testdoc_file if testdoc_file.is_file() else None
            if testdoc_path is None:
                relative_testdoc = testdoc_file.relative_to(root).as_posix()
                errors.append(f"{card}: missing testdoc {relative_testdoc}")
            errors.extend(validate_run_card(card, testdoc_path))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_csv.py tests/test_testdoc_merge.py -v`

Expected: PASS. `test_demo_catalog_tree_still_valid_without_testdocs` still PASS (no testdocs dir).

- [ ] **Step 5: Commit**

```powershell
git add tools/memory_schema.py tests/test_memory_schema.py tests/test_testdoc_csv.py fixtures/demo-testdoc
git commit -m "Validate testdocs in md and csv subfolders."
```

---

### Task 3: Skills, rules, and parent specs

**Files:**
- Modify: `.cursor/agents/librarian.md`
- Modify: `.cursor/agents/verifier.md`
- Modify: `.cursor/skills/generate-testdocs/SKILL.md`
- Modify: `.cursor/skills/verify-testdocs/SKILL.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `.cursor/rules/memory-card.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md` (paths only)
- Modify: `docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md` (paths only)
- Modify: `docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md` (paths only)

**Interfaces:**
- Consumes: layout from spec `2026-08-19-qa-swarm-testdocs-md-csv-folders-design.md`
- Produces: agents and skills that write/read `testdocs/md/` and `testdocs/csv/`

- [ ] **Step 1: Update librarian**

Canonical paths: add `testdocs/csv/<slug>.csv`; change suite line to `testdocs/md/<slug>.md`.

Testdoc incoming commands:

```
py -3 tools/testdoc_merge.py --incoming memory/<product-id>/raw/_incoming/testdocs.md --existing memory/<product-id>/testdocs/md/<slug>.md --output memory/<product-id>/testdocs/md/<slug>.md
```

Always pass `--existing memory/<product-id>/testdocs/md/<slug>.md`.

Index example Card cell: `[task-1.md](md/task-1.md)`.

CSV command:

`py -3 tools/testdoc_csv.py --suite memory/<product-id>/testdocs/md/<slug>.md --output memory/<product-id>/testdocs/csv/<slug>.csv`

Keep line: Match `fixtures/demo-testdoc/expected/` for shape (ids, sections, and `csv/task-1.csv`).

Run incoming: `Open testdocs/md/<slug>.md`.

- [ ] **Step 2: Update verifier and skills**

`.cursor/agents/verifier.md` task path:

`memory/<product-id>/testdocs/md/<slug>.md`

`.cursor/skills/generate-testdocs/SKILL.md` step 4:

Librarian runs `tools/testdoc_merge.py` (writes `testdocs/md/<slug>.md`) then `tools/testdoc_csv.py` (writes `testdocs/csv/<slug>.csv`).

`.cursor/skills/verify-testdocs/SKILL.md` step 2:

Find `memory/<id>/testdocs/md/<slug>.md`.

Coordinator verify line:

For verify-testdocs: only if `testdocs/md/<slug>.md` has an `active` case; verifier drafts `_incoming/run.md`; librarian overwrites `runs/<slug>.md`. Do not start generate-testdocs from this skill. Do not write to the product or Testmo.

`.cursor/rules/memory-card.mdc` testdoc paragraph:

Testdoc suites live in `memory/<product-id>/testdocs/md/<slug>.md` with testdoc fields from the spec. Only librarian writes them (via `tools/testdoc_merge.py`). After merge, librarian also writes `testdocs/csv/<slug>.csv` via `tools/testdoc_csv.py`. `testdocs/index.md` is not a card. `*.csv` is not a card.

- [ ] **Step 3: Update README, AGENTS.md, parent specs**

`README.md` check 7:

7. Testdocs from ready requirements: `testdocs/md/task-<id>.md` has one active case per Testable arrow, a checklist of those ids, `testdocs/csv/task-<id>.csv` with those active rows, schema `OK`; Upservice and Testmo are not called.

`AGENTS.md` Spec list: add

`docs/superpowers/specs/2026-08-19-qa-swarm-testdocs-md-csv-folders-design.md`

Parent spec path replacements (do not change case/CSV column contract):

`2026-08-14-qa-swarm-test-documentation-design.md`:

- `testdocs/<slug>.md + testdocs/index.md` → `testdocs/md/<slug>.md + testdocs/index.md`
- `memory/upservice/testdocs/<slug>.md` → `memory/upservice/testdocs/md/<slug>.md`
- `merge с testdocs/<slug>.md` → `merge с testdocs/md/<slug>.md`
- `testdocs/task-<id>.md` in scenario 1 → `testdocs/md/task-<id>.md`

`2026-08-17-qa-swarm-testmo-csv-export-design.md`:

- `testdocs/<slug>.md` / `testdocs/<slug>.csv` → `testdocs/md/<slug>.md` / `testdocs/csv/<slug>.csv` everywhere those paths mean the live layout
- table «Где файл» → `memory/<product-id>/testdocs/csv/<slug>.csv`
- architecture and librarian CLI `--suite` / `--output` to `md/` and `csv/`
- fixture sentence: `fixtures/demo-testdoc/expected/testdocs/md/task-1.md` and `.../csv/task-1.csv`
- «рядом появляется» → «появляется в `testdocs/csv/<slug>.csv`»
- add one sentence: root `testdocs/<slug>.md` / `.csv` is `legacy testdoc path` (see 2026-08-19 spec)

`2026-08-14-qa-swarm-mcp-verification-design.md`:

- `testdocs/<slug>.md` → `testdocs/md/<slug>.md` for the live suite path (sections 2, 5, 8, 9, scenario 1)

- [ ] **Step 4: Sanity-check docs still mention the new spec**

Grep agent/skill files for leftover live paths `testdocs/<slug>.md` that are not historical plan files:

```powershell
py -3 -c "from pathlib import Path; roots=[Path('.cursor'), Path('AGENTS.md'), Path('README.md')];
[print(p) for r in roots for p in ([r] if r.is_file() else r.rglob('*')) if p.is_file() and p.suffix in {'.md', '.mdc'} and 'testdocs/<slug>.md' in p.read_text(encoding='utf-8')]"
```

Expected: no hits in `.cursor/`, `AGENTS.md`, `README.md`. Parent specs should only use `testdocs/md/<slug>.md` for live paths.

- [ ] **Step 5: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/agents/verifier.md .cursor/skills/generate-testdocs/SKILL.md .cursor/skills/verify-testdocs/SKILL.md .cursor/rules/coordinator.mdc .cursor/rules/memory-card.mdc AGENTS.md README.md docs/superpowers/specs/2026-08-14-qa-swarm-test-documentation-design.md docs/superpowers/specs/2026-08-17-qa-swarm-testmo-csv-export-design.md docs/superpowers/specs/2026-08-14-qa-swarm-mcp-verification-design.md
git commit -m "Point testdoc skills and specs at md and csv folders."
```

---

### Task 4: Migrate Upservice testdocs memory

**Files:**
- Move: `memory/upservice/testdocs/task-*.md` → `memory/upservice/testdocs/md/`
- Move: `memory/upservice/testdocs/task-*.csv` → `memory/upservice/testdocs/csv/`
- Modify: `memory/upservice/testdocs/index.md`

**Interfaces:**
- Consumes: schema from Task 2
- Produces: `py -3 tools/memory_schema.py memory/upservice` → `OK`

Slugs to move (all six pairs): `task-4827386`, `task-4867441`, `task-4985417`, `task-5199819`, `task-5201511`, `task-5210629`.

- [ ] **Step 1: Move files with git mv**

```powershell
New-Item -ItemType Directory -Force memory/upservice/testdocs/md, memory/upservice/testdocs/csv | Out-Null
$slugs = @('task-4827386','task-4867441','task-4985417','task-5199819','task-5201511','task-5210629')
foreach ($s in $slugs) {
  git mv "memory/upservice/testdocs/$s.md" "memory/upservice/testdocs/md/$s.md"
  git mv "memory/upservice/testdocs/$s.csv" "memory/upservice/testdocs/csv/$s.csv"
}
```

- [ ] **Step 2: Rewrite index Card links**

`memory/upservice/testdocs/index.md` must keep the same rows and counts. Change every Card cell from `[task-….md](task-….md)` to `[task-….md](md/task-….md)`. Example row:

`| task-5210629 | 5210629 | ready | 21 | [task-5210629.md](md/task-5210629.md) |`

- [ ] **Step 3: Validate schema**

Run: `py -3 tools/memory_schema.py memory/upservice`

Expected: stdout `OK`, exit code 0.

If it fails with `legacy testdoc path`, a file was left in `testdocs/` root. If it fails `missing testdoc CSV`, a csv move was skipped.

- [ ] **Step 4: Re-run unit tests**

Run: `py -3 -m pytest tests/test_testdoc_csv.py tests/test_memory_schema.py tests/test_testdoc_merge.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```powershell
git add memory/upservice/testdocs
git commit -m "Move Upservice testdoc suites into md and csv folders."
```

---

## Self-review

**Spec coverage:**

| Spec section | Task |
|--------------|------|
| Paths `testdocs/md/` + `testdocs/csv/` + index | 1, 2, 4 |
| Path helpers in `memory_schema.py` | 1 |
| `validate_testdoc_csv` via `testdoc_csv_for_suite` | 2 |
| Tree walk `md/*.md` and `csv/*.csv` | 2 |
| Legacy root files | 2 |
| Run lookup `testdocs/md/` | 2 |
| Librarian / generate / verify / coordinator / memory-card | 3 |
| Parent spec path updates | 3 |
| Fixture `demo-testdoc` md+csv | 2 |
| `demo-run` left as lone file | 2 (not moved) |
| Migrate existing Upservice suites | 4 |
| Scenario 1 generate paths | 3 (skills) + 2 (schema) |
| Scenario 2 legacy error | 2 |
| Scenario 3 memory OK | 4 |

**Placeholder scan:** no TBD / “implement later” / “similar to Task N”.

**Type consistency:** `testdoc_suite_path(root, slug)`, `testdoc_csv_path(root, slug)`, `testdoc_csv_for_suite(suite_path)` used in Task 2 with the same names. Error substring `legacy testdoc path` and `missing testdoc testdocs/md/task-1.md` match the spec.
