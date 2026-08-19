from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

TOOLS_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from testmo_mcp import client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("testmo")


@mcp.tool()
def list_testmo_projects() -> dict:
    """List Testmo projects.

    Returns {"status_code": int, "body": object|str}. Does not write files.
    """

    return client.list_testmo_projects(products_root=REPO_ROOT / "products")


@mcp.tool()
def list_testmo_folders(
    project_id: str | int,
    page: int | None = None,
    per_page: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Testmo folders for a project."""

    return client.list_testmo_folders(
        project_id,
        page=page,
        per_page=per_page,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_testmo_cases(
    project_id: str | int,
    page: int | None = None,
    per_page: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Testmo repository cases for a project."""

    return client.list_testmo_cases(
        project_id,
        page=page,
        per_page=per_page,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_testmo_runs(
    project_id: str | int,
    page: int | None = None,
    per_page: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Testmo runs for a project."""

    return client.list_testmo_runs(
        project_id,
        page=page,
        per_page=per_page,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_testmo_milestones(
    project_id: str | int,
    page: int | None = None,
    per_page: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Testmo milestones for a project."""

    return client.list_testmo_milestones(
        project_id,
        page=page,
        per_page=per_page,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def create_testmo_folders(project_id: str | int, folders: list[dict[str, Any]]) -> dict:
    """Create one or more Testmo folders for a project."""

    return client.create_testmo_folders(
        project_id,
        folders=folders,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def create_testmo_cases(project_id: str | int, cases: list[dict[str, Any]]) -> dict:
    """Create one or more Testmo cases for a project."""

    return client.create_testmo_cases(
        project_id,
        cases=cases,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def create_testmo_runs(project_id: str | int, payload: dict[str, Any]) -> dict:
    """Create one Testmo run for a project."""

    return client.create_testmo_runs(
        project_id,
        payload=payload,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def create_testmo_milestones(project_id: str | int, payload: dict[str, Any]) -> dict:
    """Create one Testmo milestone for a project."""

    return client.create_testmo_milestones(
        project_id,
        payload=payload,
        products_root=REPO_ROOT / "products",
    )


if __name__ == "__main__":
    mcp.run()
