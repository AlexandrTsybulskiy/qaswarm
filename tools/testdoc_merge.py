from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from memory_schema import parse_frontmatter


@dataclass
class TestdocCase:
    title: str
    action: str
    expected: str
    status: str = "active"
    case_id: str | None = None


def match_key(action: str, expected: str) -> str:
    return f"{action.strip()}\n{expected.strip()}"


def case_id_prefix(task_id: str, slug: str) -> str:
    if task_id and task_id != "none":
        return task_id
    return slug


def format_case_id(prefix: str, n: int) -> str:
    return f"tc-{prefix}-{n}"


def _section_body(body: str, heading: str) -> str:
    pattern = re.compile(rf"(?ms)^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)")
    match = pattern.search(body)
    return match.group(1) if match else ""


def _parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or ":" not in stripped:
            continue
        key, raw = stripped.split(":", 1)
        fields[key.strip()] = raw.strip()
    return fields


def _case_blocks(section: str) -> list[str]:
    chunks = re.split(r"(?m)^### .+\n", section)
    return [chunk for chunk in chunks[1:] if chunk.strip()]


def parse_incoming_body(body: str) -> tuple[list[TestdocCase], list[str]]:
    cases: list[TestdocCase] = []
    for block in _case_blocks(_section_body(body, "Cases")):
        fields = _parse_fields(block)
        cases.append(
            TestdocCase(
                title=fields.get("title", ""),
                action=fields.get("action", ""),
                expected=fields.get("expected", ""),
            )
        )
    gaps: list[str] = []
    for line in _section_body(body, "Gaps").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            gaps.append(stripped[2:].strip())
    return cases, gaps


def parse_canonical_cases(body: str) -> list[TestdocCase]:
    cases: list[TestdocCase] = []
    section = _section_body(body, "Cases")
    headings = re.findall(r"(?m)^### (\S+)\s*$", section)
    blocks = _case_blocks(section)
    for heading, block in zip(headings, blocks, strict=False):
        fields = _parse_fields(block)
        cases.append(
            TestdocCase(
                title=fields.get("title", ""),
                action=fields.get("action", ""),
                expected=fields.get("expected", ""),
                status=fields.get("status", "active"),
                case_id=heading,
            )
        )
    return cases


def _case_number(case_id: str | None) -> int:
    if not case_id:
        return 0
    _, _, last = case_id.rpartition("-")
    return int(last) if last.isdigit() else 0


def merge_testdoc_cases(
    existing: list[TestdocCase],
    incoming: list[TestdocCase],
    prefix: str,
    next_id: int,
) -> tuple[list[TestdocCase], list[str], int]:
    claimed: set[int] = set()
    active: list[TestdocCase] = []
    cursor = next_id
    for item in incoming:
        key = match_key(item.action, item.expected)
        found: int | None = None
        for index, prior in enumerate(existing):
            if index in claimed:
                continue
            if match_key(prior.action, prior.expected) == key:
                found = index
                break
        if found is not None:
            claimed.add(found)
            prior = existing[found]
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=prior.case_id,
                )
            )
        else:
            active.append(
                TestdocCase(
                    title=item.title,
                    action=item.action.strip(),
                    expected=item.expected.strip(),
                    status="active",
                    case_id=format_case_id(prefix, cursor),
                )
            )
            cursor += 1
    orphans = [
        TestdocCase(
            title=prior.title,
            action=prior.action,
            expected=prior.expected,
            status="orphan",
            case_id=prior.case_id,
        )
        for index, prior in enumerate(existing)
        if index not in claimed
    ]
    cases = active + orphans
    checklist = [case.case_id for case in active if case.case_id]
    max_n = max([_case_number(case.case_id) for case in cases] + [cursor - 1, 0])
    return cases, checklist, max_n + 1


def render_testdoc(
    meta: dict[str, str],
    cases: list[TestdocCase],
    checklist: list[str],
    gaps: list[str],
) -> str:
    lines = ["---"]
    for key in (
        "slug",
        "title",
        "product",
        "task_id",
        "requirement",
        "status",
        "fetched_at",
        "next_id",
    ):
        lines.append(f"{key}: {meta[key]}")
    lines.extend(["---", "", "## Cases", ""])
    for case in cases:
        lines.extend(
            [
                f"### {case.case_id}",
                f"title: {case.title}",
                f"action: {case.action}",
                f"expected: {case.expected}",
                f"status: {case.status}",
                "",
            ]
        )
    lines.extend(["## Checklist", ""])
    for case_id in checklist:
        lines.append(f"- {case_id}")
    if not checklist:
        lines.append("")
    lines.extend(["", "## Gaps", ""])
    if gaps:
        for gap in gaps:
            lines.append(f"- {gap}")
    else:
        lines.append("- none")
    lines.extend(["", "Did not write to Upservice or Testmo.", ""])
    return "\n".join(lines)


def merge_files(incoming_path: Path, existing_path: Path | None) -> str:
    incoming_meta, incoming_body = parse_frontmatter(
        incoming_path.read_text(encoding="utf-8")
    )
    incoming_cases, gaps = parse_incoming_body(incoming_body)
    existing_cases: list[TestdocCase] = []
    next_id = 1
    if existing_path is not None and existing_path.is_file():
        existing_meta, existing_body = parse_frontmatter(
            existing_path.read_text(encoding="utf-8")
        )
        existing_cases = parse_canonical_cases(existing_body)
        next_id = int(existing_meta.get("next_id", "1"))
    prefix = case_id_prefix(incoming_meta["task_id"], incoming_meta["slug"])
    cases, checklist, new_next = merge_testdoc_cases(
        existing_cases, incoming_cases, prefix, next_id
    )
    status = "ready" if any(case.status == "active" for case in cases) else "draft"
    meta = {
        "slug": incoming_meta["slug"],
        "title": incoming_meta["title"],
        "product": incoming_meta["product"],
        "task_id": incoming_meta["task_id"],
        "requirement": incoming_meta["requirement"],
        "status": status,
        "fetched_at": incoming_meta["fetched_at"],
        "next_id": str(new_next),
    }
    return render_testdoc(meta, cases, checklist, gaps)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Merge testdoc incoming into a suite")
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--existing", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        text = merge_files(args.incoming, args.existing)
    except (KeyError, ValueError, OSError) as exc:
        sys.stderr.write(f"{exc}\n")
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    sys.stdout.write(f"{args.output}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
