from __future__ import annotations

import sys
from pathlib import Path

try:
    from mcp.server.fastmcp import FastMCP  # pyright: ignore[reportMissingImports]
except ImportError:
    from mcp.server.mcpserver import MCPServer as FastMCP

TOOLS_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from upservice_mcp import client  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("upservice")


@mcp.tool()
def get_task(task_id: str | int) -> dict:
    """Fetch one Upservice task by id from the public API.

    Call this instead of constructing GET /v1/tasks/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_task(task_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_project(project_id: str | int) -> dict:
    """Fetch one Upservice project by id from the public API.

    Call this instead of constructing GET /v1/projects/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_project(project_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_sprint(sprint_id: str | int) -> dict:
    """Fetch one Upservice sprint by id from the public API.

    Call this instead of constructing GET /v1/sprints/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_sprint(sprint_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_directory(directory_id: str | int) -> dict:
    """Fetch one Upservice directory by id from the public API.

    Call this instead of constructing GET /v1/directories/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_directory(directory_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def get_directory_record(record_id: str | int) -> dict:
    """Fetch one Upservice directory record by id from the public API.

    Call this instead of constructing GET /v1/directory-records/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_directory_record(record_id, products_root=REPO_ROOT / "products")


@mcp.tool()
def list_tasks(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice tasks from the public API.

    Call this instead of constructing GET /v1/tasks.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_tasks(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_projects(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice projects from the public API.

    Call this instead of constructing GET /v1/projects.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_projects(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_sprints(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice sprints from the public API.

    Call this instead of constructing GET /v1/sprints.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_sprints(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_employees(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice employees from the public API.

    Call this instead of constructing GET /v1/employees.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_employees(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_tags(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice tags from the public API.

    Call this instead of constructing GET /v1/tags.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_tags(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_directories(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice directories from the public API.

    Call this instead of constructing GET /v1/directories.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_directories(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


@mcp.tool()
def list_directory_records(
    limit: int | None = None,
    offset: int | None = None,
    query: dict | None = None,
) -> dict:
    """List Upservice directory records from the public API.

    Call this instead of constructing GET /v1/directory-records.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.list_directory_records(
        limit=limit,
        offset=offset,
        query=query,
        products_root=REPO_ROOT / "products",
    )


if __name__ == "__main__":
    mcp.run()
