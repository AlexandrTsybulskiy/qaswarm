from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from upservice_public_api.client import (
    _decode_body,
    _error,
    _normalize_body,
    _redact_token_in_body,
    load_token,
    parse_product_yaml,
)

GET_TIMEOUT = 30.0
POST_TIMEOUT = 30.0


def authorization_header(token: str) -> str:
    value = token.strip()
    prefix = "bearer "
    if value.lower().startswith(prefix):
        return f"Bearer {value[len(prefix) :].strip()}"
    return f"Bearer {value}"


def _product_dir(products_root: Path) -> Path | None:
    if not products_root.is_dir():
        return None
    dirs = [path for path in products_root.iterdir() if path.is_dir()]
    if len(dirs) != 1 or dirs[0].name != "upservice":
        return None
    return dirs[0]


def _load_testmo_config(
    products_root: Path, environ: dict[str, str] | None = None
) -> tuple[str, str, Path] | tuple[None, None, None]:
    product_dir = _product_dir(products_root)
    if product_dir is None:
        return None, None, None
    config_path = product_dir / "config.yaml"
    if not config_path.is_file():
        return None, None, None
    parsed = parse_product_yaml(config_path.read_text(encoding="utf-8"))
    if parsed.get("id") != "upservice":
        return None, None, None
    testmo = parsed.get("testmo")
    if not isinstance(testmo, dict):
        return None, None, None
    base_url = str(testmo.get("base_url", "")).rstrip("/")
    token_env = str(testmo.get("token_env", "")).strip()
    if not base_url or not token_env:
        return None, None, None
    return base_url, token_env, product_dir


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


def urllib_post(
    url: str, headers: dict[str, str], body: str, timeout: float
) -> tuple[int, str, dict[str, str]]:
    data = body.encode("utf-8")
    request = urllib.request.Request(url, headers=headers, method="POST", data=data)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            text = response.read().decode("utf-8", errors="replace")
            return int(response.status), text, dict(response.headers.items())
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return int(exc.code), text, dict(exc.headers.items())
    except Exception as exc:
        return 0, str(exc), {}


def _result(status: int, text: str, token: str) -> dict[str, object]:
    if status == 0:
        return _error(0, text or "request failed")
    body = _normalize_body(_decode_body(text))
    if not isinstance(body, (dict, str)):
        body = _normalize_body(body)
    return {"status_code": status, "body": _redact_token_in_body(body, token)}


