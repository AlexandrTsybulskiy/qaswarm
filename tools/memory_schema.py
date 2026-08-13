from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REQUIRED_FIELDS = ("slug", "title", "status", "source", "fetched_at", "product")
STATUSES = {"map", "deep", "stale"}
SOURCES = {"public", "internal", "browser"}
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
