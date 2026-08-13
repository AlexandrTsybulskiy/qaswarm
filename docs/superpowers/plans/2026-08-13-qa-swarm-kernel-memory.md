# QA Swarm Kernel + Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Собрать в репозитории `qaswarm` Cursor-команду (координатор, Hunter, Librarian) с git-памятью продукта и тремя skills: карта системы, ответ из памяти, точечное обновление.

**Architecture:** Человек говорит только с координатором. Hunter пишет сырьё в `memory/<product-id>/raw/_incoming/` (плюс `MANIFEST.md`). Librarian — единственный писатель канона (`index.md`, `catalog/api.md`, `entities/*.md`, `gaps.md`). Ответы человеку только из канона. Python-модуль `tools/memory_schema.py` не ходит в продукт: это контракт схемы и CLI для ревью/фикстур.

**Tech Stack:** Cursor (AGENTS.md, `.cursor/rules/*.mdc`, `.cursor/agents/*.md`, `.cursor/skills/*/SKILL.md`), Markdown/YAML память, Python 3.11+ stdlib + pytest/ruff (dev), без HTTP-клиента, БД и RAG.

## Global Constraints

- Workspace: отдельный репозиторий `qaswarm`; продукт снаружи; хост/токены не угадывать.
- Имена `product-id` и `slug`: только `[a-z0-9-]`.
- Лестница источников: public API → internal API (если есть в конфиге) → browser MCP только если API не ответил.
- Browser MCP на `index-system` запрещён.
- Координатор не пишет в `memory/`. Hunter не пишет канон. Librarian не ходит в продукт.
- Секреты не в git, не в карточках, не в ответах чата.
- Повторный `index-system` не понижает `deep` → `map` и не затирает тело `deep`.
- На один `product-id`: не больше одного Hunter; замок — непустой `raw/_incoming/`.
- `ttl_hours` по умолчанию `168`; истекший TTL при `recall` = промах (добор), не фоновая запись `stale`.
- `status: stale` пишет только Librarian перед `refresh`.
- Если `catalog_hint` = `unknown`, пробовать только `/openapi.json`, `/swagger.json`, `/swagger/v1/swagger.json`, `/api-docs`.
- В `products/` в v1 ровно один каталог продукта; ноль — стоп; больше одного — спросить id.
- Skills: `index-system`, `recall`, `refresh`. Субагенты: `hunter`, `librarian`.
- Не делать: тест-доки, тикеты, e2e/Playwright, RAG, CLI-оркестратор, обход UI на старте, полный дамп записей API.

### File map (создаём по задачам)

| Path | Responsibility |
|------|----------------|
| `tools/memory_schema.py` | Парсинг frontmatter, TTL, валидация дерева памяти, CLI |
| `tests/test_memory_schema.py` | Контракт схемы и фикстур |
| `tests/conftest.py` | `sys.path` на `tools/` |
| `pyproject.toml` | pytest, ruff, pythonpath |
| `.gitignore` | `.env`, кэши, `_incoming/` |
| `docs/examples/product-config.yaml` | Шаблон подключения продукта |
| `products/README.md` | Как создать единственный `products/<id>/` |
| `memory/README.md` | Что канон, что сырьё |
| `fixtures/demo-catalog/incoming/` | Эталон выхода Hunter |
| `fixtures/demo-catalog/expected/` | Эталон канона Librarian |
| `.cursor/rules/coordinator.mdc` | Маршрутизация, запрет писать память |
| `.cursor/rules/memory-card.mdc` | Схема карточки при работе с `memory/**` |
| `.cursor/agents/hunter.md` | Субагент Hunter |
| `.cursor/agents/librarian.md` | Субагент Librarian |
| `.cursor/skills/index-system/SKILL.md` | Стартовая карта |
| `.cursor/skills/recall/SKILL.md` | Вопрос из памяти |
| `.cursor/skills/refresh/SKILL.md` | Обновление |
| `AGENTS.md` | Точка входа координатора |
| `README.md` | Как запустить v1 в Cursor |

---

