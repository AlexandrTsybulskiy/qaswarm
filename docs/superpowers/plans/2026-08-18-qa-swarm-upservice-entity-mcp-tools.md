# Upservice MCP entity GET/list tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add named public GET MCP tools for Upservice entities (get-by-id where the catalog has it, plus list) so Hunter does not invent those URLs.

**Architecture:** Extract `public_get` and `merge_list_query` in `tools/upservice_mcp/client.py`. Thin `get_*` / `list_*` functions share config, token, 429 retry, and `{status_code, body}`. `server.py` registers FastMCP wrappers. `get_task` keeps its external contract.

**Tech Stack:** Python 3.11+ stdlib (`urllib`, `json`, `re`), package `mcp` (FastMCP), pytest, ruff. Host CLI: `py -3`.

## Global Constraints

- Named tools only (not `get_resource`); HTTP is GET only; paths have no trailing slash.
- Return shape is always `{status_code: int, body: object|str}`; the tool writes no files.
- Token values never appear in `body`, logs, git, or incoming JSON; env name `UPSERVICE_PUBLIC_API_TOKEN` is allowed.
- Token source: `os.environ[token_env]` then `products/upservice/.env`.
- Config from `products/upservice/config.yaml` (`public_api.base_url`, `public_api.token_env`); v1 product id must be `upservice`.
- 429 retries only (not 401/404/5xx/`status_code: 0`); max 6 GETs per tool call; wait `Retry-After` or 1→2→4→8→16s, cap 30s; GET timeout 30s.
- List tools: optional `limit`, `offset`, and `query` dict; argument `limit`/`offset` override same keys in `query`.
- No POST/PUT/PATCH/DELETE; no channels/files/external-channels; no `get_employee` / `get_tag`.
- No PyYAML and no httpx; do not import `upservice-personal-assistant`.
- Do not change `tools/memory_schema.py`, the `task.json` contract, or `docs/examples/mcp.json`.
- Host CLI: `py -3`, not `python`.
- Coordinator does not write `memory/`. Agents do not write to Upservice.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/upservice_mcp/client.py` | `public_get`, `merge_list_query`, `get_*`, `list_*` |
| `tools/upservice_mcp/server.py` | FastMCP wrappers for every tool in spec §6.1 |
| `tests/test_get_task_mcp.py` | Unchanged `get_task` contract (must stay green) |
| `tests/test_entity_mcp.py` | New entity tools, query merge, URL checks |
| `.cursor/agents/hunter.md` | Named tools; do not construct those URLs |
| `.cursor/rules/coordinator.mdc` | Missing entity tool → mcp.json, no guessed URL |
| `AGENTS.md`, `README.md` | Spec link; pytest includes `test_entity_mcp.py` |
| `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md` | HTTP-client exception covers all GET MCP tools |

Shared keyword args on every client fetch function (do not rename):

```python
*,
products_root: Path,
environ: Mapping[str, str] | None = None,
http_get: HttpGet | None = None,
sleep: Callable[[float], None] | None = None,
now: Callable[[], datetime] | None = None,
```

---

### Task 1: Extract `public_get` and keep `get_task`

**Files:**
- Modify: `tools/upservice_mcp/client.py`
- Modify: `tests/test_get_task_mcp.py`
- Test: `tests/test_get_task_mcp.py`

**Interfaces:**
- Consumes: existing `get_task` HTTP loop, config, token, 429 retry
- Produces:
  - `PATH_FORBIDDEN = frozenset("?# ")` (or equivalent checks)
  - `public_get(path: str, *, products_root: Path, query: Mapping[str, object] | None = None, environ: Mapping[str, str] | None = None, http_get: HttpGet | None = None, sleep: Callable[[float], None] | None = None, now: Callable[[], datetime] | None = None) -> dict[str, object]`
  - `_get_by_id(path_prefix: str, id_name: str, raw_id: str | int, *, products_root: Path, environ=..., http_get=..., sleep=..., now=...) -> dict[str, object]`
  - `get_task(...)` unchanged signature; implementation calls `_get_by_id("/v1/tasks", "task_id", task_id, ...)`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_get_task_mcp.py`:

