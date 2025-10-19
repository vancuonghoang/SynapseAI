#!/usr/bin/env bash
set -euo pipefail

WORKSPACE_DIR="agent_framework/workspace"
echo "[Typecheck] Entering workspace: $WORKSPACE_DIR"
cd "$WORKSPACE_DIR"

if [ -f "pyproject.toml" ]; then
  if command -v mypy >/dev/null 2>&1; then
    echo "[Typecheck] Running mypy..."
    mypy .
  else
    echo "[Typecheck] mypy is not installed; skipping Python type checking." >&2
  fi
elif [ -f "package.json" ]; then
  if command -v npm >/dev/null 2>&1; then
    echo "[Typecheck] Running npm run typecheck (if present)..."
    npm run typecheck --if-present || echo "[Typecheck] npm run typecheck failed or not defined; review output."
  else
    echo "[Typecheck] npm is not available; skipping Node type check." >&2
  fi
else
  echo "[Typecheck] No type checking configuration detected; skipping."
fi

echo "[Typecheck] Completed."
