from __future__ import annotations

import textwrap
from pathlib import Path

import e2e_scan


def test_resolve_root_prefers_env(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "pw"
    target.mkdir()
    monkeypatch.setenv("UPSERVICE_PLAYWRIGHT_ROOT", str(target))
    cfg = {
        "playwright": {
            "root_env": "UPSERVICE_PLAYWRIGHT_ROOT",
            "root": str(tmp_path / "other"),
        }
    }
    assert e2e_scan.resolve_playwright_root(cfg) == target.resolve()


def test_resolve_root_falls_back_to_root(tmp_path: Path) -> None:
    target = tmp_path / "pw"
    target.mkdir()
    cfg = {"playwright": {"root": str(target)}}
    assert e2e_scan.resolve_playwright_root(cfg, env={}) == target.resolve()


def test_resolve_root_missing_returns_none() -> None:
    assert e2e_scan.resolve_playwright_root({}, env={}) is None
    assert (
        e2e_scan.resolve_playwright_root({"playwright": {"root": "/no/such"}}, env={})
        is None
    )


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
            """
            import pytest

            @pytest.mark.qaswarm_tc("tc-1-1")
            def test_widget_visible():
                assert True
            """
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
    for name in ("test_a.py", "test_b.py"):
        (tests / name).write_text(
            'import pytest\n@pytest.mark.qaswarm_tc("tc-1-1")\ndef test_x():\n    pass\n',
            encoding="utf-8",
        )
    try:
        e2e_scan.scan_qaswarm_tc(tmp_path)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "tc-1-1" in str(exc)