```python
def test_public_get_rejects_query_in_path(tmp_path: Path) -> None:
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.public_get(
        "/v1/tasks/1?x=1",
        products_root=tmp_path,
        environ={},
        http_get=http_get,
    )
    assert result["status_code"] == 0
    body = result["body"]
    assert isinstance(body, dict)
    assert body.get("error") == "invalid path"
    assert called["n"] == 0


def test_public_get_rejects_dotdot(tmp_path: Path) -> None:
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.public_get(
        "/v1/../secret",
        products_root=tmp_path,
        environ={},
        http_get=http_get,
    )
    assert result["status_code"] == 0
    assert called["n"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_get_task_mcp.py::test_public_get_rejects_query_in_path tests/test_get_task_mcp.py::test_public_get_rejects_dotdot -v`

Expected: FAIL with `AttributeError: module 'upservice_mcp.client' has no attribute 'public_get'`

- [ ] **Step 3: Implement `public_get` and slim `get_task`**

In `tools/upservice_mcp/client.py` add `import urllib.parse` next to the other `urllib` imports.

Replace `get_task` with these three functions (keep every helper above `_error` / `parse_retry_after` unchanged):

```python
def _valid_public_path(path: str) -> bool:
    if not path.startswith("/v1/"):
        return False
    if ".." in path:
        return False
    if any(ch in path for ch in "?# "):
        return False
    return True


def public_get(
    path: str,
    *,
    products_root: Path,
    query: Mapping[str, object] | None = None,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    if not _valid_public_path(path):
        return _error(0, "invalid path")

    env = dict(environ) if environ is not None else dict(__import__("os").environ)
    if not products_root.is_dir():
        return _error(0, "missing product config")
    dirs = [p for p in products_root.iterdir() if p.is_dir()]
    if len(dirs) != 1 or dirs[0].name != "upservice":
        return _error(0, "product must be upservice")
    product_dir = dirs[0]
    config_path = product_dir / "config.yaml"
    if not config_path.is_file():
        return _error(0, "missing product config")
    parsed = parse_product_yaml(config_path.read_text(encoding="utf-8"))
    if parsed.get("id") != "upservice":
        return _error(0, "product must be upservice")
    public = parsed.get("public_api")
    if not isinstance(public, dict):
        return _error(0, "missing public_api")
    base_url = str(public.get("base_url", "")).rstrip("/")
    token_env = str(public.get("token_env", "")).strip()
    if not base_url or not token_env:
        return _error(0, "missing public_api")

    token = load_token(token_env, product_dir / ".env", env)
    if not token:
        return _error(401, "missing token")

    getter = http_get or urllib_get
    sleeper = sleep or __import__("time").sleep
    clock = now or (lambda: datetime.now(timezone.utc))
    url = f"{base_url}{path}"
    if query:
        encoded = urllib.parse.urlencode(query, doseq=True)
        if encoded:
            url = f"{url}?{encoded}"
    headers = {"Authorization": authorization_header(token), "Accept": "application/json"}
    last_status = 0
    last_text = ""
    wait_index = 0
    for attempt in range(MAX_ATTEMPTS):
        last_status, last_text, resp_headers = getter(url, headers, GET_TIMEOUT)
        if last_status != 429:
            break
        if attempt == MAX_ATTEMPTS - 1:
            break
        header_val = None
        for key, val in resp_headers.items():
            if key.lower() == "retry-after":
                header_val = val
                break
        wait = parse_retry_after(header_val, now=clock())
        if wait is None:
            wait = backoff_seconds(wait_index)
            wait_index += 1
        else:
            wait = min(wait, MAX_WAIT)
            wait_index += 1
        sleeper(wait)
    if last_status == 0:
        result = _error(0, last_text or "request failed")
    else:
        result = {"status_code": last_status, "body": _normalize_body(_decode_body(last_text))}
    body = result["body"]
    if not isinstance(body, (dict, str)):
        body = _normalize_body(body)
    result = dict(result)
    result["body"] = _redact_token_in_body(body, token)
    return result


def _get_by_id(
    path_prefix: str,
    id_name: str,
    raw_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    raw_text = str(raw_id)
    if "/" in raw_text:
        return _error(0, f"invalid {id_name}")
    normalized = normalize_task_id(raw_id)
    if not normalized or "/" in normalized:
        return _error(0, f"invalid {id_name}")
    return public_get(
        f"{path_prefix}/{normalized}",
        products_root=products_root,
        query=None,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def get_task(
    task_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _get_by_id(
        "/v1/tasks",
        "task_id",
        task_id,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_get_task_mcp.py -v`

