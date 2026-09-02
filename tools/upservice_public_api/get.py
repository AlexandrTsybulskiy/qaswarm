from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[2]

if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from upservice_public_api import client  # noqa: E402


def _parse_scalar(value: str) -> str | int | bool:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if value.isdigit() or (value.startswith("-") and value[1:].isdigit()):
        return int(value)
    return value


def _add_query_value(query: dict[str, object], key: str, value: object) -> None:
    if key not in query:
        query[key] = value
        return
    existing = query[key]
    if isinstance(existing, list):
        if isinstance(value, list):
            existing.extend(value)
        else:
            existing.append(value)
        return
    if isinstance(value, list):
        query[key] = [existing, *value]
    else:
        query[key] = [existing, value]


def parse_query_args(rest: list[str]) -> dict[str, object]:
    query: dict[str, object] = {}
    index = 0
    while index < len(rest):
        arg = rest[index]
        if not arg.startswith("--"):
            raise ValueError(f"unexpected argument: {arg}")
        key = arg[2:]
        if not key or client.QUERY_KEY_RE.fullmatch(key) is None:
            raise ValueError(f"invalid query key: {key}")
        index += 1
        values: list[str] = []
        while index < len(rest) and not rest[index].startswith("--"):
            values.append(rest[index])
            index += 1
        if not values:
            raise ValueError(f"missing value for --{key}")
        if len(values) == 1:
            parsed: str | int | bool | list[str | int | bool] = _parse_scalar(values[0])
        else:
            parsed = [_parse_scalar(value) for value in values]
        _add_query_value(query, key, parsed)
    return query


def run(
    path: str,
    query_args: list[str] | None = None,
    *,
    products_root: Path | None = None,
) -> dict[str, object]:
    normalized = path.strip()
    if not normalized.startswith("/"):
        normalized = f"/{normalized}"
    query: dict[str, object] | None = None
    if query_args:
        query = parse_query_args(query_args)
    merged = client.merge_list_query(query=query)
    if merged is None:
        return {"status_code": 0, "body": {"error": "invalid query"}}
    root = products_root if products_root is not None else REPO_ROOT / "products"
    return client.public_get(normalized, products_root=root, query=merged or None)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="GET one Upservice public API path; prints JSON {status_code, body}."
    )
    parser.add_argument(
        "path",
        help="Catalog path starting with /v1/, e.g. /v1/tasks/5250593 or /v1/projects",
    )
    parser.add_argument(
        "query_args",
        nargs=argparse.REMAINDER,
        help="Optional query flags: --limit 25 --status active --status completed",
    )
    args = parser.parse_args(argv)
    try:
        result = run(args.path, args.query_args or None)
    except ValueError as exc:
        print(json.dumps({"status_code": 0, "body": {"error": str(exc)}}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("status_code") != 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
