from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from product_config import (
    load_token,  # re-exported for testmo_mcp and figma_mcp
    merge_env,
    parse_product_yaml,
    resolve_public_api_base_url,
    resolve_public_api_token,
)

GET_TIMEOUT = 30.0
MAX_ATTEMPTS = 6
MAX_WAIT = 30.0
ID_RE = re.compile(r"^[a-z0-9-]+$")
QUERY_KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")
BACKOFF = (1.0, 2.0, 4.0, 8.0, 16.0)

HttpGet = Callable[[str, dict[str, str], float], tuple[int, str, dict[str, str]]]


def normalize_task_id(raw: str | int) -> str:
    text = str(raw).strip()
    if ID_RE.fullmatch(text):
        return text
    text = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return text


def authorization_header(token: str) -> str:
    value = token.strip()
    prefix = "bearer "
    if value.lower().startswith(prefix):
        return value[len(prefix) :].strip()
    return value


def urllib_get(
    url: str, headers: dict[str, str], timeout: float
) -> tuple[int, str, dict[str, str]]:
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


def _normalize_body(decoded: Any) -> dict[str, Any] | str:
    if isinstance(decoded, dict):
        return decoded
    if isinstance(decoded, str):
        return decoded
    return json.dumps(decoded)


def _redact_token_in_value(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {
            (key.replace(token, "[REDACTED]") if isinstance(key, str) else key): (
                _redact_token_in_value(item, token)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_token_in_value(item, token) for item in value]
    if isinstance(value, str):
        return value.replace(token, "[REDACTED]")
    return value


def _redact_token_in_body(body: dict[str, Any] | str, token: str) -> dict[str, Any] | str:
    if isinstance(body, dict):
        return _redact_token_in_value(body, token)
    return body.replace(token, "[REDACTED]")


def _error(status: int, message: str) -> dict[str, object]:
    return {"status_code": status, "body": {"error": message}}


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


def _invalid_nonneg_int(value: int | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool) or not isinstance(value, int):
        return True
    return value < 0


def merge_list_query(
    limit: int | None = None,
    offset: int | None = None,
    query: Mapping[str, object] | None = None,
) -> dict[str, str | list[str]] | None:
    if _invalid_nonneg_int(limit) or _invalid_nonneg_int(offset):
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
    token_env = str(public.get("token_env", "")).strip()
    if not token_env:
        return _error(0, "missing public_api")

    merged_env = merge_env(product_dir / ".env", env)
    base_url = resolve_public_api_base_url(parsed, merged_env)
    if not base_url:
        return _error(0, "missing public_api")

    token, _ = resolve_public_api_token(product_dir, parsed, merged_env)
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