Expected: PASS, including `test_get_task_200_raw_body_no_token_leak` URL `https://public.upservice.io/v1/tasks/1` with no query string.

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/client.py tests/test_get_task_mcp.py
git commit -m "refactor: share Upservice public GET helper for MCP tools"
```

---

### Task 2: `merge_list_query`

**Files:**
- Modify: `tools/upservice_mcp/client.py`
- Create: `tests/test_entity_mcp.py`
- Test: `tests/test_entity_mcp.py`

**Interfaces:**
- Consumes: nothing from later tasks
- Produces:
  - `QUERY_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")`
  - `merge_list_query(limit: int | None = None, offset: int | None = None, query: Mapping[str, object] | None = None) -> dict[str, str | list[str]] | None`
  - `None` means invalid (`invalid query`). `{}` means valid empty (no `?` on the URL).
  - `bool` encodes as `true` / `false`. `int` (not `bool`) encodes with `str()`. `None` values skipped. Empty lists omitted. Argument `limit`/`offset` overwrite keys in `query`. Negative or non-int `limit`/`offset` → `None`. Non-dict `query` (when not `None`) → `None`. Nested dict values → `None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_entity_mcp.py`:

```python
from __future__ import annotations

from upservice_mcp import client as utc


def test_merge_list_query_empty() -> None:
    assert utc.merge_list_query() == {}


def test_merge_list_query_limit_offset() -> None:
    assert utc.merge_list_query(limit=25, offset=0) == {"limit": "25", "offset": "0"}


def test_merge_list_query_repeated_lists() -> None:
    merged = utc.merge_list_query(
        limit=25,
        query={"status": ["active", "completed"], "tags_ids": ["a", "b"]},
    )
    assert merged == {
        "status": ["active", "completed"],
        "tags_ids": ["a", "b"],
        "limit": "25",
    }


def test_merge_list_query_arg_limit_overrides_query() -> None:
    merged = utc.merge_list_query(limit=25, query={"status": "active", "limit": 10})
    assert merged is not None
    assert merged["limit"] == "25"
    assert merged["status"] == "active"


def test_merge_list_query_bool_and_skip_none() -> None:
    merged = utc.merge_list_query(query={"is_lag": True, "unused": None})
    assert merged == {"is_lag": "true"}


def test_merge_list_query_empty_list_omitted() -> None:
    assert utc.merge_list_query(query={"status": []}) == {}


def test_merge_list_query_invalid_key() -> None:
    assert utc.merge_list_query(query={"a/b": "x"}) is None


def test_merge_list_query_nested_dict_invalid() -> None:
    assert utc.merge_list_query(query={"filters": {"status": "active"}}) is None


def test_merge_list_query_query_not_dict() -> None:
    assert utc.merge_list_query(query=["status"]) is None  # type: ignore[arg-type]


def test_merge_list_query_negative_limit() -> None:
    assert utc.merge_list_query(limit=-1) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_entity_mcp.py -v`

Expected: FAIL with `AttributeError: module 'upservice_mcp.client' has no attribute 'merge_list_query'`

- [ ] **Step 3: Implement `merge_list_query`**

Add to `tools/upservice_mcp/client.py` next to `ID_RE`:

```python
QUERY_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
```

Add after `_error`:

