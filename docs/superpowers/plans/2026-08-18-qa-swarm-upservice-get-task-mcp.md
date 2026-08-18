# Upservice MCP `get_task` Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Hunter a Cursor MCP tool `get_task(task_id)` that GETs the public Upservice task JSON so the agent does not invent `/v1/tasks/{id}`.

**Architecture:** Tested HTTP lives in `tools/upservice_mcp/client.py` (stdlib urllib GET, 429 retry). `server.py` is a thin FastMCP wrapper. Hunter still writes `_incoming/task.json` from the raw `{status_code, body}`. Librarian and `task.json` schema do not change.

**Tech Stack:** Python 3.11+ stdlib (`urllib`, `json`, `re`), package `mcp` (FastMCP), pytest, ruff. Host CLI: `py -3`.

## Global Constraints

- Tool name is exactly `get_task`; HTTP is GET only, path `/v1/tasks/{task_id}` with no trailing slash.
- Return shape is always `{status_code: int, body: object|str}`; the tool writes no files.
- Token values never appear in `body`, logs, git, or `task.json`; env name `UPSERVICE_PUBLIC_API_TOKEN` is allowed.
- Token source: `os.environ[token_env]` then `products/upservice/.env`.
- Config from `products/upservice/config.yaml` (`public_api.base_url`, `public_api.token_env`); v1 product id must be `upservice`.
- 429 retries only (not 401/404/5xx/`status_code: 0`); max 6 GETs per tool call; wait `Retry-After` or 1→2→4→8→16s, cap 30s; GET timeout 30s.
- No PyYAML and no httpx; parse the existing YAML config with a small nested-key reader.
- Do not import `upservice-personal-assistant`.
- Do not change `tools/memory_schema.py` or the `task.json` contract.
- Do not add list/search/write tools or an internal-API MCP.
- Host CLI: `py -3`, not `python`.
- Coordinator does not write `memory/`. Agents do not write to Upservice.

### File map

| Path | Responsibility |
|------|----------------|
| `tools/upservice_mcp/__init__.py` | Package marker |
| `tools/upservice_mcp/client.py` | Normalize id, config, token, GET, 429 retry, `get_task` |
| `tools/upservice_mcp/server.py` | FastMCP stdio + tool `get_task` |
| `tests/test_get_task_mcp.py` | Mocked HTTP tests (no live Upservice) |
| `docs/examples/mcp.json` | Cursor MCP registration example (no secrets) |
| `pyproject.toml` | Runtime dep `mcp` |
| `.cursor/agents/hunter.md` | `kind: task` must call `get_task` |
| `.cursor/rules/coordinator.mdc` | Missing tool → example mcp.json, no second Hunter |
| `AGENTS.md`, `README.md` | Spec link and setup |
| `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md` | HTTP-client exception |

---

### Task 1: Public GET client (no 429 retry yet)

**Files:**
- Create: `tools/upservice_mcp/__init__.py`
- Create: `tools/upservice_mcp/client.py`
- Create: `tests/test_get_task_mcp.py`
- Test: `tests/test_get_task_mcp.py`

**Interfaces:**
- Consumes: nothing from later tasks
- Produces:
  - `GET_TIMEOUT: float = 30.0`
  - `MAX_ATTEMPTS: int = 6`
  - `MAX_WAIT: float = 30.0`
  - `normalize_task_id(raw: str | int) -> str`
  - `authorization_header(token: str) -> str`
  - `parse_product_yaml(text: str) -> dict`
  - `load_token(token_env: str, env_file: Path, environ: Mapping[str, str]) -> str | None`
  - `urllib_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]`
  - `get_task(task_id: str | int, *, products_root: Path, environ: Mapping[str, str] | None = None, http_get: Callable[[str, dict[str, str], float], tuple[int, str, dict[str, str]]] | None = None, sleep: Callable[[float], None] | None = None, now: Callable[[], datetime] | None = None) -> dict[str, object]`
  - In this task `get_task` performs **one** GET (429 is returned immediately). `sleep` / `MAX_ATTEMPTS` exist so Task 2 does not rename the function.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_get_task_mcp.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from upservice_mcp import client as utc

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


def test_normalize_keeps_digits() -> None:
    assert utc.normalize_task_id("5201511") == "5201511"


def test_normalize_strips_junk() -> None:
    assert utc.normalize_task_id(" Task 12 ") == "task-12"


