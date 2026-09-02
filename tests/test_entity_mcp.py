from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from upservice_public_api import client as utc
from upservice_public_api import get as upg

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

    def http_get(
        got: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
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

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = utc.get_project("../x", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 0
    assert called["n"] == 0


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

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
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

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
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

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
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

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
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


def test_get_cli_project_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    calls: list[str] = []

    def fake_public_get(
        path: str, *, products_root: Path, query: object = None, **kwargs: object
    ) -> dict[str, object]:
        calls.append(path)
        return {"status_code": 200, "body": {"id": 12}}

    monkeypatch.setattr(upg.client, "public_get", fake_public_get)
    result = upg.run("/v1/projects/12", products_root=products)
    assert result == {"status_code": 200, "body": {"id": 12}}
    assert calls == ["/v1/projects/12"]


def test_get_cli_list_projects_query(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    seen: dict[str, object] = {}

    def fake_public_get(
        path: str, *, products_root: Path, query: object = None, **kwargs: object
    ) -> dict[str, object]:
        seen["path"] = path
        seen["query"] = query
        return {"status_code": 200, "body": {"count": 0, "results": []}}

    monkeypatch.setattr(upg.client, "public_get", fake_public_get)
    result = upg.run(
        "/v1/projects",
        ["--limit", "25", "--offset", "0", "--status", "active"],
        products_root=products,
    )
    assert result["status_code"] == 200
    assert seen["path"] == "/v1/projects"
    assert seen["query"] == {"limit": "25", "offset": "0", "status": "active"}



