# Product connection

v1: exactly one directory here, named `<product-id>` (`[a-z0-9-]+`).

1. Copy `docs/examples/product-config.yaml` to `products/<product-id>/config.yaml`.
2. Set `id` to the same folder name.
3. Put secrets in `products/<product-id>/.env` (gitignored) and/or Cursor MCP settings.
4. Never put tokens into `config.yaml` values or into `memory/`.

Zero product folders: coordinator must stop and ask for id + public API base URL.
More than one folder: coordinator must stop and ask which id.