def test_authorization_adds_bearer() -> None:
    assert utc.authorization_header("abc") == "Bearer abc"


def test_authorization_keeps_existing_scheme() -> None:
    assert utc.authorization_header("Bearer abc") == "Bearer abc"


def test_get_task_200_raw_body_no_token_leak(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[tuple[str, dict[str, str], float]] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append((url, headers, timeout))
        return 200, json.dumps({"id": 1, "title": "Show sprint dates"}), {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert result["body"] == {"id": 1, "title": "Show sprint dates"}
    assert TOKEN not in json.dumps(result)
    assert calls[0][0] == "https://public.upservice.io/v1/tasks/1"
    assert calls[0][2] == utc.GET_TIMEOUT
    assert calls[0][1]["Authorization"] == f"Bearer {TOKEN}"
    assert len(calls) == 1


def test_get_task_404_single_get(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(url)
        return 404, json.dumps({"detail": "not found"}), {}

    result = utc.get_task("9", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 404
    assert len(calls) == 1


def test_get_task_401_no_retry(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[int] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls.append(1)
        return 401, json.dumps({"detail": "unauthorized"}), {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 401
    assert TOKEN not in json.dumps(result)
    assert len(calls) == 1


def test_get_task_missing_token_no_http(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env="")
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 401
    assert called["n"] == 0
    assert TOKEN not in json.dumps(result)
    body = result["body"]
    assert isinstance(body, dict)
    assert "error" in body


def test_get_task_token_from_environ_not_dotenv(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env="UPSERVICE_PUBLIC_API_TOKEN=from-file\n")
    seen: list[str] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        seen.append(headers["Authorization"])
        return 200, "{}", {}

    utc.get_task(
        "1",
        products_root=products,
        environ={"UPSERVICE_PUBLIC_API_TOKEN": "from-env"},
        http_get=http_get,
    )
    assert seen == ["Bearer from-env"]


def test_get_task_missing_config(tmp_path: Path) -> None:
    products = tmp_path / "products"
    products.mkdir()
    result = utc.get_task("1", products_root=products, environ={}, http_get=lambda *_a: (200, "{}", {}))
    assert result["status_code"] == 0
    assert isinstance(result["body"], dict)


def test_get_task_rejects_slash_id(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.get_task("../x", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 0
    assert called["n"] == 0


def test_get_task_wrong_product_id(tmp_path: Path) -> None:
    config = CONFIG.replace("id: upservice", "id: other")
    products = _product_root(tmp_path, config=config, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    called = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 0
    assert called["n"] == 0


def test_get_task_non_json_body_is_string(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        return 200, "not-json", {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert result["body"] == "not-json"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `py -3 -m pytest tests/test_get_task_mcp.py -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'upservice_mcp'` (or `cannot import name`).

- [ ] **Step 3: Write minimal implementation (single GET, no 429 loop)**

Create empty `tools/upservice_mcp/__init__.py`.

Create `tools/upservice_mcp/client.py`:

```python
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any

GET_TIMEOUT = 30.0
MAX_ATTEMPTS = 6
MAX_WAIT = 30.0
ID_RE = re.compile(r"^[a-z0-9-]+$")
BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0)

HttpGet = Callable[[str, dict[str, str], float], tuple[int, str, dict[str, str]]]


def normalize_task_id(raw: str | int) -> str:
    text = str(raw).strip()
    if ID_RE.fullmatch(text):
        return text
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text


def authorization_header(token: str) -> str:
    if " " in token:
        return token
    return f"Bearer {token}"


def parse_product_yaml(text: str) -> dict[str, Any]:
    root: dict[str, Any] = {}
    section: str | None = None
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        if line[0] not in " \t":
            section = None
            key, _, value = line.partition(":")
            key = key.strip()
            value = value.strip()
            if value:
                root[key] = value
            else:
                nested: dict[str, str] = {}
                root[key] = nested
                section = key
            continue
        if section is None:
            continue
        key, _, value = line.strip().partition(":")
        nested_map = root[section]
        if isinstance(nested_map, dict):
            nested_map[key.strip()] = value.strip()
    return root


def load_token(token_env: str, env_file: Path, environ: Mapping[str, str]) -> str | None:
    value = environ.get(token_env, "").strip()
    if value:
        return value
    if not env_file.is_file():
        return None
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        if key.strip() != token_env:
            continue
        return val.strip().strip("'").strip('"')
    return None


def urllib_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
            return int(response.status), body, dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), body, dict(exc.headers.items())
    except Exception as exc:
        return 0, str(exc), {}


def _decode_body(text: str) -> Any:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def _error(status: int, message: str) -> dict[str, object]:
    return {"status_code": status, "body": {"error": message}}


def get_task(
    task_id: str | int,
    *,
    products_root: Path,
    environ: Mapping[str, str] | None = None,
    http_get: HttpGet | None = None,
    sleep: Callable[[float], None] | None = None,
    now: Callable[[], datetime] | None = None,
) -> dict[str, object]:
    del sleep, now
    env = dict(environ) if environ is not None else dict(__import__("os").environ)
    task_id_text = str(task_id)
    if "/" in task_id_text:
        return _error(0, "invalid task_id")
    normalized = normalize_task_id(task_id)
    if not normalized or "/" in normalized:
        return _error(0, "invalid task_id")

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
    url = f"{base_url}/v1/tasks/{normalized}"
    headers = {"Authorization": authorization_header(token), "Accept": "application/json"}
    status, text, _hdrs = getter(url, headers, GET_TIMEOUT)
    if status == 0:
        return _error(0, text or "request failed")
    return {"status_code": status, "body": _decode_body(text)}
```

Do not log the token. `sleep` and `now` are unused until Task 2.

- [ ] **Step 4: Run tests to verify they pass**

Run: `py -3 -m pytest tests/test_get_task_mcp.py -v`

Expected: PASS (all Task 1 tests).

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/__init__.py tools/upservice_mcp/client.py tests/test_get_task_mcp.py
git commit -m "feat: add Upservice public GET client for get_task"
```

---

### Task 2: 429 retry inside `get_task`

**Files:**
- Modify: `tools/upservice_mcp/client.py`
- Modify: `tests/test_get_task_mcp.py`
- Test: `tests/test_get_task_mcp.py`

**Interfaces:**
- Consumes: `get_task`, `GET_TIMEOUT`, `MAX_ATTEMPTS`, `MAX_WAIT`, `BACKOFF` from Task 1
- Produces:
  - `parse_retry_after(value: str | None, *, now: datetime) -> float | None`
  - `backoff_seconds(wait_index: int) -> float` — `wait_index` 0..4 → 1, 2, 4, 8, 16; larger indexes → `MAX_WAIT`; each value capped at `MAX_WAIT`
  - `get_task` retries only when HTTP status is 429, up to `MAX_ATTEMPTS` GETs; other statuses unchanged (one GET)

- [ ] **Step 1: Write the failing 429 tests**

Append to `tests/test_get_task_mcp.py`:

```python
from datetime import datetime, timedelta, timezone


def test_backoff_series() -> None:
    assert utc.backoff_seconds(0) == 1.0
    assert utc.backoff_seconds(1) == 2.0
    assert utc.backoff_seconds(4) == 16.0
    assert utc.backoff_seconds(5) == utc.MAX_WAIT


def test_parse_retry_after_delta_seconds() -> None:
    now = datetime(2026, 8, 18, tzinfo=timezone.utc)
    assert utc.parse_retry_after("2", now=now) == 2.0


def test_parse_retry_after_http_date() -> None:
    now = datetime(2026, 8, 18, 12, 0, 0, tzinfo=timezone.utc)
    later = now + timedelta(seconds=8)
    http_date = later.strftime("%a, %d %b %Y %H:%M:%S GMT")
    assert utc.parse_retry_after(http_date, now=now) == 8.0


def test_429_then_200_retries_once(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls = {"n": 0}
    sleeps: list[float] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, json.dumps({"detail": "slow down"}), {}
        return 200, json.dumps({"id": 1}), {}

    result = utc.get_task(
        "1",
        products_root=products,
        environ={},
        http_get=http_get,
        sleep=sleeps.append,
    )
    assert result["status_code"] == 200
    assert result["body"] == {"id": 1}
    assert calls["n"] == 2
    assert sleeps == [1.0]


def test_retry_after_header_used(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    sleeps: list[float] = []
    calls = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls["n"] += 1
        if calls["n"] == 1:
            return 429, "{}", {"Retry-After": "2"}
        return 200, "{}", {}

    utc.get_task(
        "1",
        products_root=products,
        environ={},
        http_get=http_get,
        sleep=sleeps.append,
    )
    assert sleeps[0] >= 2.0


def test_six_429_returns_429(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls = {"n": 0}
    sleeps: list[float] = []

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls["n"] += 1
        return 429, json.dumps({"detail": "rate"}), {}

    result = utc.get_task(
        "1",
        products_root=products,
        environ={},
        http_get=http_get,
        sleep=sleeps.append,
    )
    assert result["status_code"] == 429
    assert calls["n"] == 6
    assert sleeps == [1.0, 2.0, 4.0, 8.0, 16.0]
    assert TOKEN not in json.dumps(result)


def test_404_still_single_get_after_retry_logic(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls = {"n": 0}

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        calls["n"] += 1
        return 404, "{}", {}

    utc.get_task("1", products_root=products, environ={}, http_get=http_get, sleep=lambda _s: None)
    assert calls["n"] == 1
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `py -3 -m pytest tests/test_get_task_mcp.py::test_429_then_200_retries_once tests/test_get_task_mcp.py::test_six_429_returns_429 -v`

Expected: FAIL (`status_code` 429 after one GET, or `backoff_seconds` missing).

- [ ] **Step 3: Implement retry in `get_task`**

Add to `tools/upservice_mcp/client.py` (keep existing helpers). Import `email.utils.parsedate_to_datetime`.

```python
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime


def backoff_seconds(wait_index: int) -> float:
    if wait_index < 0:
        wait_index = 0
    if wait_index >= len(BACKOFF):
        return MAX_WAIT
    return min(BACKOFF[wait_index], MAX_WAIT)


def parse_retry_after(value: str | None, *, now: datetime) -> float | None:
    if not value:
        return None
    text = value.strip()
    if text.isdigit():
        return min(float(text), MAX_WAIT)
    try:
        target = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    if target.tzinfo is None:
        target = target.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    delta = (target - now).total_seconds()
    if delta < 0:
        return 0.0
    return min(delta, MAX_WAIT)
```

Replace the single `getter(...)` tail of `get_task` with this loop (do not delete config/token checks). Stop using `del sleep, now`. Default `sleep` is `time.sleep`. Default `now` is `datetime.now(timezone.utc)`.

```python
    getter = http_get or urllib_get
    sleeper = sleep or __import__("time").sleep
    clock = now or (lambda: datetime.now(timezone.utc))
    url = f"{base_url}/v1/tasks/{normalized}"
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
        return _error(0, last_text or "request failed")
    return {"status_code": last_status, "body": _decode_body(last_text)}
```

Header lookup is case-insensitive (`Retry-After` vs `retry-after`).

- [ ] **Step 4: Run all client tests**

Run: `py -3 -m pytest tests/test_get_task_mcp.py -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/client.py tests/test_get_task_mcp.py
git commit -m "feat: retry Upservice get_task on HTTP 429"
```

---

### Task 3: FastMCP server, example mcp.json, dependency

**Files:**
- Create: `tools/upservice_mcp/server.py`
- Create: `docs/examples/mcp.json`
- Modify: `pyproject.toml`
- Modify: `tests/test_get_task_mcp.py`
- Modify: `README.md` (setup + checks)
- Test: `tests/test_get_task_mcp.py`

**Interfaces:**
- Consumes: `get_task` from `tools/upservice_mcp/client.py` (same signature as Task 2)
- Produces:
  - `tools/upservice_mcp/server.py` FastMCP app name `upservice`, tool function `get_task(task_id: str | int) -> dict`
  - `REPO_ROOT = Path(__file__).resolve().parents[2]`
  - `docs/examples/mcp.json` with command `py` args `["-3", "tools/upservice_mcp/server.py"]`
  - `pyproject.toml` `[project] dependencies = ["mcp>=1.9.0"]`

- [ ] **Step 1: Write the failing server wiring test**

Append to `tests/test_get_task_mcp.py`:

```python
from upservice_mcp import server as ums


def test_server_get_task_uses_repo_products(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_get_task(task_id: str | int, *, products_root: Path, **kwargs: object) -> dict[str, object]:
        seen["task_id"] = task_id
        seen["products_root"] = products_root
        return {"status_code": 200, "body": {"id": int(task_id)}}

    monkeypatch.setattr(ums.client, "get_task", fake_get_task)
    result = ums.get_task("5201511")
    assert result == {"status_code": 200, "body": {"id": 5201511}}
    assert seen["task_id"] == "5201511"
    assert seen["products_root"] == ums.REPO_ROOT / "products"
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `py -3 -m pytest tests/test_get_task_mcp.py::test_server_get_task_uses_repo_products -v`

Expected: FAIL (`ModuleNotFoundError: upservice_mcp.server`).

- [ ] **Step 3: Add dependency, server, example mcp.json, README**

In `pyproject.toml` add under `[project]` (keep `requires-python` and `optional-dependencies`):

```toml
dependencies = ["mcp>=1.9.0"]
```

Install for this machine:

```powershell
py -3 -m pip install "mcp>=1.9.0"
```

Create `tools/upservice_mcp/server.py`:

```python
from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

from upservice_mcp import client

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("upservice")


@mcp.tool()
def get_task(task_id: str) -> dict:
    """Fetch one Upservice task by id from the public API.

    Call this instead of constructing GET /v1/tasks/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_task(task_id, products_root=REPO_ROOT / "products")


if __name__ == "__main__":
    mcp.run()
```

If `@mcp.tool()` fails on this `mcp` version, use `@mcp.tool` without `()` — keep the function name `get_task`.

Create `docs/examples/mcp.json` with no token fields:

```json
{
  "mcpServers": {
    "upservice": {
      "command": "py",
      "args": ["-3", "tools/upservice_mcp/server.py"]
    }
  }
}
```

In `README.md` Setup, after the `.env` bullet, add:

```markdown
7. Copy `docs/examples/mcp.json` into `.cursor/mcp.json` (gitignored) so Hunter can call `get_task`. Reload MCP in Cursor. Token stays in `products/upservice/.env`, not in mcp.json.
```

Renumber only if needed so the list stays sequential; do not drop Figma MCP.

In Checks, add `tests/test_get_task_mcp.py` to the pytest line:

```powershell
python -m pytest tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py tests/test_get_task_mcp.py -v
```

- [ ] **Step 4: Run tests**

Run: `py -3 -m pytest tests/test_get_task_mcp.py -v`

Expected: PASS, including `test_server_get_task_uses_repo_products`.

If import of `mcp.server.fastmcp` fails, fix the import to whatever the installed `mcp>=1.9.0` exports for FastMCP; do not switch to the `fastmcp` PyPI package.

- [ ] **Step 5: Commit**

```bash
git add tools/upservice_mcp/server.py docs/examples/mcp.json pyproject.toml tests/test_get_task_mcp.py README.md
git commit -m "feat: expose get_task as Cursor MCP stdio server"
```

---

### Task 4: Hunter, coordinator, kernel exception, spec index

**Files:**
- Modify: `.cursor/agents/hunter.md`
- Modify: `.cursor/rules/coordinator.mdc`
- Modify: `AGENTS.md`
- Modify: `README.md` (Acceptance spec links)
- Modify: `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md`
- Test: no new pytest; grep/read the phrases below

**Interfaces:**
- Consumes: MCP tool name `get_task` from Task 3; client retry from Task 2
- Produces: prompt/rules text only (no Python API)

- [ ] **Step 1: Patch Hunter `kind: task`**

In `.cursor/agents/hunter.md` replace the catalog sentence:

`Call APIs with Cursor HTTP/MCP tools. There is no HTTP client in this repo. Use `token_env` names; never write token values into files.`

with:

```markdown
Call APIs with Cursor HTTP/MCP tools. The only HTTP client in this repo is GET inside `tools/upservice_mcp/` for the `get_task` MCP tool. Use `token_env` names; never write token values into files.
```

Replace the whole `## Task snapshot (analyze-requirement)` section with the following (keep a json fence around the example object, same as today's hunter.md):

````markdown
## Task snapshot (analyze-requirement)

When the coordinator task says `kind: task` and a `task_id`:

- Normalize the raw task id before using it in `task.json` or any path: if it already matches `[a-z0-9-]+`, keep it; otherwise lowercase it, replace each run of non-alphanumeric characters with `-`, and trim leading/trailing `-`. If normalization produces an empty id, report failure and write nothing.
- Public fetch: call MCP tool `get_task` with that `task_id`. Do not construct `GET /v1/tasks/{id}` yourself. Do not open Figma. Browser is forbidden for this kind.
- If `get_task` is not in the available MCP tool list: stop. Write nothing. Report that Cursor must copy `docs/examples/mcp.json` into `.cursor/mcp.json` and reload MCP. Do not guess the public path.
- If `get_task` returns `status_code` 429: call `get_task` again with the same id, up to two more times (three tool calls max). 429 is not "task missing".
- If public still did not return 200 JSON and `internal_api.base_url` is in `products/<product-id>/config.yaml`: one generic HTTP call to internal (not MCP). Success → `channel: internal`.
- Do not treat `entities/tasks.md` as the instance list.
- Write `memory/<product-id>/raw/_incoming/task.json` from the tool `body` (title, fields, figma URLs you find there). Shape:

```json
{
  "kind": "task",
  "channel": "public",
  "fetched_at": "2026-08-13T17:00:00+03:00",
  "task_id": "1",
  "title": "Show sprint dates",
  "fields": {},
  "figma_urls": ["https://www.figma.com/design/demo/sprint"],
  "errors": []
}
```

- `MANIFEST.md` lists only `task.json`.
- If the task is missing or the tool returns 404/401/exhausted 429/`status_code` 0: `task.json` with empty title/fields and `errors[]` (code + short message, never the token value); still write MANIFEST. Do not invent the task.
- Do not write `requirements/` or `tasks/` canonical files.
````

- [ ] **Step 2: Patch coordinator**

Append to `.cursor/rules/coordinator.mdc` after the analyze-requirement paragraph:

```markdown
If Hunter reports the MCP tool `get_task` is missing: do not launch a second hunter and do not tell it to guess `/v1/tasks/{id}`. Tell the human to copy `docs/examples/mcp.json` into `.cursor/mcp.json` and reload MCP. Token stays in `products/upservice/.env`.
```

- [ ] **Step 3: Spec index + kernel exception**

In `AGENTS.md` Spec list, add:

```markdown
`docs/superpowers/specs/2026-08-18-qa-swarm-upservice-get-task-mcp-design.md`
```

In `README.md` Acceptance spec links, add the same path after the Testmo CSV line.

In `docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md` replace:

`Hunter ходит в public/internal API инструментами Cursor (HTTP и/или MCP из конфига Cursor). Отдельный HTTP-клиент в репозитории в v1 не пишем.`

with:

```markdown
Hunter ходит в public/internal API инструментами Cursor (HTTP и/или MCP из конфига Cursor). Отдельный HTTP-клиент в репозитории запрещён, кроме GET внутри `tools/upservice_mcp/` для MCP-тула `get_task`.
```

- [ ] **Step 4: Confirm phrases and tests still pass**

Run:

```powershell
py -3 -m pytest tests/test_get_task_mcp.py tests/test_memory_schema.py tests/test_testdoc_merge.py tests/test_testdoc_csv.py -v
```

Expected: PASS. `memory_schema.py` is unchanged.

Open `.cursor/agents/hunter.md` and confirm the phrases: `call MCP tool get_task`, `Do not construct GET /v1/tasks/{id}`, `up to two more times`, `docs/examples/mcp.json`.

Open `.cursor/rules/coordinator.mdc` and confirm: `get_task` is missing, no second hunter, `docs/examples/mcp.json`.

- [ ] **Step 5: Commit**

```bash
git add .cursor/agents/hunter.md .cursor/rules/coordinator.mdc AGENTS.md README.md docs/superpowers/specs/2026-08-13-qa-swarm-kernel-memory-design.md
git commit -m "docs: route Hunter kind:task through MCP get_task"
```

---

## Spec coverage (self-review)

| Spec | Task |
|------|------|
| `get_task` MCP, GET `/v1/tasks/{id}`, raw `{status_code, body}` | 1, 3 |
| Token env then `.env`; no secret in body | 1 |
| Product `upservice` only; invalid id `/` | 1 |
| 429: 6 attempts, Retry-After, backoff cap 30s | 2 |
| Hunter: must call tool, 2 extra 429 calls, internal ladder, missing MCP stop | 4 |
| Example `docs/examples/mcp.json`; gitignore `.cursor/mcp.json` | 3 (example); gitignore already lists `.cursor/mcp.json` |
| Kernel HTTP-client exception | 4 |
| Tests 1–8 from spec §11 | 1–2 (`urllib` URL asserted in 200 test) |
| No `memory_schema` / `task.json` change | 4 step 4 |
| Manual live acceptance | not automated; README setup step to enable MCP |

Do not implement list/search/write tools, internal MCP, or personal-assistant imports.
