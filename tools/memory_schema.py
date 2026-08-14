from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REQUIRED_FIELDS = ("slug", "title", "status", "source", "fetched_at", "product")
STATUSES = {"map", "deep", "stale"}
SOURCES = {"public", "internal", "browser"}
REQ_REQUIRED = (
    "slug",
    "title",
    "product",
    "task_id",
    "status",
    "source_task",
    "source_design",
    "fetched_at",
    "figma_urls",
    "entities",
)
REQ_STATUSES = {"draft", "ready", "stale"}
SOURCE_TASK_VALUES = {"upservice", "none"}
SOURCE_DESIGN_VALUES = {"figma", "none"}
TD_REQUIRED = (
    "slug",
    "title",
    "product",
    "task_id",
    "requirement",
    "status",
    "fetched_at",
    "next_id",
)
TD_STATUSES = {"draft", "ready", "stale"}
TD_CASE_STATUSES = {"active", "orphan"}
SLUG_RE = re.compile(r"^[a-z0-9-]+$")
SECRET_RE = re.compile(
    r"(?i)(?:(?:token|password|secret|api[_-]?key)\s*[:=]\s*"
    r"(?:sk-|ghp_|xox[baprs]-|Bearer\s+)?|Authorization\s*:\s*Bearer\s+)\S+"
)
PLACEHOLDER_VALUES = {"скрыто", "redacted", "hidden", "[redacted]"}


def slug_ok(value: str) -> bool:
    return bool(SLUG_RE.fullmatch(value))


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict[str, str] = {}
    for line in parts[1].splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, raw = line.split(":", 1)
        meta[key.strip()] = raw.strip()
    return meta, parts[2].lstrip("\n")


def is_fresh(fetched_at: str, ttl_hours: int, now: datetime) -> bool:
    stamp = datetime.fromisoformat(fetched_at)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now - stamp <= timedelta(hours=ttl_hours)


def incoming_complete(incoming_dir: Path) -> bool:
    manifest = incoming_dir / "MANIFEST.md"
    if not manifest.is_file():
        return False
    listed: list[str] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            listed.append(stripped[2:].strip())
    if not listed:
        return False
    incoming_root = incoming_dir.resolve()
    for name in listed:
        relative = Path(name)
        if relative.is_absolute():
            return False
        candidate = (incoming_root / relative).resolve()
        if not candidate.is_relative_to(incoming_root) or not candidate.is_file():
            return False
    return True


def _looks_like_secret(text: str) -> bool:
    for match in SECRET_RE.finditer(text):
        value = match.group(0).split(":", 1)[-1].split("=", 1)[-1].strip()
        value = re.sub(r"(?i)^Bearer\s+", "", value)
        if value.lower() not in PLACEHOLDER_VALUES:
            return True
    return False


