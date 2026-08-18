from __future__ import annotations

import json
from pathlib import Path

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


def test_get_task_redacts_token_from_response_body(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        return 200, json.dumps({"id": 1, "note": f"token was {TOKEN}"}), {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert TOKEN not in json.dumps(result)
    body = result["body"]
    assert isinstance(body, dict)
    assert TOKEN not in json.dumps(body)
    assert "note" in body


def test_get_task_json_array_body_is_string(tmp_path: Path) -> None:
    products = _product_root(tmp_path, env=f"UPSERVICE_PUBLIC_API_TOKEN={TOKEN}\n")
    payload = [{"id": 1}, {"id": 2}]

    def http_get(url: str, headers: dict[str, str], timeout: float) -> tuple[int, str, dict[str, str]]:
        return 200, json.dumps(payload), {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    body = result["body"]
    assert isinstance(body, str)
    assert json.loads(body) == payload