```python
def _encode_query_scalar(value: object) -> tuple[str | None, bool]:
    if value is None:
        return None, True
    if isinstance(value, bool):
        return ("true" if value else "false"), True
    if isinstance(value, int):
        return str(value), True
    if isinstance(value, str):
        return value, True
    return None, False


def merge_list_query(
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
) -> dict[str, str | list[str]] | None:
    if limit is not None and (isinstance(limit, bool) or not isinstance(limit, int) or limit < 0):
        return None
    if offset is not None and (isinstance(offset, bool) or not isinstance(offset, int) or offset < 0):
        return None
    merged: dict[str, str | list[str]] = {}
    if query is not None:
        if not isinstance(query, dict):
            return None
        for key, raw in query.items():
            if not isinstance(key, str) or not QUERY_KEY_RE.fullmatch(key):
                return None
            if isinstance(raw, (list, tuple)):
                encoded_items: list[str] = []
                for item in raw:
                    encoded, ok = _encode_query_scalar(item)
                    if not ok:
                        return None
                    if encoded is None:
                        continue
                    encoded_items.append(encoded)
                if encoded_items:
                    merged[key] = encoded_items
                continue
            encoded, ok = _encode_query_scalar(raw)
            if not ok:
                return None
            if encoded is None:
                continue
            merged[key] = encoded
    if limit is not None:
        merged["limit"] = str(limit)
    if offset is not None:
        merged["offset"] = str(offset)
    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_entity_mcp.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/client.py tests/test_entity_mcp.py
git commit -m "feat: encode Upservice list MCP query params"
```

---

### Task 3: `get_project`, `get_sprint`, `get_directory`, `get_directory_record`

**Files:**
- Modify: `tools/upservice_mcp/client.py`
- Modify: `tests/test_entity_mcp.py`
- Test: `tests/test_entity_mcp.py`

**Interfaces:**
- Consumes: `_get_by_id`, `public_get` from Task 1
- Produces:
  - `get_project(project_id: str | int, *, products_root: Path, environ=..., http_get=..., sleep=..., now=...) -> dict[str, object]` → GET `/v1/projects/{id}`
  - `get_sprint(sprint_id: str | int, *, ...)` → GET `/v1/sprints/{id}`
  - `get_directory(directory_id: str | int, *, ...)` → GET `/v1/directories/{id}`
  - `get_directory_record(record_id: str | int, *, ...)` → GET `/v1/directory-records/{id}`

- [ ] **Step 1: Write the failing tests**

At the top of `tests/test_entity_mcp.py`, add:

```python
import json
from pathlib import Path

import pytest
```

After the `utc` import, add:

```python
CONFIG = """id: upservice
name: Upservice
public_api:
  base_url: https://public.upservice.io/
  catalog_hint: /openapi.json
  token_env: UPSERVICE_PUBLIC_API_TOKEN
mcp:
  browser: false
ttl_hours: 168
"""

TOKEN = "secret-token-xyz"


def _product_root(tmp_path: Path, config: str = CONFIG, env: str | None = None) -> Path:
    products = tmp_path / "products"
    folder = products / "upservice"
    folder.mkdir(parents=True)
    (folder / "config.yaml").write_text(config, encoding="utf-8")
    if env is not None:
        (folder / ".env").write_text(env, encoding="utf-8")
    return products
```

Append:

```python
GET_BY_ID = (
    ("get_project", "7", "https://public.upservice.io/v1/projects/7"),
    ("get_sprint", "3", "https://public.upservice.io/v1/sprints/3"),
    ("get_directory", "2", "https://public.upservice.io/v1/directories/2"),
    ("get_directory_record", "9", "https://public.upservice.io/v1/directory-records/9"),
)


@pytest.mark.parametrize("fn_name, raw_id, url", GET_BY_ID)
def test_get_by_id_hits_catalog_path(tmp_path: Path, fn_name: str, raw_id: str, url: str) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def http_get(got: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(got)
        return 200, json.dumps({"id": int(raw_id)}), {}

    fn = getattr(utc, fn_name)
    result = fn(raw_id, products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert result["body"] == {"id": int(raw_id)}
    assert TOKEN not in json.dumps(result)
    assert calls == [url]


def test_get_project_rejects_slash_id(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.get_project("../x", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 0
    assert called["n"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_entity_mcp.py::test_get_by_id_hits_catalog_path tests/test_entity_mcp.py::test_get_project_rejects_slash_id -v`

Expected: FAIL with `AttributeError` for `get_project` (or the first missing name).

- [ ] **Step 3: Implement get-by-id functions**

Append to `tools/upservice_mcp/client.py` after `get_task`:

