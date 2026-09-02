from __future__ import annotations

from pathlib import Path

from product_config import (
    active_env_name,
    merge_env,
    resolve_product_connection,
    resolve_public_api_base_url,
    resolve_public_api_token,
    resolve_ui_base_url,
    resolve_ui_credentials,
)
from upservice_public_api import client as utc

CONFIG = """id: upservice
name: Upservice
public_api:
  base_url: https://public.upservice.io/
  catalog_hint: /openapi.json
  token_env: UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN
mcp:
  browser: false
ttl_hours: 168
"""


def _product_dir(tmp_path: Path, env: str) -> Path:
    folder = tmp_path / "upservice"
    folder.mkdir()
    (folder / "config.yaml").write_text(CONFIG, encoding="utf-8")
    (folder / ".env").write_text(env, encoding="utf-8")
    return folder


def test_active_env_defaults_to_prod() -> None:
    assert active_env_name({}) == "prod"


def test_active_env_reads_stage() -> None:
    assert active_env_name({"UPSERVICE_ENV": "stage"}) == "stage"


def test_active_env_invalid_falls_back_to_prod() -> None:
    assert active_env_name({"UPSERVICE_ENV": "purple"}) == "prod"


def test_resolve_public_api_base_url_for_stage(tmp_path: Path) -> None:
    product_dir = _product_dir(
        tmp_path,
        env=(
            "UPSERVICE_ENV=stage\n"
            "UPSERVICE_STAGE_PUBLIC_API_BASE_URL=https://public.staging.buselsoft.com/\n"
            "UPSERVICE_STAGE_PUBLIC_API_TOKEN=stage-token\n"
        ),
    )
    parsed = utc.parse_product_yaml((product_dir / "config.yaml").read_text(encoding="utf-8"))
    merged = merge_env(product_dir / ".env", {})
    assert resolve_public_api_base_url(parsed, merged) == "https://public.staging.buselsoft.com"


def test_resolve_ui_base_url_for_gold(tmp_path: Path) -> None:
    product_dir = _product_dir(
        tmp_path,
        env=(
            "UPSERVICE_ENV=gold\n"
            "UPSERVICE_GOLD_UI_BASE_URL=https://app.gold.buselsoft.com\n"
        ),
    )
    parsed = utc.parse_product_yaml((product_dir / "config.yaml").read_text(encoding="utf-8"))
    merged = merge_env(product_dir / ".env", {})
    assert resolve_ui_base_url(parsed, merged) == "https://app.gold.buselsoft.com"


def test_resolve_token_uses_employee_key(tmp_path: Path) -> None:
    product_dir = _product_dir(
        tmp_path,
        env="UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN=employee-token\n",
    )
    parsed = utc.parse_product_yaml((product_dir / "config.yaml").read_text(encoding="utf-8"))
    merged = merge_env(product_dir / ".env", {})
    token, token_env = resolve_public_api_token(product_dir, parsed, merged)
    assert token == "employee-token"
    assert token_env == "UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN"


def test_public_get_uses_stage_env(tmp_path: Path) -> None:
    products = tmp_path / "products"
    products.mkdir()
    _product_dir(
        products,
        env=(
            "UPSERVICE_ENV=stage\n"
            "UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN=employee-token\n"
            "UPSERVICE_STAGE_PUBLIC_API_BASE_URL=https://public.staging.buselsoft.com/\n"
        ),
    )
    calls: list[str] = []

    def http_get(
        url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, str, dict[str, str]]:
        calls.append(url)
        return 200, "{}", {}

    result = utc.get_task("1", products_root=products, environ={}, http_get=http_get)
    assert result["status_code"] == 200
    assert calls == ["https://public.staging.buselsoft.com/v1/tasks/1"]


def test_resolve_ui_credentials(tmp_path: Path) -> None:
    product_dir = _product_dir(
        tmp_path,
        env=(
            "UPSERVICE_ENV=stage\n"
            "UPSERVICE_STAGE_UI_EMAIL=user@example.com\n"
            "UPSERVICE_STAGE_UI_PASSWORD=secret\n"
        ),
    )
    merged = merge_env(product_dir / ".env", {})
    email, password, email_env, password_env = resolve_ui_credentials(product_dir, merged)
    assert email == "user@example.com"
    assert password == "secret"
    assert email_env == "UPSERVICE_STAGE_UI_EMAIL"
    assert password_env == "UPSERVICE_STAGE_UI_PASSWORD"


def test_resolve_product_connection_includes_ui_credentials(tmp_path: Path) -> None:
    product_dir = _product_dir(
        tmp_path,
        env=(
            "UPSERVICE_ENV=gold\n"
            "UPSERVICE_GOLD_PUBLIC_API_BASE_URL=https://public.gold.buselsoft.com/\n"
            "UPSERVICE_GOLD_API_BASE_URL=https://api.gold.buselsoft.com\n"
            "UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN=employee-token\n"
            "UPSERVICE_GOLD_UI_BASE_URL=https://app.gold.buselsoft.com\n"
            "UPSERVICE_GOLD_UI_EMAIL=user@example.com\n"
            "UPSERVICE_GOLD_UI_PASSWORD=secret\n"
        ),
    )
    resolved = resolve_product_connection(product_dir, environ={})
    assert resolved["env"] == "gold"
    assert resolved["public_api"]["base_url"] == "https://public.gold.buselsoft.com"
    assert resolved["public_api"]["token_set"] is True
    assert resolved["api"]["base_url"] == "https://api.gold.buselsoft.com"
    assert resolved["ui"]["base_url"] == "https://app.gold.buselsoft.com"
    assert resolved["ui"]["credentials_set"] is True