### Task 1: Контракт памяти (схема + фикстуры + CLI)

**Files:**
- Create: `tools/memory_schema.py`
- Create: `tests/conftest.py`
- Create: `tests/test_memory_schema.py`
- Create: `pyproject.toml`
- Create: `fixtures/demo-catalog/incoming/catalog.json`
- Create: `fixtures/demo-catalog/incoming/MANIFEST.md`
- Create: `fixtures/demo-catalog/expected/index.md`
- Create: `fixtures/demo-catalog/expected/gaps.md`
- Create: `fixtures/demo-catalog/expected/catalog/api.md`
- Create: `fixtures/demo-catalog/expected/entities/user.md`
- Create: `fixtures/demo-catalog/expected/entities/order.md`
- Test: `tests/test_memory_schema.py`

**Interfaces:**
- Consumes: nothing (greenfield)
- Produces:
  - `parse_frontmatter(text: str) -> tuple[dict[str, str], str]`
  - `validate_card(path: Path) -> list[str]` — пустой список = ок
  - `is_fresh(fetched_at: str, ttl_hours: int, now: datetime) -> bool`
  - `incoming_complete(incoming_dir: Path) -> bool`
  - `validate_memory_tree(root: Path) -> list[str]`
  - CLI: `python tools/memory_schema.py <memory-root>` exit 0 если ошибок нет, иначе 1 и список ошибок в stdout
  - Hunter incoming JSON: объект с полями `channel`, `fetched_at`, `base_url`, `resources` (список `{path, methods, title, slug_hint, summary}`), `errors` (список `{channel, code, message}`)

- [ ] **Step 1: Write the failing test**

Create `tests/conftest.py`:

```python
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
```

Create `tests/test_memory_schema.py`:

```python
from datetime import datetime, timedelta, timezone
from pathlib import Path

import memory_schema

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = ROOT / "fixtures" / "demo-catalog" / "expected"
INCOMING = ROOT / "fixtures" / "demo-catalog" / "incoming"


def test_valid_expected_tree_has_no_errors() -> None:
    errors = memory_schema.validate_memory_tree(EXPECTED)
    assert errors == []


def test_card_missing_fetched_at_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "product: demo\n---\n\nUser entity.\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("fetched_at" in e for e in errors)


def test_slug_rejects_uppercase() -> None:
    assert memory_schema.slug_ok("User") is False
    assert memory_schema.slug_ok("user") is True
    assert memory_schema.slug_ok("order-item") is True


def test_ttl_fresh_within_default_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=24)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is True


def test_ttl_expired_after_ttl_hours() -> None:
    now = datetime(2026, 8, 13, 20, 0, tzinfo=timezone.utc)
    fetched = (now - timedelta(hours=169)).isoformat()
    assert memory_schema.is_fresh(fetched, 168, now) is False


def test_incoming_without_manifest_is_incomplete(tmp_path: Path) -> None:
    incoming = tmp_path / "_incoming"
    incoming.mkdir()
    (incoming / "catalog.json").write_text("{}", encoding="utf-8")
    assert memory_schema.incoming_complete(incoming) is False


def test_demo_incoming_is_complete() -> None:
    assert memory_schema.incoming_complete(INCOMING) is True


def test_secret_like_value_in_card_fails(tmp_path: Path) -> None:
    card = tmp_path / "user.md"
    card.write_text(
        "---\nslug: user\ntitle: User\nstatus: map\nsource: public\n"
        "fetched_at: 2026-08-13T17:00:00+03:00\nproduct: demo\n---\n\n"
        "token: sk-abc123secret\n",
        encoding="utf-8",
    )
    errors = memory_schema.validate_card(card)
    assert any("secret" in e.lower() for e in errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
python -m pytest tests/test_memory_schema.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'memory_schema'` (or collection error). Do not create `pyproject.toml` yet if pytest is missing — install pytest in the next implementation step after RED is confirmed. If pytest is not installed:

```powershell
python -m pip install pytest
python -m pytest tests/test_memory_schema.py -v
```

Expected still: FAIL, `memory_schema` not found.

