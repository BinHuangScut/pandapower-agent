#!/usr/bin/env bash
set -euo pipefail

# Demo flow: discover network -> run checks -> run AI analysis -> export artifacts
# Usage:
#   OPENAI_API_KEY=... scripts/demo_flow.sh
#   GOOGLE_API_KEY=... LLM_PROVIDER=google scripts/demo_flow.sh

echo "[1/6] List networks"
agent networks --query case --max 5

echo "[2/6] Switch network"
agent use case14

echo "[3/6] Local tool-only checks (no API key required)"
agent tools --format table
agent doctor --format table

if [[ -n "${OPENAI_API_KEY:-}" || -n "${GOOGLE_API_KEY:-}" ]]; then
  echo "[4/6] Run one natural-language analysis"
  agent run "run AC power flow and summarize voltage and loading risks"

  echo "[5/6] Export machine-readable output"
  agent export --type summary --path ./outputs/summary.json
else
  echo "[4/6] Skip agent run (no API key provided)."
fi

echo "[6/6] Export network plot"
agent plot-network --path ./outputs/network_plot.png

echo "Demo complete."