```python
def get_project(
    project_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _get_by_id(
        "/v1/projects",
        "project_id",
        project_id,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def get_sprint(
    sprint_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _get_by_id(
        "/v1/sprints",
        "sprint_id",
        sprint_id,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def get_directory(
    directory_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _get_by_id(
        "/v1/directories",
        "directory_id",
        directory_id,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def get_directory_record(
    record_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _get_by_id(
        "/v1/directory-records",
        "record_id",
        record_id,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_entity_mcp.py tests/test_get_task_mcp.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/client.py tests/test_entity_mcp.py
git commit -m "feat: add Upservice MCP get-by-id for catalog entities"
```

---

### Task 4: list tools

**Files:**
- Modify: `tools/upservice_mcp/client.py`
- Modify: `tests/test_entity_mcp.py`
- Test: `tests/test_entity_mcp.py`

**Interfaces:**
- Consumes: `merge_list_query` from Task 2, `public_get` from Task 1
- Produces:
  - `_list_collection(path: str, *, limit: int | None, offset: int | None, query: Mapping[str, object] | None, products_root: Path, environ=..., http_get=..., sleep=..., now=...) -> dict[str, object]`
  - Invalid merge → `{status_code: 0, body: {error: "invalid query"}}` and **zero** HTTP calls (do not load token if you already returned; not loading config is allowed).
  - `list_tasks`, `list_projects`, `list_sprints`, `list_employees`, `list_tags`, `list_directories`, `list_directory_records`
  - Each: `(*, limit: int | None = None, offset: int | None = None, query: Mapping[str, object] | None = None, products_root: Path, environ=..., http_get=..., sleep=..., now=...) -> dict[str, object]`
  - Paths: `/v1/tasks`, `/v1/projects`, `/v1/sprints`, `/v1/employees`, `/v1/tags`, `/v1/directories`, `/v1/directory-records`

- [ ] **Step 1: Write the failing tests**

At the top of `tests/test_entity_mcp.py`, add `from urllib.parse import parse_qs, urlparse`.

Append:

```python
LIST_PATHS = (
    ("list_tasks", "/v1/tasks"),
    ("list_projects", "/v1/projects"),
    ("list_sprints", "/v1/sprints"),
    ("list_employees", "/v1/employees"),
    ("list_tags", "/v1/tags"),
    ("list_directories", "/v1/directories"),
    ("list_directory_records", "/v1/directory-records"),
)


@pytest.mark.parametrize("fn_name, path", LIST_PATHS)
def test_list_without_args_has_no_query(tmp_path: Path, fn_name: str, path: str) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(url)
        return 200, json.dumps({"count": 0, "results": []}), {}

    fn = getattr(utc, fn_name)
    result = fn(products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert TOKEN not in json.dumps(result)
    assert calls == [f"https://public.upservice.io{path}"]


def test_list_projects_encodes_repeated_query(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(url)
        return 200, json.dumps({"count": 0, "results": []}), {}

    result = utc.list_projects(
        limit=25,
        offset=0,
        query={"status": ["active", "completed"], "tags_ids": ["a", "b"]},
        products_root=products,
        environ={},
        http_get=http_get,
    )
    assert result["status_code"] == 200
    parsed = urlparse(calls[0])
    assert parsed.path == "/v1/projects"
    qs = parse_qs(parsed.query)
    assert qs["status"] == ["active", "completed"]
    assert qs["tags_ids"] == ["a", "b"]
    assert qs["limit"] == ["25"]
    assert qs["offset"] == ["0"]


def test_list_projects_limit_arg_overrides_query(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(url)
        return 200, "{}", {}

    utc.list_projects(
        limit=25,
        query={"status": "active", "limit": 10},
        products_root=products,
        environ={},
        http_get=http_get,
    )
    qs = parse_qs(urlparse(calls[0]).query)
    assert qs["limit"] == ["25"]
    assert qs["status"] == ["active"]


def test_list_projects_invalid_query_skips_http(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    slash_key = utc.list_projects(
        query={"a/b": "x"},
        products_root=products,
        environ={},
        http_get=http_get,
    )
    nested = utc.list_projects(
        query={"filters": {"status": "active"}},
        products_root=products,
        environ={},
        http_get=http_get,
    )
    assert slash_key["status_code"] == 0
    assert nested["status_code"] == 0
    assert called["n"] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_entity_mcp.py::test_list_without_args_has_no_query tests/test_entity_mcp.py::test_list_projects_encodes_repeated_query -v`