- [ ] **Step 3: Write fixtures**

`fixtures/demo-catalog/incoming/catalog.json`:

```json
{
  "channel": "public",
  "fetched_at": "2026-08-13T17:00:00+03:00",
  "base_url": "https://api.demo.example",
  "resources": [
    {
      "path": "/users",
      "methods": ["GET"],
      "title": "User",
      "slug_hint": "user",
      "summary": "Account of a person in the demo product."
    },
    {
      "path": "/orders",
      "methods": ["GET", "POST"],
      "title": "Order",
      "slug_hint": "order",
      "summary": "Purchase made by a user."
    }
  ],
  "errors": [
    {
      "channel": "public",
      "code": "no-description",
      "message": "Payment resource has no description in the catalog."
    }
  ]
}
```

`fixtures/demo-catalog/incoming/MANIFEST.md`:

```markdown
# Hunter incoming manifest

- catalog.json
```

`fixtures/demo-catalog/expected/entities/user.md`:

```markdown
---
slug: user
title: User
status: map
source: public
fetched_at: 2026-08-13T17:00:00+03:00
product: demo
---

Account of a person in the demo product.

## Fields

Fields are not detailed on map status.

## Relations

None stated by the source.

## Missing

- Field list not fetched (map only).
```

`fixtures/demo-catalog/expected/entities/order.md`:

```markdown
---
slug: order
title: Order
status: map
source: public
fetched_at: 2026-08-13T17:00:00+03:00
product: demo
---

Purchase made by a user.

## Fields

Fields are not detailed on map status.

## Relations

None stated by the source.

## Missing

- Field list not fetched (map only).
```

`fixtures/demo-catalog/expected/catalog/api.md`:

```markdown
# API catalog

Fetched at: `2026-08-13T17:00:00+03:00`
Channel: `public`
Base URL: `https://api.demo.example`

| Resource | Methods | Channel | Entity | fetched_at |
|----------|---------|---------|--------|------------|
| `/users` | GET | public | [user](../entities/user.md) | 2026-08-13T17:00:00+03:00 |
| `/orders` | GET, POST | public | [order](../entities/order.md) | 2026-08-13T17:00:00+03:00 |
```

`fixtures/demo-catalog/expected/index.md`:

```markdown
# Demo product map

Last successful index-system: `2026-08-13T17:00:00+03:00`

## Entities

| Slug | Title | Status | Card |
|------|-------|--------|------|
| user | User | map | [user.md](entities/user.md) |
| order | Order | map | [order.md](entities/order.md) |
```

`fixtures/demo-catalog/expected/gaps.md`:

```markdown
# Gaps

| Missing | Tried | Next | Code | Date |
|---------|-------|------|------|------|
| Payment resource has no description in the catalog. | public | internal or browser | no-description | 2026-08-13 |
```

- [ ] **Step 4: Write minimal implementation**

Create `tools/memory_schema.py`:

```python
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
    r"(?i)(?:token|password|secret|api[_-]?key)\s*[:=]\s*(?:sk-|ghp_|xox[baprs]-|Bearer\s+)?\S+"
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
    return all((incoming_dir / name).is_file() for name in listed)


def _looks_like_secret(text: str) -> bool:
    for match in SECRET_RE.finditer(text):
        value = match.group(0).split(":", 1)[-1].split("=", 1)[-1].strip()
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
            datetime.fromisoformat(fetched)
        except ValueError:
            errors.append(f"{path}: fetched_at is not ISO-8601")
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
        if required.exists() is False:
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
```

Create `pyproject.toml`:

```toml
[project]
name = "qaswarm"
version = "0.1.0"
requires-python = ">=3.11"
description = "Cursor-native QA swarm kernel and product memory"

