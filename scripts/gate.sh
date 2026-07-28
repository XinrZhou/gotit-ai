#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="${HOME}/.local/share/mise/shims:${HOME}/.local/bin:${PATH}"

echo "==> ruff"
uv run ruff check src tests

echo "==> mypy"
uv run mypy src

echo "==> pytest"
uv run pytest

echo "==> harness (dev case set)"
uv run python scripts/run_harness.py --label gate

echo "==> gate ok"