Expected: FAIL with `AttributeError` for `list_tasks` or `list_projects`.

- [ ] **Step 3: Implement list functions**

Append to `tools/upservice_mcp/client.py`:

```python
def _list_collection(
    path: str,
    *,
    limit: int | None,
    offset: int | None,
    query: Mapping[str, object] | None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    merged = merge_list_query(limit=limit, offset=offset, query=query)
    if merged is None:
        return _error(0, "invalid query")
    return public_get(
        path,
        products_root=products_root,
        query=merged,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_tasks(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/tasks",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_projects(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/projects",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_sprints(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/sprints",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_employees(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/employees",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_tags(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/tags",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_directories(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/directories",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )


def list_directory_records(
    *,
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    return _list_collection(
        "/v1/directory-records",
        limit=limit,
        offset=offset,
        query=query,
        products_root=products_root,
        environ=environ,
        http_get=http_get,
        sleep=sleep,
        now=now,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_entity_mcp.py tests/test_get_task_mcp.py -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/client.py tests/test_entity_mcp.py
git commit -m "feat: add Upservice MCP list tools for catalog collections"
```

---

### Task 5: FastMCP wrappers

**Files:**
- Modify: `tools/upservice_mcp/server.py`
- Modify: `tests/test_entity_mcp.py`
- Test: `tests/test_entity_mcp.py`

**Interfaces:**
- Consumes: client functions from Tasks 3–4
- Produces FastMCP tools (same names) that pass `products_root=REPO_ROOT / "products"`:
  - `get_task(task_id: str | int) -> dict` (already present; do not rename)
  - `get_project(project_id: str | int) -> dict`
  - `get_sprint(sprint_id: str | int) -> dict`
  - `get_directory(directory_id: str | int) -> dict`
  - `get_directory_record(record_id: str | int) -> dict`
  - `list_tasks(limit: int | None = None, offset: int | None = None, query: dict | None = None) -> dict`
  - `list_projects`, `list_sprints`, `list_employees`, `list_tags`, `list_directories`, `list_directory_records` with the same list signature
  - Docstring of each tool includes `Call this instead of constructing GET …`

- [ ] **Step 1: Write the failing tests**

At the top of `tests/test_entity_mcp.py`, add `from typing import get_type_hints` and `from upservice_mcp import server as ums`.

Append to `tests/test_entity_mcp.py`:

```python
def test_server_get_project_uses_repo_products(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_get_project(
        project_id: str | int, *, products_root: Path, **kwargs: object
    ) -> dict[str, object]:
        seen["project_id"] = project_id
        seen["products_root"] = products_root
        return {"status_code": 200, "body": {"id": int(project_id)}}

    monkeypatch.setattr(ums.client, "get_project", fake_get_project)
    result = ums.get_project("12")
    assert result == {"status_code": 200, "body": {"id": 12}}
    assert seen["project_id"] == "12"
    assert seen["products_root"] == ums.REPO_ROOT / "products"
    assert get_type_hints(ums.get_project)["project_id"] == str | int


def test_server_list_projects_passes_query(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_list_projects(
        *,
        limit: int | None = None,
        offset: int | None = None,
        query: dict | None = None,
        products_root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        seen["limit"] = limit
        seen["offset"] = offset
        seen["query"] = query
        seen["products_root"] = products_root
        return {"status_code": 200, "body": {"count": 0, "results": []}}

    monkeypatch.setattr(ums.client, "list_projects", fake_list_projects)
    result = ums.list_projects(limit=25, offset=0, query={"status": "active"})
    assert result["status_code"] == 200
    assert seen["limit"] == 25
    assert seen["offset"] == 0
    assert seen["query"] == {"status": "active"}
    assert seen["products_root"] == ums.REPO_ROOT / "products"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_entity_mcp.py::test_server_get_project_uses_repo_products tests/test_entity_mcp.py::test_server_list_projects_passes_query -v`

Expected: FAIL with `AttributeError: module 'upservice_mcp.server' has no attribute 'get_project'`

- [ ] **Step 3: Register tools in `server.py`**

Replace `tools/upservice_mcp/server.py` with:

