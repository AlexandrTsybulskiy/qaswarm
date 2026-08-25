"""Scan Playwright repo for qaswarm_tc markers; classify testdoc channels."""

from __future__ import annotations

import argparse
import ast
import os
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
        if (
            node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
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


def _record_binding(
    by_id: dict[str, TcBinding],
    duplicates: set[str],
    tc_id: str,
    binding: TcBinding,
) -> None:
    if tc_id in by_id and by_id[tc_id] != binding:
        duplicates.add(tc_id)
    by_id[tc_id] = binding


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
            if isinstance(node, ast.ClassDef):
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        for tc_id in _function_tc_ids(item):
                            nodeid = f"{rel}::{node.name}::{item.name}"
                            _record_binding(
                                by_id, duplicates, tc_id, TcBinding(tc_id, rel, nodeid)
                            )
                continue
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for tc_id in _function_tc_ids(node):
                nodeid = f"{rel}::{node.name}"
                _record_binding(
                    by_id, duplicates, tc_id, TcBinding(tc_id, rel, nodeid)
                )
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
    for binding in bindings:
        print(f"{binding.tc_id}\t{binding.path}\t{binding.nodeid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
