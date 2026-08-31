from __future__ import annotations

import argparse
import sys
from pathlib import Path

from product_config import format_connection_report, resolve_product_connection


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resolve active Upservice environment settings.")
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
    resolved = resolve_product_connection(product_dir)
    print(format_connection_report(resolved))
    return 0 if resolved["public_api"]["token_set"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