[project.optional-dependencies]
dev = ["pytest>=8.0", "ruff>=0.6"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[tool.ruff]
target-version = "py311"
line-length = 100
src = ["tools", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I"]
```

- [ ] **Step 5: Run tests to verify they pass**

```powershell
python -m pip install pytest ruff
python -m pytest tests/test_memory_schema.py -v
python -m ruff check tools tests
python tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: pytest all PASS; ruff no issues; CLI prints `OK` and exit 0.

- [ ] **Step 6: Commit**

```powershell
git add tools/memory_schema.py tests/conftest.py tests/test_memory_schema.py pyproject.toml fixtures/demo-catalog
git commit -m "Add memory schema checker and demo catalog fixtures."
```

If `git init` has not been run yet, run `git init` first, then the add/commit. Do not commit `.env` files.

---

### Task 2: Каркас репозитория (gitignore, шаблон продукта, память)

**Files:**
- Create: `.gitignore`
- Create: `docs/examples/product-config.yaml`
- Create: `products/README.md`
- Create: `memory/README.md`
- Test: `tests/test_memory_schema.py` (уже есть; каркас не ломает CLI)

**Interfaces:**
- Consumes: `validate_memory_tree`, product config field names from spec
- Produces: шаблон `docs/examples/product-config.yaml` с полями `id`, `name`, `public_api.base_url`, `public_api.catalog_hint`, `public_api.token_env`, `internal_api.base_url` (закомментирован), `mcp.browser`, `ttl_hours`

- [ ] **Step 1: Write `.gitignore`**

```gitignore
.env
**/.env
.venv/
__pycache__/
.pytest_cache/
.ruff_cache/
memory/*/raw/_incoming/
```

- [ ] **Step 2: Write product config template**

`docs/examples/product-config.yaml`:

```yaml
id: my-product
name: My Product
public_api:
  base_url: https://api.example.com
  catalog_hint: /openapi.json
  token_env: PUBLIC_API_TOKEN
# internal_api:
#   base_url: https://internal-api.example.com
#   token_env: INTERNAL_API_TOKEN
mcp:
  browser: false
ttl_hours: 168
```

`products/README.md`:

```markdown
# Product connection

v1: exactly one directory here, named `<product-id>` (`[a-z0-9-]+`).

1. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`.
2. Set `id` to the same folder name.
3. Put secrets in `products/<product-id>/.env` (gitignored) and/or Cursor MCP settings.
4. Never put tokens into `config.yaml` values or into `memory/`.

Zero product folders: coordinator must stop and ask for id + public API base URL.
More than one folder: coordinator must stop and ask which id.
```

`memory/README.md`:

```markdown
# Product memory

Canonical (answers to humans): `memory/<product-id>/index.md`, `catalog/api.md`, `entities/*.md`, `gaps.md`.

Hunter draft only: `memory/<product-id>/raw/_incoming/` plus `MANIFEST.md`. Incomplete incoming is not canonical.

Do not quote `raw/` in chat answers.
```

- [ ] **Step 3: Smoke-check schema CLI still passes**

```powershell
python tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: `OK`

- [ ] **Step 4: Commit**

```powershell
git add .gitignore docs/examples/product-config.yaml products/README.md memory/README.md
git commit -m "Add product connection template and memory layout docs."
```

---

### Task 3: Librarian subagent

**Files:**
- Create: `.cursor/agents/librarian.md`
- Create: `.cursor/rules/memory-card.mdc`
- Test: `python tools/memory_schema.py fixtures/demo-catalog/expected` (контракт, которому Librarian обязан соответствовать)

**Interfaces:**
- Consumes: incoming shape from Task 1 (`catalog.json` + `MANIFEST.md`); `validate_card` / `validate_memory_tree` rules
- Produces: Cursor subagent `name: librarian`. Writes only under `memory/<product-id>/` canonical paths. After success deletes processed files in `raw/_incoming/`. Never calls product HTTP/MCP.

- [ ] **Step 1: Write memory card rule**

`.cursor/rules/memory-card.mdc`:

```markdown
---
description: Canonical memory card schema for QA swarm
globs: memory/**/*.md
alwaysApply: false
---

# Memory cards

Entity files live in `memory/<product-id>/entities/<slug>.md`.

Required YAML frontmatter: `slug`, `title`, `status` (`map`|`deep`|`stale`), `source` (`public`|`internal`|`browser`), `fetched_at` (ISO-8601 with offset), `product`.

`slug` and filename stem must match `[a-z0-9-]+`.

No tokens, passwords, or raw Authorization values. If a secret appeared in source data, write that the field exists and the value is hidden.

Coordinator and Hunter must not edit these files. Only the `librarian` subagent writes them.

Validate with: `python tools/memory_schema.py memory/<product-id>`
```

- [ ] **Step 2: Write librarian agent**

`.cursor/agents/librarian.md`:

```markdown
---
name: librarian
description: Writes canonical QA swarm memory from Hunter incoming drafts. Enforces card schema, slug dedupe, and secret redaction. Never calls product APIs or browser MCP. Use after Hunter writes raw/_incoming/MANIFEST.md, and to set status stale before refresh.
---

You are the QA swarm Librarian. You are the only writer of canonical memory.

## When invoked

1. Read the written task (product-id, goal: index | merge-one | mark-stale, paths).
2. Read `products/<product-id>/config.yaml` only for `id` / `ttl_hours` / name. Do not use tokens.
3. Do not call HTTP, MCP, or the product.

## Canonical paths

- `memory/<product-id>/index.md`
- `memory/<product-id>/catalog/api.md`
- `memory/<product-id>/entities/<slug>.md`
- `memory/<product-id>/gaps.md`

## Incoming

Complete incoming = `memory/<product-id>/raw/_incoming/MANIFEST.md` listing files that exist (see `tools/memory_schema.py` `incoming_complete`). If incomplete: write nothing canonical; report failure.

Expected Hunter file: `_incoming/catalog.json` with `channel`, `fetched_at`, `base_url`, `resources[]` (`path`, `methods`, `title`, `slug_hint`, `summary`), `errors[]`.

## Card rules

Copy schema from `.cursor/rules/memory-card.mdc`. Status `map` for index-system entities. Status `deep` only when the task is a targeted fill and new detail was actually written. Never invent CRUD or fields the JSON did not contain.

Slug: lowercase `slug_hint` if it matches `[a-z0-9-]+`, else slugify title the same way. One slug one file. If the same entity already exists, merge into that file.

`index-system` must not downgrade existing `deep` cards to `map` and must not overwrite their body. Update catalog, index, new/map cards, and `gaps.md` only.

`mark-stale`: set `status: stale` on listed slugs (or all map cards if the task says refresh-all-map). Do not change `deep` unless the task lists those slugs or says including-deep.

After successful canonical write, delete processed files in `_incoming/` including `MANIFEST.md`.

Redact secrets. Prefer wording: field exists, value hidden.

Match the shape of `fixtures/demo-catalog/expected/` (structure and frontmatter, not the demo sentences).

Finally run `python tools/memory_schema.py memory/<product-id>` if that tree exists. If it prints errors, fix files before reporting success.
```

- [ ] **Step 3: Static verify**

```powershell
python tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: `OK`

Open `.cursor/agents/librarian.md` and confirm frontmatter `name: librarian` and the phrases: only writer, no HTTP/MCP, no deep overwrite on index-system, delete `_incoming` after success.

- [ ] **Step 4: Commit**

```powershell
git add .cursor/agents/librarian.md .cursor/rules/memory-card.mdc
git commit -m "Add librarian subagent and memory card rule."
```

---

### Task 4: Hunter subagent

**Files:**
- Create: `.cursor/agents/hunter.md`
- Test: no new pytest; hunter output must be valid incoming for Task 1 (`incoming_complete`)

**Interfaces:**
- Consumes: `products/<id>/config.yaml` fields from Task 2; catalog_hint fallback paths from Global Constraints
- Produces: Cursor subagent `name: hunter`. Writes only `memory/<id>/raw/_incoming/catalog.json` and `MANIFEST.md`. Does not write `index.md` / `entities/`.

- [ ] **Step 1: Write hunter agent**

`.cursor/agents/hunter.md`:

```markdown
---
name: hunter
description: Fetches product context for QA swarm memory. Uses public API, then internal API if configured and public was not enough, then browser MCP only on recall/refresh when APIs fail. Writes only memory/<id>/raw/_incoming/. Use when building a system map or filling one memory miss.
---

You are the QA swarm Hunter. You fetch. You do not write canonical memory.

## When invoked

Read the task: `product-id`, mode (`index-system` | `recall` | `refresh`), allowed channels, the single target for recall/refresh, what is already in memory.

If `memory/<product-id>/raw/_incoming/` is not empty: stop. Report lock busy. Do not write.

Read `products/<product-id>/config.yaml`. Do not guess base URL.

## Channels

Order: public API → internal API (only if `internal_api.base_url` is present) → browser MCP (only if allowed).

`index-system`: public, then internal if public did not yield a catalog or resource summaries. Browser is forbidden. Put UI gaps into `errors[]` in `catalog.json` instead.

`recall` / `refresh`: one target. Next channel only if the previous did not answer. Browser only if `mcp.browser` is true and APIs failed.

## Catalog discovery

Use `public_api.catalog_hint` relative to `public_api.base_url`. If `unknown`, try only:

- `/openapi.json`
- `/swagger.json`
- `/swagger/v1/swagger.json`
- `/api-docs`

Do not invent resources. Map only paths the catalog actually returned. Do not dump all records; this is a map: path, methods, title, short summary.

Call APIs with Cursor HTTP/MCP tools. There is no HTTP client in this repo. Use `token_env` names; never write token values into files.

## Output

Write:

- `memory/<product-id>/raw/_incoming/catalog.json` — same schema as `fixtures/demo-catalog/incoming/catalog.json`
- `memory/<product-id>/raw/_incoming/MANIFEST.md` listing `catalog.json`

On 401/unreachable public API: still write `catalog.json` with empty `resources` and an `errors[]` entry (`channel`, `code`, `message`). Still write MANIFEST so Librarian can record gaps. Do not switch to browser on `index-system`.

Do not edit `index.md`, `catalog/api.md`, `entities/`, or `gaps.md`.
```

- [ ] **Step 2: Verify incoming fixture still matches hunter schema**

```powershell
python -c "from pathlib import Path; import json, sys; sys.path.insert(0,'tools'); import memory_schema; d=json.loads(Path('fixtures/demo-catalog/incoming/catalog.json').read_text(encoding='utf-8')); assert {'channel','fetched_at','base_url','resources','errors'} <= set(d); assert memory_schema.incoming_complete(Path('fixtures/demo-catalog/incoming'))"
```

Expected: no assertion error, exit 0.

- [ ] **Step 3: Commit**

```powershell
git add .cursor/agents/hunter.md
git commit -m "Add hunter subagent for API ladder incoming drafts."
```

---

### Task 5: Координатор, AGENTS.md и три skills

**Files:**
- Create: `AGENTS.md`
- Create: `.cursor/rules/coordinator.mdc`
- Create: `.cursor/skills/index-system/SKILL.md`
- Create: `.cursor/skills/recall/SKILL.md`
- Create: `.cursor/skills/refresh/SKILL.md`
- Test: ручной чеклист в Step 4 (рантайм Cursor); схема не регрессирует

**Interfaces:**
- Consumes: subagents `hunter` and `librarian`; `is_fresh`; config template; lock on `_incoming/`
- Produces: coordinator behavior — read memory, never write `memory/`, launch one hunter then librarian with a written task containing `product-id`, goal, allowed channels, known cards, missing item

- [ ] **Step 1: Write coordinator rule**

`.cursor/rules/coordinator.mdc`:

```markdown
---
description: QA swarm coordinator routing and memory write ban
alwaysApply: true
---

# Coordinator

You are the only agent that talks to the human. You do not write files under `memory/`.

If `products/` has exactly one product directory, use that id. If zero, ask for id and public API base URL. If more than one, ask which id.

Answer product questions from `memory/<id>/index.md` and `entities/` with `source` and `fetched_at`. Do not quote `raw/`.

If a card is missing, `status` is `stale`, or `is_fresh(fetched_at, ttl_hours, now)` is false, launch `hunter` then `librarian`. One hunter at a time. If `raw/_incoming/` is not empty, do not launch another hunter.

Never say the system is remembered unless canonical files exist and `python tools/memory_schema.py memory/<id>` would pass.

Skills: `index-system`, `recall`, `refresh`. Subagents: `hunter`, `librarian`.
```

Keep this file under 50 lines as written above.

- [ ] **Step 2: Write AGENTS.md**

```markdown
# QA swarm

This workspace is the QA swarm kernel: remember an external product in git and answer from that memory.

## Roles

- You (this chat) are the coordinator. Follow `.cursor/rules/coordinator.mdc`.
- `hunter` fetches. Output only `memory/<id>/raw/_incoming/`.
- `librarian` writes canonical memory. Never calls the product.

## Do not do in v1

Test plans, tickets, Playwright/e2e, full API dumps, scheduled reindex, RAG, guessing product URLs.

## Spec

`docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
```

- [ ] **Step 3: Write the three skills**

`.cursor/skills/index-system/SKILL.md`:

```markdown
---
name: index-system
description: Builds a map of the external product (API catalog, short entity cards, gaps) into git memory. Use when the user says запомни систему, index the system, build the product map, or refresh the catalog of resources.
---

# index-system

## Steps

1. Resolve the single `product-id` under `products/`. If missing, stop and ask for `id` + `public_api.base_url`. Do not invent the host. Offer copying `docs/examples/product-config.yaml`.
2. If `memory/<id>/raw/_incoming/` is not empty, stop (lock).
3. Launch subagent `hunter` with written task: mode `index-system`, product-id, allowed channels public then internal if configured, browser forbidden.
4. After Hunter: `_incoming/MANIFEST.md` must exist. Launch `librarian` with goal `index`. Librarian must not downgrade `deep` cards.
5. Read `index.md` and `gaps.md`. Report entity count, gaps, file paths.
6. Forbidden success phrase if schema would fail: do not say the system is remembered. Run `python tools/memory_schema.py memory/<id>` or equivalent Read of frontmatter.

Map only: no record dumps, no browser crawl.
```

`.cursor/skills/recall/SKILL.md`:

```markdown
---
name: recall
description: Answers product questions from QA swarm git memory, citing source and fetched_at. Use when the user asks what an entity is, how the API works, or what the product contains. Fetches only on miss, stale, or expired TTL.
---

# recall

## Steps

1. Resolve `product-id`. Grep/Read `memory/<id>/index.md` and `entities/`.
2. Hit and fresh (`fetched_at` within `ttl_hours`, default 168): answer with source and date. Do not launch hunter. Do not write files.
3. Miss, `status: stale`, or expired TTL: if `_incoming/` not empty, stop. Else one `hunter` task with a single target and allowed ladder (browser only if `mcp.browser` is true and APIs fail). Then `librarian` merge (status `deep` if new detail). Then answer from the file.
4. If channels fail: say memory is missing or only old `fetched_at` exists; what to check in config. Do not present expired data as current.
5. Never quote secrets or `raw/`.
```

`.cursor/skills/refresh/SKILL.md`:

```markdown
---
name: refresh
description: Marks selected memory cards stale and re-fetches them into git. Use when the user says обнови, refresh X, or update the map. Deep cards update only if listed or the user said including deep.
---

# refresh

## Steps

1. Resolve `product-id` and the target: one slug, several slugs, or all map cards. `deep` only if listed or user said including deep.
2. If `_incoming/` not empty, stop.
3. Launch `librarian` with goal `mark-stale` and the slug list.
4. Launch `hunter` with mode `refresh` and the same targets. Browser only if `mcp.browser` is true and APIs fail. Then `librarian` merge.
5. Answer from updated canonical files with new `fetched_at`.
6. Refresh-all in v1 = re-run catalog + map cards (same as index-system plus stale mark on those map cards), not a silent wipe of `deep`.
```

- [ ] **Step 4: Lint + schema still pass**

```powershell
python -m ruff check tools tests
python -m pytest tests/test_memory_schema.py -v
python tools/memory_schema.py fixtures/demo-catalog/expected
```

Expected: ruff clean, tests PASS, `OK`.

Manual file check (no Cursor run yet): each skill `name` matches folder name; coordinator rule says coordinator does not write `memory/`; hunter/librarian names match AGENTS.md.

- [ ] **Step 5: Commit**

```powershell
git add AGENTS.md .cursor/rules/coordinator.mdc .cursor/skills/index-system/SKILL.md .cursor/skills/recall/SKILL.md .cursor/skills/refresh/SKILL.md
git commit -m "Add coordinator rules and index/recall/refresh skills."
```

---

### Task 6: README и приёмочный прогон

**Files:**
- Create: `README.md`
- Modify: none required in tests
- Test: три сценария из spec §12 (ручные); плюс pytest

**Interfaces:**
- Consumes: all previous files
- Produces: operator instructions to connect one product and run index / recall / miss

- [ ] **Step 1: Write README.md**

```markdown
# qaswarm

Cursor-native QA swarm kernel: map an external product into git memory and answer from that memory.

## What this is

Coordinator (this repo's chat) + `hunter` + `librarian`. Not a test runner. Not a ticket bot.

## Setup

1. Python 3.11+
2. `python -m pip install pytest ruff`
3. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`
4. Put API tokens in `products/<product-id>/.env` or Cursor MCP. Never commit them.
5. Open this folder as the Cursor workspace.

## Commands (natural language)

- «Запомни систему» → skill `index-system` (API map, not a data dump)
- A question about an entity → `recall`
- «Обнови user» → `refresh`

## Checks

```powershell
python -m pytest tests/test_memory_schema.py -v
python tools/memory_schema.py fixtures/demo-catalog/expected
python tools/memory_schema.py memory/<product-id>
```

## Acceptance (spec)

1. Map: after index, cards exist with `status: map`, `source`, `fetched_at`; no secrets; coordinator lists gaps.
2. Recall hit: second question about a known entity does not launch hunter; answer cites source and date.
3. Recall miss: one targeted fetch; one new/updated card; no second hunter while `_incoming/` is busy.

Spec: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
```

- [ ] **Step 2: Run automated checks**

```powershell
python -m pytest tests/test_memory_schema.py -v
python tools/memory_schema.py fixtures/demo-catalog/expected
python -m ruff check tools tests
```

Expected: PASS / `OK` / no ruff errors.

- [ ] **Step 3: Commit**

```powershell
git add README.md
git commit -m "Document QA swarm setup and acceptance checks."
```

- [ ] **Step 4: Human acceptance against the real public API**

Do this in Cursor after the files exist (not in pytest):

1. Create `products/<id>/config.yaml` and `.env`.
2. Ask: запомни систему. Expect map files; run `python tools/memory_schema.py memory/<id>` → `OK`.
3. Ask about an indexed entity. Expect citation, no new hunter.
4. Ask about something absent. Expect one hunter+librarian pass and a new/updated card.

If schema CLI fails, the run fails even if the chat text looks good.

---

## Self-review (spec coverage)

| Spec section | Task |
|--------------|------|
| §2 цели, ответы из памяти | 5 (recall), 6 |
| §3 / §13 вне скоупа | AGENTS.md + coordinator + README |
| §5 роли и шина файлов | 3, 4, 5 |
| §6 дерево репо | 2, 5 |
| §7 config, один продукт, token_env | 2, 5 |
| §8 контракт карточек, deep preserve, MANIFEST | 1, 3 |
| §9 skills names | 5 |
| §10 потоки index/recall/refresh, lock | 4, 5 |
| §11 ошибки 401, secrets, no manifest | 4, 3, 5 |
| §12 фикстуры и три сценария | 1, 6 |
| §14 без HTTP-клиента/БД | весь план; только `tools/memory_schema.py` как валидатор |

Placeholders: none. Types: `validate_card` / `incoming_complete` / `is_fresh` names are stable across tasks. Hunter JSON fields are identical in Task 1 fixture, Task 4 prompt, Task 3 librarian prompt.
