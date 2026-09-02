# Product connection

v1: exactly one directory here, named `<product-id>` (`[a-z0-9-]+`).

1. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`.
2. Set `id` to the same folder name.
3. Put secrets in `products/<product-id>/.env` (gitignored) and/or Cursor MCP settings.
4. Never put tokens into `config.yaml` values or into `memory/`.

## Multi-environment (Upservice)

Set `UPSERVICE_ENV=prod|stage|gold` in `products/upservice/.env` and define per-env keys (URLs from `upservice_playwright_testing/.env`):

- `UPSERVICE_{ENV}_PUBLIC_API_BASE_URL`
- `UPSERVICE_{ENV}_API_BASE_URL`
- `UPSERVICE_{ENV}_UI_BASE_URL`
- `UPSERVICE_{ENV}_API_TAG_URL`
- `UPSERVICE_{ENV}_MESSENGER_API_URL`
- `UPSERVICE_{ENV}_STORAGE_BASE_URL`
- `UPSERVICE_{ENV}_UI_EMAIL`
- `UPSERVICE_{ENV}_UI_PASSWORD`

Workspace employee public API token (one for all envs):

- `UPSERVICE_EMPLOYEE_PUBLIC_API_TOKEN`

`config.yaml` keeps prod defaults as fallback. Effective settings:

`py -3 tools/product_env.py products/upservice`

## Code repos (multi-root)

Point `code.frontend` and `code.backend` at cloned repos (see `../upservice.code-workspace`):

`py -3 tools/code_roots.py products/upservice`

Optional env overrides: `UPSERVICE_FRONTEND_ROOT`, `UPSERVICE_BACKEND_ROOT` via `code.frontend_env` / `code.backend_env`.

Zero product folders: coordinator must stop and ask for id + public API base URL.
More than one folder: coordinator must stop and ask which id.
