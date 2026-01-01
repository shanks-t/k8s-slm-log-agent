#!/usr/bin/env bash
# Quick curl to local /v1/analyze endpoint (JSON response)
# Simpler than analyze.sh - uses current time with configurable lookback
set -euo pipefail

NAMESPACE="${1:-llm}"
SEVERITY="${2:-error}"
LOOKBACK="${3:-30m}"

# Calculate time range
source just-helpers/calc-time-range.sh "$LOOKBACK"

echo "🔍 Analyzing $NAMESPACE namespace (severity: $SEVERITY, last $LOOKBACK)"
echo ""

curl -s -X POST http://localhost:8000/v1/analyze \
  -H "Content-Type: application/json" \
  -d "{
    \"time_range\": {
      \"start\": \"$START\",
      \"end\": \"$END\"
    },
    \"filters\": {
      \"namespace\": \"$NAMESPACE\",
      \"severity\": \"$SEVERITY\"
    },
    \"limit\": 15
  }" | jq .
