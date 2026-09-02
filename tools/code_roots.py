"""Resolve frontend/backend repo roots from product config."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from product_config import parse_product_yaml

CodeKey = Literal["frontend", "backend"]
CODE_KEYS: tuple[CodeKey, ...] = ("frontend", "backend")


def resolve_code_root(
    config: dict[str, object],
    key: CodeKey,
    env: Mapping[str, str] | None = None,
) -> Path | None:
    environ = env if env is not None else os.environ
    block = config.get("code")
    if not isinstance(block, dict):
        return None
    env_key = f"{key}_env"
    env_var = block.get(env_key)
    if isinstance(env_var, str) and env_var.strip():
        raw = environ.get(env_var.strip())
        if raw:
            path = Path(raw).expanduser()
            if path.is_dir():
                return path.resolve()
    root = block.get(key)
    if isinstance(root, str) and root.strip():
        path = Path(root.strip()).expanduser()
        if path.is_dir():
            return path.resolve()
    return None


def resolve_code_roots(
    config: dict[str, object], env: Mapping[str, str] | None = None
) -> dict[CodeKey, Path | None]:
    return {key: resolve_code_root(config, key, env) for key in CODE_KEYS}


def format_code_roots_report(roots: Mapping[CodeKey, Path | None]) -> str:
    lines: list[str] = []
    for key in CODE_KEYS:
        path = roots.get(key)
        if path:
            lines.append(f"{key}: {path} (ok)")
        else:
            lines.append(f"{key}: (missing — set code.{key} or code.{key}_env in config.yaml)")
    return "\n".join(lines)


def load_product_config(product_dir: Path) -> dict[str, object]:
    cfg_path = product_dir / "config.yaml"
    return parse_product_yaml(cfg_path.read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve product code repo roots.")
    parser.add_argument(
        "product_dir",
        nargs="?",
        type=Path,
        help="Product directory (default: sole folder under products/)",
    )
    args = parser.parse_args(argv)
    product_dir = args.product_dir
    if product_dir is None:
        products_root = Path(__file__).resolve().parents[1] / "products"
        dirs = [path for path in products_root.iterdir() if path.is_dir()]
        if len(dirs) != 1:
            parser.error("pass product_dir when products/ does not contain exactly one folder")
        product_dir = dirs[0]
    config = load_product_config(product_dir)
    roots = resolve_code_roots(config)
    print(format_code_roots_report(roots))
    return 0 if all(roots.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
