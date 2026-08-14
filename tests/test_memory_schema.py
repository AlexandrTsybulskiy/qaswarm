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


def test_run_non_skipped_empty_observed_fails(tmp_path: Path) -> None:
    for verdict, channel, reason_line in (
        ("fail", "browser", "reason: expected not matched\n"),
        ("blocked", "none", "reason: env unavailable\n"),
        ("pass", "http", ""),
    ):
        card = tmp_path / f"task-{verdict}.md"
        text = RUN_EXPECTED.read_text(encoding="utf-8").replace(
            "### tc-1-1\nverdict: fail\nchannel: browser\n"
            "observed: Settings screen missing Menu item\n"
            "reason: expected not matched\n",
            f"### tc-1-1\nverdict: {verdict}\nchannel: {channel}\n"
            f"observed:\n{reason_line}",
        )
        if verdict == "pass":
            text = text.replace("fail: 1", "fail: 0").replace("pass: 1", "pass: 2")
        card.write_text(text, encoding="utf-8")
        errors = memory_schema.validate_run_card(card)
        assert any("missing observed" in e for e in errors), verdict


def test_run_skipped_empty_observed_valid() -> None:
    assert memory_schema.validate_run_card(RUN_EXPECTED) == []


def test_parse_run_results_empty_block_keeps_pairing() -> None:
    body = (
        "## Results\n\n"
        "### tc-1-1\n\n"
        "### tc-1-2\n"
        "verdict: pass\n"
        "channel: http\n"
        "observed: 200 OK\n"
    )
    results = memory_schema.parse_run_results(body)
    assert len(results) == 2
    assert results[0].case_id == "tc-1-1"
    assert results[0].observed == ""
    assert results[0].verdict == ""
    assert results[1].case_id == "tc-1-2"
    assert results[1].observed == "200 OK"
    assert results[1].verdict == "pass"


def test_run_empty_result_block_does_not_steal_next_case_fields(tmp_path: Path) -> None:
    card = tmp_path / "task-1.md"
    text = RUN_EXPECTED.read_text(encoding="utf-8").replace(
        "### tc-1-1\nverdict: fail\nchannel: browser\n"
        "observed: Settings screen missing Menu item\n"
        "reason: expected not matched\n",
        "### tc-1-1\n\n",
    )
    card.write_text(text, encoding="utf-8")
    errors = memory_schema.validate_run_card(card)
    assert any("tc-1-1" in e and "missing observed" in e for e in errors)
    assert not any("tc-1-2" in e and "missing observed" in e for e in errors)
