from pathlib import Path

import testdoc_csv
from testdoc_merge import TestdocCase

ROOT = Path(__file__).resolve().parents[1]
TD_EXPECTED = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "md" / "task-1.md"
TD_CSV = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "csv" / "task-1.csv"


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


TD_INDEX = ROOT / "fixtures" / "demo-testdoc" / "expected" / "testdocs" / "index.md"

DRAFT_SUITE = """\
---
slug: draft-1
title: Draft suite
status: draft
---

## Cases

### tc-1-1
title: Active case
action: Do thing
expected: Works
status: active

## Checklist

- tc-1-1
"""


def test_export_draft_suite_header_only(tmp_path: Path) -> None:
    draft = tmp_path / "draft.md"
    draft.write_text(DRAFT_SUITE, encoding="utf-8")
    assert testdoc_csv.export_suite(draft) == "Name,Folder,Steps,Expected,Id\n"


def test_cli_index_md_does_not_write(tmp_path: Path) -> None:
    output = tmp_path / "out.csv"
    code = testdoc_csv.main(
        ["--suite", str(TD_INDEX), "--output", str(output)]
    )
    assert code == 1
    assert not output.exists()