```python
from __future__ import annotations

import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

TOOLS_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from upservice_mcp import client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("upservice")


@mcp.tool()
def get_task(task_id: str | int) -> dict:
    """Fetch one Upservice task by id from the public API.

    Call this instead of constructing GET /v1/tasks/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_task(task_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_project(project_id: str | int) -> dict:
    """Fetch one Upservice project by id from the public API.

    Call this instead of constructing GET /v1/projects/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_project(project_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_sprint(sprint_id: str | int) -> dict:
    """Fetch one Upservice sprint by id from the public API.

    Call this instead of constructing GET /v1/sprints/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_sprint(sprint_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_directory(directory_id: str | int) -> dict:
    """Fetch one Upservice directory by id from the public API.

    Call this instead of constructing GET /v1/directories/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_directory(directory_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_directory_record(record_id: str | int) -> dict:
    """Fetch one Upservice directory record by id from the public API.

    Call this instead of constructing GET /v1/directory-records/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_directory_record(record_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def list_tasks(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice tasks from the public API.

    Call this instead of constructing GET /v1/tasks.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_tasks(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_projects(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice projects from the public API.

    Call this instead of constructing GET /v1/projects.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_projects(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_sprints(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice sprints from the public API.

    Call this instead of constructing GET /v1/sprints.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_sprints(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_employees(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice employees from the public API.

    Call this instead of constructing GET /v1/employees.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_employees(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_tags(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice tags from the public API.

    Call this instead of constructing GET /v1/tags.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_tags(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_directories(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice directories from the public API.

    Call this instead of constructing GET /v1/directories.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_directories(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_directory_records(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice directory records from the public API.

    Call this instead of constructing GET /v1/directory-records.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_directory_records(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


if __name__ == "__main__":
    mcp.run()
```

If `@mcp.tool()` fails on this `mcp` version, use `@mcp.tool` without `()` — keep the function names.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_entity_mcp.py tests/test_get_task_mcp.py -v`

Expected: PASS, including `test_server_get_task_uses_repo_products` and `test_server_script_imports_without_tools_on_sys_path`.

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/server.py tests/test_entity_mcp.py
git commit -m "feat: expose Upservice entity GET/list tools on MCP stdio"
```

---

### Task 6: Hunter, coordinator, and spec links

**Files:**
- Modify: `.cursor/agents/hunter.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Test: `tests/test_entity_mcp.py`, `tests/test_get_task_mcp.py` (no new tests required)

**Interfaces:**
- Consumes: tool names from Task 5
- Produces: hunter must call named tools for spec §6.1 paths; missing tool → mcp.json, do not guess URL; `index-system` OpenAPI unchanged; kernel HTTP-client exception covers all GET tools in `tools/upservice_mcp/`

- [ ] **Step 1: Update hunter**

In `.cursor/agents/hunter.md` replace:

```text
Call APIs with Cursor HTTP/MCP tools. The only HTTP client in this repo is GET inside `tools/upservice_mcp/` for the `get_task` MCP tool. Use `token_env` names; never write token values into files.
```

with:

```text
Call APIs with Cursor HTTP/MCP tools. The only HTTP client in this repo is GET inside `tools/upservice_mcp/` for the public GET MCP tools. Use `token_env` names; never write token values into files.

For public GET of these paths, call the named MCP tool. Do not construct the URL:

- GET `/v1/tasks/{id}` → `get_task`
- GET `/v1/projects/{id}` → `get_project`
- GET `/v1/sprints/{id}` → `get_sprint`
- GET `/v1/directories/{id}` → `get_directory`
- GET `/v1/directory-records/{id}` → `get_directory_record`
- GET `/v1/tasks` → `list_tasks`
- GET `/v1/projects` → `list_projects`
- GET `/v1/sprints` → `list_sprints`
- GET `/v1/employees` → `list_employees`
- GET `/v1/tags` → `list_tags`
- GET `/v1/directories` → `list_directories`
- GET `/v1/directory-records` → `list_directory_records`

If that tool is not in the available MCP tool list: do not guess the public path. Report that Cursor must copy `docs/examples/mcp.json` into `.cursor/mcp.json` and reload MCP. Do not stop `index-system` catalog discovery via `catalog_hint` / OpenAPI.

