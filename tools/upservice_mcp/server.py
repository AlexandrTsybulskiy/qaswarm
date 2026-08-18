from __future__ import annotations

from pathlib import Path

from mcp.server.mcpserver import MCPServer as FastMCP

from upservice_mcp import client

REPO_ROOT = Path(__file__).resolve().parents[2]

mcp = FastMCP("upservice")


@mcp.tool()
def get_task(task_id: str) -> dict:
    """Fetch one Upservice task by id from the public API.

    Call this instead of constructing GET /v1/tasks/{id}.
    Returns {"status_code": int, "body": object|str}. Does not write files.
    429 is retried inside the tool.
    """
    return client.get_task(task_id, products_root=REPO_ROOT / "products")


if __name__ == "__main__":
    mcp.run()