def validate_card(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in REQUIRED_FIELDS:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    source = meta.get("source", "")
    if source and source not in SOURCES:
        errors.append(f"{path}: invalid source {source!r}")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    fetched = meta.get("fetched_at")
    if fetched:
        try:
            stamp = datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
        else:
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                errors.append(f"{path}: fetched_at must include timezone offset")
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    return errors


def validate_task_snapshot(path: Path) -> list[str]:
    errors = validate_card(path)
    meta, _body = parse_frontmatter(path.read_text(encoding="utf-8"))
    task_id = meta.get("task_id", "")
    if not task_id:
        errors.append(f"{path}: missing task_id")
    elif not slug_ok(task_id):
        errors.append(f"{path}: invalid task_id {task_id!r}")
    slug = meta.get("slug", "")
    if task_id and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    return errors


def validate_requirement_card(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in REQ_REQUIRED:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in REQ_STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    if meta.get("source_task") and meta["source_task"] not in SOURCE_TASK_VALUES:
        errors.append(f"{path}: invalid source_task")
    if meta.get("source_design") and meta["source_design"] not in SOURCE_DESIGN_VALUES:
        errors.append(f"{path}: invalid source_design")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    task_id = meta.get("task_id", "")
    if task_id and task_id != "none" and not slug_ok(task_id):
        errors.append(f"{path}: invalid task_id {task_id!r}")
    if task_id and task_id != "none" and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    fetched = meta.get("fetched_at")
    if fetched:
        try:
            stamp = datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
        else:
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                errors.append(f"{path}: fetched_at must include timezone offset")
    if meta.get("source_design") == "figma" and meta.get("figma_urls", "none") == "none":
        errors.append(f"{path}: source_design figma requires figma_urls")
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    if not re.search(r"(?m)^## Gaps\s*$", body):
        errors.append(f"{path}: missing ## Gaps heading")
    if not any("Did not write to Upservice" in line for line in body.splitlines()):
        errors.append(f"{path}: missing Did not write to Upservice notice")
    if status == "ready":
        testable = body.split("## Testable", 1)
        chunk = testable[1].split("##", 1)[0] if len(testable) == 2 else ""
        if not re.search(r"(?m)^\s*[-*+]\s+.*(?:→|->).*$", chunk):
            errors.append(f"{path}: ready card needs Testable item with arrow")
    return errors


def validate_testdoc_suite(path: Path) -> list[str]:
    import testdoc_merge

    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    for field in TD_REQUIRED:
        if field not in meta or not meta[field]:
            errors.append(f"{path}: missing {field}")
    status = meta.get("status", "")
    if status and status not in TD_STATUSES:
        errors.append(f"{path}: invalid status {status!r}")
    slug = meta.get("slug", "")
    if slug and not slug_ok(slug):
        errors.append(f"{path}: invalid slug {slug!r}")
    if slug and path.stem != slug:
        errors.append(f"{path}: filename stem {path.stem!r} != slug {slug!r}")
    task_id = meta.get("task_id", "")
    if task_id and task_id != "none" and not slug_ok(task_id):
        errors.append(f"{path}: invalid task_id {task_id!r}")
    if task_id and task_id != "none" and slug and slug != f"task-{task_id}":
        errors.append(f"{path}: slug {slug!r} must be task-{task_id}")
    requirement = meta.get("requirement", "")
    if requirement and not slug_ok(requirement):
        errors.append(f"{path}: invalid requirement {requirement!r}")
    fetched = meta.get("fetched_at")
    if fetched:
        try:
            stamp = datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
        else:
            if stamp.tzinfo is None or stamp.utcoffset() is None:
                errors.append(f"{path}: fetched_at must include timezone offset")
    next_raw = meta.get("next_id", "")
    next_id = 0
    if next_raw:
        if not re.fullmatch(r"[1-9][0-9]*", next_raw):
            errors.append(f"{path}: next_id must be an integer >= 1")
        else:
            next_id = int(next_raw)
    if _looks_like_secret(text):
        errors.append(f"{path}: secret-like value in card")
    if not body.strip():
        errors.append(f"{path}: empty body")
    for heading in ("## Cases", "## Checklist", "## Gaps"):
        if not re.search(rf"(?m)^{re.escape(heading)}\s*$", body):
            errors.append(f"{path}: missing {heading} heading")
    if not any(
        "Did not write to Upservice" in line and "Testmo" in line
        for line in body.splitlines()
    ):
        errors.append(f"{path}: missing Did not write to Upservice or Testmo notice")
    cases = testdoc_merge.parse_canonical_cases(body)
    prefix = testdoc_merge.case_id_prefix(task_id or "none", slug)
    active_ids: list[str] = []
    max_n = 0
    for case in cases:
        if not case.case_id or not case.case_id.startswith(f"tc-{prefix}-"):
            errors.append(f"{path}: invalid case id {case.case_id!r}")
        elif not re.fullmatch(rf"tc-{re.escape(prefix)}-[1-9][0-9]*", case.case_id):
            errors.append(f"{path}: invalid case id {case.case_id!r}")
        if case.status not in TD_CASE_STATUSES:
            errors.append(f"{path}: invalid case status {case.status!r}")
        if not case.action or not case.expected:
            errors.append(f"{path}: case {case.case_id} missing action or expected")
        if case.case_id:
            _, _, last = case.case_id.rpartition("-")
            if last.isdigit():
                max_n = max(max_n, int(last))
        if case.status == "active" and case.case_id:
            active_ids.append(case.case_id)
    if status == "ready" and not active_ids:
        errors.append(f"{path}: ready suite needs an active case")
    checklist: list[str] = []
    chunk = body.split("## Checklist", 1)
    check_body = chunk[1].split("##", 1)[0] if len(chunk) == 2 else ""
    for line in check_body.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            checklist.append(stripped[2:].strip())
    if checklist != active_ids:
        errors.append(f"{path}: checklist must list active ids in case order")
    if next_id and max_n and next_id != max_n + 1:
        errors.append(f"{path}: next_id {next_id} must be {max_n + 1}")
    if next_id and not cases and next_id != 1:
        errors.append(f"{path}: empty suite next_id must be 1")
    return errors


def validate_memory_tree(root: Path) -> list[str]:
    errors: list[str] = []
    index = root / "index.md"
    catalog = root / "catalog" / "api.md"
    gaps = root / "gaps.md"
    entities = root / "entities"
    for required in (index, catalog, gaps, entities):
        if not required.exists():
            errors.append(f"{root}: missing {required.relative_to(root)}")
    if entities.is_dir():
        cards = list(entities.glob("*.md"))
        if not cards:
            errors.append(f"{root}: no entity cards")
        for card in cards:
            errors.extend(validate_card(card))
    incoming = root / "raw" / "_incoming"
    if incoming.is_dir() and any(incoming.iterdir()) and not incoming_complete(incoming):
        errors.append(f"{root}: incomplete incoming (no valid MANIFEST)")
    tasks_dir = root / "tasks"
    if tasks_dir.is_dir():
        for card in tasks_dir.glob("task-*.md"):
            errors.extend(validate_task_snapshot(card))
    req_dir = root / "requirements"
    if req_dir.is_dir():
        for card in req_dir.glob("*.md"):
            if card.name == "index.md":
                continue
            errors.extend(validate_requirement_card(card))
    testdocs_dir = root / "testdocs"
    if testdocs_dir.is_dir():
        for card in testdocs_dir.glob("*.md"):
            if card.name == "index.md":
                continue
            errors.extend(validate_testdoc_suite(card))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate QA swarm memory tree")
    parser.add_argument("root", type=Path)
    args = parser.parse_args(argv)
    errors = validate_memory_tree(args.root)
    if errors:
        sys.stdout.write("\n".join(errors) + "\n")
        return 1
    sys.stdout.write("OK\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
