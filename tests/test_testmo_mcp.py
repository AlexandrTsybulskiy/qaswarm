from __future__ import annotations

import json
from pathlib import Path
from typing import get_type_hints
from urllib.parse import parse_qs, urlparse

import pytest

from testmo_mcp import client as tmc
from testmo_mcp import server as tms

CONFIG = """id: upservice
name: Upservice
public_api:
  base_url: https://public.upservice.io/
  catalog_hint: /openapi.json
  token_env: UPSERVICE_PUBLIC_API_TOKEN
testmo:
  base_url: https://softvoya.testmo.net
  token_env: TESTMO_API_KEY
mcp:
  browser: false
ttl_hours: 168
"""

TOKEN = "testmo-secret-token"


def _product_root(tmp_path: Path, config: str = CONFIG, env: str | None = None) -> Path:
    products = tmp_path / "products"
    folder = products / "upservice"
    folder.mkdir(parents=True)
    (folder / "config.yaml").write_text(config, encoding="utf-8")
    if env is not None:
        (folder / ".env").write_text(env, encoding="utf-8")
    return products


def test_list_testmo_projects_hits_projects_endpoint(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[tuple[str, dict[str, str]]] = []

    def http_get(
        got: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append((got, headers))
        return 200, json.dumps({"result": [{"id": 2, "name": "Upservice"}]}), {}

    result = tmc.list_testmo_projects(products_root=products, environ={}, http_get=http_get)

    assert result["status_code"] == 200
    assert result["body"] == {"result": [{"id": 2, "name": "Upservice"}]}
    assert calls == [
        (
            "https://softvoya.testmo.net/api/v1/projects",
            {"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
        )
    ]


def test_list_testmo_folders_encodes_query(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[str] = []

    def http_get(
        got: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append(got)
        return 200, json.dumps({"result": []}), {}

    result = tmc.list_testmo_folders(
        project_id=2,
        page=3,
        per_page=100,
        query={"parent_id": 1235, "name": "API"},
        products_root=products,
        environ={},
        http_get=http_get,
    )

    assert result["status_code"] == 200
    parsed = urlparse(calls[0])
    assert parsed.path == "/api/v1/projects/2/folders"
    qs = parse_qs(parsed.query)
    assert qs["page"] == ["3"]
    assert qs["per_page"] == ["100"]
    assert qs["parent_id"] == ["1235"]
    assert qs["name"] == ["API"]


def test_create_testmo_folder_posts_payload(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[tuple[str, dict[str, str], str]] = []

    def http_post(
        got: str, headers: dict[str, str], body: str, timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append((got, headers, body))
        return 201, json.dumps({"result": [{"id": 307546, "name": "API Test Folder"}]}), {}

    result = tmc.create_testmo_folders(
        project_id=2,
        folders=[{"name": "API Test Folder", "parent_id": 1235}],
        products_root=products,
        environ={},
        http_post=http_post,
    )

    assert result["status_code"] == 201
    payload = json.loads(calls[0][2])
    assert calls[0][0] == "https://softvoya.testmo.net/api/v1/projects/2/folders"
    assert calls[0][1] == {
        "Authorization": f"Bearer {TOKEN}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    assert payload == {"folders": [{"name": "API Test Folder", "parent_id": 1235}]}


def test_create_testmo_case_posts_payload(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[tuple[str, str]] = []

    def http_post(
        got: str, headers: dict[str, str], body: str, timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append((got, body))
        return 201, json.dumps({"result": [{"id": 5898127, "folder_id": 307546}]}), {}

    result = tmc.create_testmo_cases(
        project_id=2,
        cases=[{"name": "API Test Case", "folder_id": 307546}],
        products_root=products,
        environ={},
        http_post=http_post,
    )

    assert result["status_code"] == 201
    assert calls[0][0] == "https://softvoya.testmo.net/api/v1/projects/2/cases"
    assert json.loads(calls[0][1]) == {
        "cases": [{"name": "API Test Case", "folder_id": 307546}]
    }


def test_create_testmo_run_posts_payload(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[tuple[str, str]] = []

    def http_post(
        got: str, headers: dict[str, str], body: str, timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append((got, body))
        return 201, json.dumps({"result": {"id": 42}}), {}

    result = tmc.create_testmo_runs(
        project_id=2,
        payload={"name": "API Run", "case_ids": [5898127]},
        products_root=products,
        environ={},
        http_post=http_post,
    )

    assert result["status_code"] == 201
    assert calls[0][0] == "https://softvoya.testmo.net/api/v1/projects/2/runs"
    assert json.loads(calls[0][1]) == {"name": "API Run", "case_ids": [5898127]}


def test_create_testmo_milestone_posts_payload(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    calls: list[tuple[str, str]] = []

    def http_post(
        got: str, headers: dict[str, str], body: str, timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append((got, body))
        return 201, json.dumps({"result": {"id": 77}}), {}

    result = tmc.create_testmo_milestones(
        project_id=2,
        payload={"name": "API Milestone"},
        products_root=products,
        environ={},
        http_post=http_post,
    )

    assert result["status_code"] == 201
    assert calls[0][0] == "https://softvoya.testmo.net/api/v1/projects/2/milestones"
    assert json.loads(calls[0][1]) == {"name": "API Milestone"}


def test_testmo_missing_token_returns_401(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env="")
    result = tmc.list_testmo_projects(products_root=products, environ={})
    assert result == {"status_code": 401, "body": {"error": "missing token"}}


def test_testmo_invalid_query_skips_http(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")
    called = {"n": 0}

    def http_get(
        got: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        called["n"] += 1
        return 200, "{}", {}

    result = tmc.list_testmo_folders(
        project_id=2,
        query={"filters": {"name": "x"}},
        products_root=products,
        environ={},
        http_get=http_get,
    )

    assert result["status_code"] == 0
    assert called["n"] == 0


def test_testmo_redacts_token_from_error_body(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"TESTMO_API_KEY={TOKEN}\n")

    def http_get(
        got: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        return 500, json.dumps({"error": f"bad token {TOKEN}"}), {}

    result = tmc.list_testmo_projects(products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 500
    assert TOKEN not in json.dumps(result)


def test_server_list_testmo_projects_uses_repo_products(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake_list_testmo_projects(*, products_root: Path, **kwargs: object) -> dict[str, object]:
        seen["products_root"] = products_root
        return {"status_code": 200, "body": {"result": []}}

    monkeypatch.setattr(tms.client, "list_testmo_projects", fake_list_testmo_projects)
    result = tms.list_testmo_projects()
    assert result == {"status_code": 200, "body": {"result": []}}
    assert seen["products_root"] == tms.REPO_ROOT / "products"


def test_server_create_testmo_folders_passes_args(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_create_testmo_folders(
        project_id: str | int,
        *,
        folders: list[dict[str, object]],
        products_root: Path,
        **kwargs: object,
    ) -> dict[str, object]:
        seen["project_id"] = project_id
        seen["folders"] = folders
        seen["products_root"] = products_root
        return {"status_code": 201, "body": {"result": [{"id": 1}]}}

    monkeypatch.setattr(tms.client, "create_testmo_folders", fake_create_testmo_folders)
    payload = [{"name": "Folder"}]
    result = tms.create_testmo_folders("2", folders=payload)
    assert result["status_code"] == 201
    assert seen["project_id"] == "2"
    assert seen["folders"] == payload
    assert seen["products_root"] == tms.REPO_ROOT / "products"
    assert get_type_hints(tms.create_testmo_folders)["project_id"] == str | int
