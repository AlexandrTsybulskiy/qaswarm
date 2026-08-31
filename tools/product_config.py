from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

VALID_ENVS = frozenset({"prod", "stage", "gold"})
ENV_VAR = "UPSERVICE_ENV"


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


def parse_dotenv(env_file: Path) -> dict[str, str]:
    if not env_file.is_file():
        return {}
    values: dict[str, str] = {}
    for raw in env_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if not key:
            continue
        values[key] = val.strip().strip("'").strip('"')
    return values


def merge_env(env_file: Path, environ: Mapping[str, str]) -> dict[str, str]:
    merged = parse_dotenv(env_file)
    merged.update({key: value for key, value in environ.items() if value})
    return merged


def active_env_name(merged: Mapping[str, str], *, default: str = "prod") -> str:
    raw = merged.get(ENV_VAR, default).strip().lower()
    if raw in VALID_ENVS:
        return raw
    return default


def _env_prefix(env_name: str) -> str:
    return f"UPSERVICE_{env_name.upper()}_"


def resolve_public_api_base_url(parsed: Mapping[str, Any], merged: Mapping[str, str]) -> str:
    env_name = active_env_name(merged)
    prefixed = merged.get(f"{_env_prefix(env_name)}PUBLIC_API_BASE_URL", "").strip()
    if prefixed:
        return prefixed.rstrip("/")
    public = parsed.get("public_api")
    if isinstance(public, dict):
        fallback = str(public.get("base_url", "")).strip()
        if fallback:
            return fallback.rstrip("/")
    return ""


def resolve_ui_base_url(parsed: Mapping[str, Any], merged: Mapping[str, str]) -> str | None:
    env_name = active_env_name(merged)
    prefixed = merged.get(f"{_env_prefix(env_name)}UI_BASE_URL", "").strip()
    if prefixed:
        return prefixed.rstrip("/")
    ui = parsed.get("ui")
    if isinstance(ui, dict):
        fallback = str(ui.get("base_url", "")).strip()
        if fallback:
            return fallback.rstrip("/")
    root_ui = parsed.get("ui.base_url")
    if isinstance(root_ui, str) and root_ui.strip():
        return root_ui.strip().rstrip("/")
    return None


def resolve_env_value(merged: Mapping[str, str], suffix: str) -> str | None:
    env_name = active_env_name(merged)
    value = merged.get(f"{_env_prefix(env_name)}{suffix}", "").strip()
    if value:
        return value.rstrip("/")
    return None


def resolve_api_base_url(merged: Mapping[str, str]) -> str | None:
    return resolve_env_value(merged, "API_BASE_URL")


def resolve_token_env_key(parsed: Mapping[str, Any]) -> str:
    config_token_env = "UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN"
    public = parsed.get("public_api")
    if isinstance(public, dict):
        configured = str(public.get("token_env", "")).strip()
        if configured:
            config_token_env = configured
    return config_token_env


def resolve_public_api_token(
    product_dir: Path,
    parsed: Mapping[str, Any],
    merged: Mapping[str, str],
) -> tuple[str | None, str]:
    token_env = resolve_token_env_key(parsed)
    token = load_token(token_env, product_dir / ".env", merged)
    return token, token_env


def resolve_ui_credentials(
    product_dir: Path,
    merged: Mapping[str, str],
) -> tuple[str | None, str | None, str, str]:
    env_name = active_env_name(merged)
    email_env = f"{_env_prefix(env_name)}UI_EMAIL"
    password_env = f"{_env_prefix(env_name)}UI_PASSWORD"
    env_file = product_dir / ".env"
    email = load_token(email_env, env_file, merged)
    password = load_token(password_env, env_file, merged)
    return email, password, email_env, password_env


def resolve_product_connection(
    product_dir: Path,
    parsed: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    env = dict(environ) if environ is not None else dict(__import__("os").environ)
    config_path = product_dir / "config.yaml"
    if parsed is None:
        if not config_path.is_file():
            raise FileNotFoundError(f"missing product config: {config_path}")
        parsed = parse_product_yaml(config_path.read_text(encoding="utf-8"))
    merged = merge_env(product_dir / ".env", env)
    env_name = active_env_name(merged)
    token, token_env = resolve_public_api_token(product_dir, parsed, merged)
    email, password, email_env, password_env = resolve_ui_credentials(product_dir, merged)
    api_base_url = resolve_api_base_url(merged)
    return {
        "env": env_name,
        "public_api": {
            "base_url": resolve_public_api_base_url(parsed, merged),
            "token_env": token_env,
            "token_set": bool(token),
        },
        "api": {
            "base_url": api_base_url,
        },
        "ui": {
            "base_url": resolve_ui_base_url(parsed, merged),
            "email_env": email_env,
            "password_env": password_env,
            "credentials_set": bool(email and password),
        },
    }


def format_connection_report(resolved: Mapping[str, Any]) -> str:
    ui_base = resolved["ui"]["base_url"]
    lines = [
        f"env: {resolved['env']}",
        f"public_api.base_url: {resolved['public_api']['base_url']}/",
        f"public_api.token_env: {resolved['public_api']['token_env']}",
        f"public_api.token: {'set' if resolved['public_api']['token_set'] else 'missing'}",
    ]
    api_base = resolved.get("api", {}).get("base_url")
    if api_base:
        lines.append(f"api.base_url: {api_base}/")
    if ui_base:
        lines.append(f"ui.base_url: {ui_base}/")
    else:
        lines.append("ui.base_url: (not set)")
    lines.append(f"ui.email_env: {resolved['ui']['email_env']}")
    lines.append(f"ui.password_env: {resolved['ui']['password_env']}")
    lines.append(
        f"ui.credentials: {'set' if resolved['ui']['credentials_set'] else 'missing'}"
    )
    return "\n".join(lines)