If the tool returns `status_code` 429: call it again with the same arguments, up to two more times (three tool calls max). 429 is not "missing".

There is no `get_employee` or `get_tag`. There are no MCP tools for channels, files, or external-channels.
```

Leave the `kind: task` / `get_task` section unchanged.

- [ ] **Step 2: Update coordinator**

In `.cursor/rules/coordinator.mdc` replace:

```text
If Hunter reports the MCP tool `get_task` is missing: do not launch a second hunter and do not tell it to guess `/v1/tasks/{id}`. Tell the human to copy `docs/examples/mcp.json` into `.cursor/mcp.json` and reload MCP. Token stays in `products/upservice/.env`.
```

with:

```text
If Hunter reports the MCP tool `get_task` or another Upservice entity GET/list tool (`get_project`, `get_sprint`, `get_directory`, `get_directory_record`, `list_tasks`, `list_projects`, `list_sprints`, `list_employees`, `list_tags`, `list_directories`, `list_directory_records`) is missing: do not launch a second hunter and do not tell it to guess the public URL. Tell the human to copy `docs/examples/mcp.json` into `.cursor/mcp.json` and reload MCP. Token stays in `products/upservice/.env`. Do not stop `index-system` OpenAPI catalog discovery.
```

- [ ] **Step 3: Update kernel spec, AGENTS, README**

In `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md` replace:

```text
Hunter ходит в public/internal API инструментами Cursor (HTTP и/или MCP из конфига Cursor). Отдельный HTTP-клиент в репозитории запрещён, кроме GET внутри `tools/upservice_mcp/` для MCP-тула `get_task`.
```

with:

```text
Hunter ходит в public/internal API инструментами Cursor (HTTP и/или MCP из конфига Cursor). Отдельный HTTP-клиент в репозитории запрещён, кроме GET внутри `tools/upservice_mcp/` для публичных GET MCP-тулов.
```

In `AGENTS.md` Spec list, append:

```text
`docs/superpowers/specs/2026-08-18-qa-swarm-upservice-entity-mcp-tools-design.md`
```

In `README.md`:

- Setup step 7: change `so Hunter can call `get_task`` to `so Hunter can call Upservice GET MCP tools (`get_task`, `get_project`, `list_employees`, …)`.
- Checks pytest line: add `tests/test_entity_mcp.py` after `tests/test_get_task_mcp.py`.
- After the get_task spec link, add: `Upservice entity GET/list MCP spec: `docs/superpowers/specs/2026-08-18-qa-swarm-upservice-entity-mcp-tools-design.md``

Do not edit `docs/examples/mcp.json`.

- [ ] **Step 4: Run the full MCP test set and ruff**

Run:

```powershell
py -3 -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py tests/test_get_task_mcp.py tests/test_entity_mcp.py -v
py -3 -m ruff check tools/upservice_mcp tests/test_entity_mcp.py tests/test_get_task_mcp.py
```

Expected: pytest PASS; ruff exit 0.

Confirm by reading:

- `.cursor/agents/hunter.md` contains `get_project` and `Do not construct the URL`
- `.cursor/rules/coordinator.mdc` contains `list_employees` and `docs/examples/mcp.json`
- `kind: task` still says `call MCP tool get_task`

- [ ] **Step 5: Commit**

```bash
git add .cursor/agents/hunter.md .cursor/rules/coordinator.mdc docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md AGENTS.md README.md
git commit -m "docs: route Hunter public entity GET through named MCP tools"
```

---

## Spec coverage (self-review)

| Spec requirement | Task |
|------------------|------|
| `public_get`, path guard, `get_task` on helper | 1 |
| `merge_list_query`, limit/offset override, invalid query | 2 |
| get-by-id tools and URLs from §6.1 | 3 |
| list tools, repeated query, no `?` without args, token redact | 4 |
| FastMCP wrappers, `get_project` products_root | 5 |
| Hunter/coordinator/kernel/AGENTS/README; no mcp.json change | 6 |
| 429 / redact / config still via `public_get` | 1 (existing `test_get_task_mcp.py`) |
| No write tools, no channels/files, no `get_employee`/`get_tag` | constraints; not implemented |
