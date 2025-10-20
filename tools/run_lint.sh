#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="workspace"
echo "[Linter] Entering workspace: $WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

if [ -f "pyproject.toml" ]; then
  if command -v ruff >/dev/null 2>&1; then
    echo "[Linter] Running ruff check..."
    ruff check .
  else
    echo "[Linter] ruff is not installed; skipping Python lint." >&2
  fi
  if command -v black >/dev/null 2>&1; then
    echo "[Linter] Verifying formatting with black..."
    black --check .
  else
    echo "[Linter] black is not installed; skipping format check." >&2
  fi
  if command -v isort >/dev/null 2>&1; then
    echo "[Linter] Checking import order with isort..."
    isort --check-only .
  else
    echo "[Linter] isort is not installed; skipping import order check." >&2
  fi
elif [ -f "package.json" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[Linter] Running npm run lint (if present)..."
    npm run lint --if-present || echo "[Linter] npm run lint failed or not defined; review output."
  else
    echo "[Linter] npm is not available; skipping Node lint." >&2
  fi
else
  echo "[Linter] No lint configuration detected; skipping."
fi

echo "[Linter] Completed."
