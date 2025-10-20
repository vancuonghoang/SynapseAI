#!/usr/bin/env bash
set -euo pipefail

# Simple wrapper to run a freqtrade backtest in a consistent way.
# Usage:
#   bash agent_framework/tools/run_backtest.sh [StrategyName] [timeframe] [timerange]
# Defaults:
#   StrategyName = SampleStrategy
#   timeframe    = 5m
#   timerange    = 20240101-

STRATEGY="${1:-SampleStrategy}"
TIMEFRAME="${2:-5m}"
TIMERANGE="${3:-20240101-}"
CONFIG_PATH="${CONFIG:-user_data/config.example.json}"

if ! command -v freqtrade >/dev/null 2>&1; then
  echo "[Backtest] 'freqtrade' CLI not found. Skipping backtest."
  echo "[Backtest] Install with: pipx install freqtrade or refer to project docs."
  exit 0
fi

if [ ! -f "$CONFIG_PATH" ]; then
  echo "[Backtest] Config file '$CONFIG_PATH' not found."
  echo "[Backtest] Provide a valid config via env CONFIG=/path/to/config.json"
  exit 1
fi

echo "[Backtest] Running backtest: strategy=$STRATEGY timeframe=$TIMEFRAME timerange=$TIMERANGE"
freqtrade backtesting \
  --strategy "$STRATEGY" \
  --config "$CONFIG_PATH" \
  --timeframe "$TIMEFRAME" \
  --timerange "$TIMERANGE" \
  --export trades \
  --export-filename "backtest_${STRATEGY}_${TIMEFRAME}.json"

echo "[Backtest] Completed. Results exported to backtest_${STRATEGY}_${TIMEFRAME}.json"

