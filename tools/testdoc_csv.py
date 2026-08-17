from __future__ import annotations

import argparse
import csv
import io
import sys
from pathlib import Path

import testdoc_merge
from memory_schema import parse_frontmatter
from testdoc_merge import TestdocCase

CSV_COLUMNS: tuple[str, ...] = ("Name", "Folder", "Steps", "Expected", "Id")


def checklist_ids(body: str) -> list[str]:
    chunk = body.split("## Checklist", 1)
    check_body = chunk[1].split("##", 1)[0] if len(chunk) == 2 else ""
    ids: list[str] = []
    for line in check_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            ids.append(stripped[2:].strip())
    return ids


def csv_rows(
    folder: str,
    cases: list[TestdocCase],
    checklist: list[str],
) -> list[dict[str, str]]:
    active = {
        case.case_id: case
        for case in cases
        if case.status == "active" and case.case_id
    }
    rows: list[dict[str, str]] = []
    for case_id in checklist:
        case = active.get(case_id)
        if case is None:
            continue
        rows.append(
            {
                "Name": case.title,
                "Folder": folder,
                "Steps": case.action,
                "Expected": case.expected,
                "Id": case.case_id or "",
            }
        )
    return rows


def render_csv(rows: list[dict[str, str]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=list(CSV_COLUMNS),
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in CSV_COLUMNS})
    return buffer.getvalue()


def export_suite(suite_path: Path) -> str:
    if suite_path.name == "index.md":
        raise ValueError(f"{suite_path}: not a testdoc suite")
    text = suite_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    if not meta:
        raise ValueError(f"{suite_path}: not a testdoc suite")
    if meta.get("status") == "draft":
        return render_csv([])
    title = meta.get("title", "")
    cases = testdoc_merge.parse_canonical_cases(body)
    return render_csv(csv_rows(title, cases, checklist_ids(body)))


def write_csv(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(content, encoding="utf-8", newline="\n")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export testdoc suite to Testmo CSV")
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if not args.suite.is_file():
            raise FileNotFoundError(args.suite)
        text = export_suite(args.suite)
        write_csv(args.output, text)
    except (OSError, ValueError, KeyError, csv.Error) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    sys.stdout.write(f"{args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
