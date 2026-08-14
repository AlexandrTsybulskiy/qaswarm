from datetime import datetime, timedelta, timezone
from pathlib import Path

import memory_schema

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "fixtures" / "demo-catalog" / "expected"
INCOMING = ROOT / "fixtures" / "demo-catalog" / "incoming"


def test_valid_expected_tree_has_no_errors() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_card_missing_fetched_at_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "product: demo\n---\n\nUser entity.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("fetched_at" in e for e in errors)


def test_card_rejects_naive_fetched_at(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00\nproduct: demo\n---\n\nUser entity.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("timezone offset" in e for e in errors)


def test_slug_rejects_uppercase() -> None:
    assert memory_schema.slug_ok("User") is False
    assert memory_schema.slug_ok("user") is True
    assert memory_schema.slug_ok("order-item") is True


def test_ttl_fresh_within_default_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=24)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is True


def test_ttl_expired_after_ttl_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=169)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is False


def test_incoming_without_manifest_is_incomplete(tmp_path: Path) -> None:
    incoming = tmp_path / "_incoming"
    incoming.mkdir()
    (incoming / "catalog.json").write_text("{}", encoding="utf-8")
    assert memory_schema.incoming_complete(incoming) is False


def test_incoming_rejects_parent_path_escape(tmp_path: Path) -> None:
    incoming = tmp_path / "_incoming"
    incoming.mkdir()
    (tmp_path / "catalog.json").write_text("{}", encoding="utf-8")
    (incoming / "MANIFEST.md").write_text("- ../catalog.json\n", encoding="utf-8")
    assert memory_schema.incoming_complete(incoming) is False


def test_incoming_rejects_absolute_manifest_path(tmp_path: Path) -> None:
    incoming = tmp_path / "_incoming"
    incoming.mkdir()
    outside = tmp_path / "catalog.json"
    outside.write_text("{}", encoding="utf-8")
    (incoming / "MANIFEST.md").write_text(f"- {outside}\n", encoding="utf-8")
    assert memory_schema.incoming_complete(incoming) is False


def test_demo_incoming_is_complete() -> None:
    assert memory_schema.incoming_complete(INCOMING) is True


def test_secret_like_value_in_card_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\n"
        "token: sk-abc123secret\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("secret" in e.lower() for e in errors)


def test_authorization_bearer_value_in_card_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\n"
        "Authorization: Bearer abc123secret\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("secret" in e.lower() for e in errors)


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


def test_requirement_ready_requires_arrow_in_list_item(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "status: ready\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\nProse action → expected result.\n\n"
        "- no expected result\n\n## Gaps\n\n- none\n\nDid not write to Upservice.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("Testable item with arrow" in e for e in errors)


def test_requirement_requires_gaps_heading(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "status: draft\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\n- none\n\nDid not write to Upservice.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("## Gaps" in e for e in errors)


def test_requirement_requires_no_write_notice(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Demo\nproduct: demo\ntask_id: 1\n"
        "status: draft\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\n- none\n\n## Gaps\n\n- none\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("Did not write to Upservice" in e for e in errors)


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


def test_requirement_task_id_must_be_normalized(tmp_path: Path) -> None:
    card = tmp_path / "task-abc.md"
    card.write_text(
        "---\nslug: task-abc\ntitle: Demo\nproduct: demo\ntask_id: ABC\n"
        "status: draft\nsource_task: upservice\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary.\n\n## Testable\n\n- none\n\n## Gaps\n\n- none\n\n"
        "Did not write to Upservice.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_requirement_card(card)
    assert any("invalid task_id" in e for e in errors)


def test_task_snapshot_requires_task_id(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    card.write_text(
        "---\nslug: task-1\ntitle: Task 1\nstatus: deep\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\nA task.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_task_snapshot(card)
    assert any("task_id" in e for e in errors)


def test_task_snapshot_task_id_must_be_normalized(tmp_path: Path) -> None:
    card = tmp_path / "task-ABC.md"
    card.write_text(
        "---\nslug: task-ABC\ntitle: Task ABC\nstatus: deep\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\ntask_id: ABC\n"
        "---\n\nA task.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_task_snapshot(card)
    assert any("invalid task_id" in e for e in errors)


def test_memory_tree_validates_spec_only_requirement_slug(tmp_path: Path) -> None:
    requirements = tmp_path / "requirements"
    requirements.mkdir()
    (requirements / "index.md").write_text("# Requirements\n", encoding="utf-8")
    (requirements / "checkout-spec.md").write_text(
        "---\nslug: checkout-spec\ntitle: Checkout\nproduct: demo\ntask_id: none\n"
        "status: draft\nsource_task: none\nsource_design: none\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nfigma_urls: none\nentities: none\n"
        "---\n\nSummary without required sections.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_memory_tree(tmp_path)
    assert any("checkout-spec.md" in e and "## Gaps" in e for e in errors)


def test_demo_requirement_incoming_complete() -> None:
    assert memory_schema.incoming_complete(REQ_INCOMING) is True


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
            "- tc-1-1\n- tc-1-3\n- tc-1-4\n",
            "- tc-1-1\n- tc-1-3\n- tc-1-4\n- tc-1-2\n",
        ),
        encoding="utf-8",
    )
    errors = memory_schema.validate_testdoc_suite(card)
    assert any("checklist" in e.lower() for e in errors)


def test_testdoc_merge_fixture_matches_expected() -> None:
    import testdoc_merge

    text = testdoc_merge.merge_files(TD_INCOMING / "testdocs.md", TD_EXISTING)
    assert memory_schema.parse_frontmatter(text)[0]["next_id"] == "5"
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
