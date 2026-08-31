"""Launch figma-developer-mcp with FIGMA_API_KEY from products/upservice/.env."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TOOLS_ROOT = Path(__file__).resolve().parents[1]
if str(TOOLS_ROOT) not in sys.path:
    sys.path.insert(0, str(TOOLS_ROOT))

from upservice_mcp.client import load_token  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = REPO_ROOT / "products" / "upservice" / ".env"
TOKEN_ENV = "FIGMA_API_KEY"


def main() -> int:
    token = load_token(TOKEN_ENV, ENV_FILE, os.environ)
    if not token:
        print(
            f"Missing {TOKEN_ENV} in environment or {ENV_FILE}",
            file=sys.stderr,
        )
        return 1

    env = {**os.environ, TOKEN_ENV: token}
    if sys.platform == "win32":
        cmd = ["cmd", "/c", "npx", "-y", "figma-developer-mcp", "--stdio"]
    else:
        cmd = ["npx", "-y", "figma-developer-mcp", "--stdio"]
    return subprocess.call(cmd, env=env)


if __name__ == "__main__":
    raise SystemExit(main())