def _testmo_get(
    path: str,
    *,
    products_root: Path,
    query: dict[str, object] | None = None,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    base_url, token_env, product_dir = _load_testmo_config(products_root, environ)
    if not base_url or not token_env or product_dir is None:
        return _error(0, "missing testmo config")
    env = environ if environ is not None else dict(__import__("os").environ)
    token = load_token(token_env, product_dir / ".env", env)
    if not token:
        return _error(401, "missing token")
    headers = {"Authorization": authorization_header(token), "Accept": "application/json"}
    url = f"{base_url}{path}"
    if query:
        encoded = urllib.parse.urlencode(query, doseq=True)
        if encoded:
            url = f"{url}?{encoded}"
    getter = http_get or urllib_get
    status, text, _ = getter(url, headers, GET_TIMEOUT)
    return _result(status, text, token)


def _testmo_post(
    path: str,
    *,
    payload: dict[str, Any],
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_post=None,
) -> dict[str, object]:
    base_url, token_env, product_dir = _load_testmo_config(products_root, environ)
    if not base_url or not token_env or product_dir is None:
        return _error(0, "missing testmo config")
    env = environ if environ is not None else dict(__import__("os").environ)
    token = load_token(token_env, product_dir / ".env", env)
    if not token:
        return _error(401, "missing token")
    if not isinstance(payload, dict):
        return _error(0, "invalid payload")
    body = json.dumps(payload)
    headers = {
        "Authorization": authorization_header(token),
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    poster = http_post or urllib_post
    status, text, _ = poster(f"{base_url}{path}", headers, body, POST_TIMEOUT)
    return _result(status, text, token)


def _validate_query(query: dict[str, object] | None) -> bool:
    if query is None:
        return True
    if not isinstance(query, dict):
        return False
    for key, value in query.items():
        if not isinstance(key, str):
            return False
        if isinstance(value, (str, int, bool)) or value is None:
            continue
        return False
    return True


def _validate_project_id(project_id: str | int) -> str | None:
    text = str(project_id).strip()
    if not text.isdigit():
        return None
    return text


def list_testmo_projects(
    *,
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    return _testmo_get(
        "/api/v1/projects",
        products_root=products_root,
        query=None,
        environ=environ,
        http_get=http_get,
    )


def list_testmo_folders(
    project_id: str | int,
    *,
    page: int | None = None,
    per_page: int | None = None,
    query: dict[str, object] | None = None,
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not _validate_query(query):
        return _error(0, "invalid query")
    merged: dict[str, object] = {}
    if page is not None:
        merged["page"] = page
    if per_page is not None:
        merged["per_page"] = per_page
    if query:
        merged.update(query)
    return _testmo_get(
        f"/api/v1/projects/{normalized}/folders",
        products_root=products_root,
        query=merged,
        environ=environ,
        http_get=http_get,
    )


def list_testmo_cases(
    project_id: str | int,
    *,
    page: int | None = None,
    per_page: int | None = None,
    query: dict[str, object] | None = None,
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not _validate_query(query):
        return _error(0, "invalid query")
    merged: dict[str, object] = {}
    if page is not None:
        merged["page"] = page
    if per_page is not None:
        merged["per_page"] = per_page
    if query:
        merged.update(query)
    return _testmo_get(
        f"/api/v1/projects/{normalized}/cases",
        products_root=products_root,
        query=merged,
        environ=environ,
        http_get=http_get,
    )


def list_testmo_runs(
    project_id: str | int,
    *,
    page: int | None = None,
    per_page: int | None = None,
    query: dict[str, object] | None = None,
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not _validate_query(query):
        return _error(0, "invalid query")
    merged: dict[str, object] = {}
    if page is not None:
        merged["page"] = page
    if per_page is not None:
        merged["per_page"] = per_page
    if query:
        merged.update(query)
    return _testmo_get(
        f"/api/v1/projects/{normalized}/runs",
        products_root=products_root,
        query=merged,
        environ=environ,
        http_get=http_get,
    )


def list_testmo_milestones(
    project_id: str | int,
    *,
    page: int | None = None,
    per_page: int | None = None,
    query: dict[str, object] | None = None,
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_get=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not _validate_query(query):
        return _error(0, "invalid query")
    merged: dict[str, object] = {}
    if page is not None:
        merged["page"] = page
    if per_page is not None:
        merged["per_page"] = per_page
    if query:
        merged.update(query)
    return _testmo_get(
        f"/api/v1/projects/{normalized}/milestones",
        products_root=products_root,
        query=merged,
        environ=environ,
        http_get=http_get,
    )


def create_testmo_folders(
    project_id: str | int,
    *,
    folders: list[dict[str, Any]],
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_post=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not isinstance(folders, list):
        return _error(0, "invalid payload")
    return _testmo_post(
        f"/api/v1/projects/{normalized}/folders",
        payload={"folders": folders},
        products_root=products_root,
        environ=environ,
        http_post=http_post,
    )


def create_testmo_cases(
    project_id: str | int,
    *,
    cases: list[dict[str, Any]],
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_post=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None or not isinstance(cases, list):
        return _error(0, "invalid payload")
    return _testmo_post(
        f"/api/v1/projects/{normalized}/cases",
        payload={"cases": cases},
        products_root=products_root,
        environ=environ,
        http_post=http_post,
    )


def create_testmo_runs(
    project_id: str | int,
    *,
    payload: dict[str, Any],
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_post=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None:
        return _error(0, "invalid payload")
    return _testmo_post(
        f"/api/v1/projects/{normalized}/runs",
        payload=payload,
        products_root=products_root,
        environ=environ,
        http_post=http_post,
    )


def create_testmo_milestones(
    project_id: str | int,
    *,
    payload: dict[str, Any],
    products_root: Path,
    environ: dict[str, str] | None = None,
    http_post=None,
) -> dict[str, object]:
    normalized = _validate_project_id(project_id)
    if normalized is None:
        return _error(0, "invalid payload")
    return _testmo_post(
        f"/api/v1/projects/{normalized}/milestones",
        payload=payload,
        products_root=products_root,
        environ=environ,
        http_post=http_post,
    )
