#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

export PATH="${HOME}/.local/share/mise/shims:${HOME}/.local/bin:${PATH}"

pick_bin() {
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/$1" ]]; then
    echo "${VIRTUAL_ENV}/bin/$1"
    return
  fi
  if [[ -x .venv-work/bin/$1 ]]; then
    echo ".venv-work/bin/$1"
    return
  fi
  if [[ -x .venv/bin/$1 ]]; then
    echo ".venv/bin/$1"
    return
  fi
  echo "uv"
}

RUFF="$(pick_bin ruff)"
PYTEST="$(pick_bin pytest)"

echo "==> ruff"
if [[ "$RUFF" == "uv" ]]; then
  uv run ruff check src tests
else
  "$RUFF" check src tests
fi

echo "==> pytest"
if [[ "$PYTEST" == "uv" ]]; then
  uv run pytest
else
  "$PYTEST"
fi

echo "==> gate ok"
