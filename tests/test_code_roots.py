from __future__ import annotations

from pathlib import Path

import code_roots


def test_resolve_prefers_env(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "fe"
    target.mkdir()
    monkeypatch.setenv("UPSERVICE_FRONTEND_ROOT", str(target))
    cfg = {
        "code": {
            "frontend_env": "UPSERVICE_FRONTEND_ROOT",
            "frontend": str(tmp_path / "other"),
        }
    }
    assert code_roots.resolve_code_root(cfg, "frontend") == target.resolve()


def test_resolve_falls_back_to_root(tmp_path: Path) -> None:
    target = tmp_path / "be"
    target.mkdir()
    cfg = {"code": {"backend": str(target)}}
    assert code_roots.resolve_code_root(cfg, "backend", env={}) == target.resolve()


def test_resolve_missing_returns_none() -> None:
    assert code_roots.resolve_code_root({}, "frontend", env={}) is None
    assert (
        code_roots.resolve_code_root({"code": {"frontend": "/no/such"}}, "frontend", env={})
        is None
    )


def test_format_report_ok_and_missing(tmp_path: Path) -> None:
    fe = tmp_path / "fe"
    fe.mkdir()
    text = code_roots.format_code_roots_report(
        {"frontend": fe.resolve(), "backend": None}
    )
    assert "(ok)" in text
    assert "backend: (missing" in text
