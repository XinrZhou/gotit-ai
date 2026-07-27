#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="${HOME}/.local/share/mise/shims:${HOME}/.local/bin:${PATH}"

echo "==> ruff"
uv run ruff check src tests

echo "==> pytest"
uv run pytest

echo "==> gate ok"
