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
    assert by_id["tc-1-4"].action == "Open empty"
    assert by_id["tc-1-4"].status == "active"
    assert checklist == ["tc-1-1", "tc-1-3", "tc-1-4"]
    assert next_id == 5


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
