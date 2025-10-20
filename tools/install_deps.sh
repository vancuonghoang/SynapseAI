#!/usr/bin/env bash
set -euo pipefail

# This script installs dependencies based on the project type.

cd workspace

if [ -f "pyproject.toml" ]; then
  echo "Installing Python dependencies..."
  pip install ruff black mypy

elif [ -f "package.json" ]; then
  echo "Installing Node.js dependencies..."
  pnpm install

else
  echo "No dependency management file found (pyproject.toml or package.json)."
  exit 0
fi
