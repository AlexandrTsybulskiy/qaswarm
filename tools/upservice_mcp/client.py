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


def _normalize_body(decoded: Any) -> dict[str, Any] | str:
    if isinstance(decoded, dict):
        return decoded
    if isinstance(decoded, str):
        return decoded
    return json.dumps(decoded)


def _redact_token_in_value(value: Any, token: str) -> Any:
    if isinstance(value, dict):
        return {key: _redact_token_in_value(item, token) for key, item in value.items()}
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
        result = _error(0, text or "request failed")
    else:
        result = {"status_code": status, "body": _normalize_body(_decode_body(text))}
    body = result["body"]
    if not isinstance(body, (dict, str)):
        body = _normalize_body(body)
    result = dict(result)
    result["body"] = _redact_token_in_body(body, token)
    return result
