#!/usr/bin/env bash
# Evaluate log-analyzer by comparing LLM analysis with raw Loki logs
set -euo pipefail

NAMESPACE="$1"
DURATION="$2"

# Calculate time range
source helpers/calc-time-range.sh "$DURATION"

# Create output file with timestamp
TIMESTAMP=$(date -u +%Y%m%d-%H%M%S)
OUTPUT_FILE="/tmp/evaluation-${TIMESTAMP}.json"

echo "=========================================="
echo "Evaluation Run"
echo "=========================================="
echo "Namespace:   $NAMESPACE"
echo "Duration:    $DURATION"
echo "Time Range:  $START → $END"
echo "Output:      $OUTPUT_FILE"
echo ""

# Start port-forwards
echo "Setting up port-forwards..."
kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000 > /dev/null 2>&1 &
PF_ANALYZER_PID=$!
kubectl port-forward -n logging svc/loki 3100:3100 > /dev/null 2>&1 &
PF_LOKI_PID=$!

# Ensure cleanup on exit
trap "echo 'Cleaning up port-forwards...'; kill $PF_ANALYZER_PID $PF_LOKI_PID 2>/dev/null || true" EXIT

# Wait for services to be ready
echo "Waiting for services..."
helpers/wait-for.sh http://localhost:8000/health
helpers/wait-for.sh http://localhost:3100/ready

# Query log-analyzer (LLM analysis)
echo ""
echo "1. Querying log-analyzer (LLM analysis)..."
LLM_OUTPUT=$(mktemp)
curl -s -N -X POST http://127.0.0.1:8000/v1/analyze/stream \
  -H "Content-Type: application/json" \
  -d "{
    \"time_range\": {
      \"start\": \"$START\",
      \"end\": \"$END\"
    },
    \"filters\": {
      \"namespace\": \"$NAMESPACE\"
    },
    \"limit\": 15
  }" > "$LLM_OUTPUT"

# Query Loki directly (raw logs)
echo "2. Querying Loki (raw logs)..."
LOKI_OUTPUT=$(mktemp)

# Convert timestamps to nanoseconds
START_NS=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$START" +%s 2>/dev/null || date -u -d "$START" +%s)000000000
END_NS=$(date -u -j -f "%Y-%m-%dT%H:%M:%SZ" "$END" +%s 2>/dev/null || date -u -d "$END" +%s)000000000

# Query Loki with same filters
curl -s -G "http://localhost:3100/loki/api/v1/query_range" \
  --data-urlencode "query={namespace=\"$NAMESPACE\",container!=\"loki\"}" \
  --data-urlencode "start=${START_NS}" \
  --data-urlencode "end=${END_NS}" \
  --data-urlencode "limit=15" \
  --data-urlencode "direction=backward" > "$LOKI_OUTPUT"

# Create combined evaluation file
echo "3. Creating evaluation file..."

# Export variables for Python script
export LLM_FILE="$LLM_OUTPUT"
export LOKI_FILE="$LOKI_OUTPUT"
export EVAL_FILE="$OUTPUT_FILE"
export EVAL_TIMESTAMP="$TIMESTAMP"
export EVAL_NAMESPACE="$NAMESPACE"
export EVAL_DURATION="$DURATION"
export EVAL_START="$START"
export EVAL_END="$END"

# Run evaluation script
python3 helpers/create_evaluation.py

# Display quick preview
echo ""
echo "=========================================="
echo "Quick Preview"
echo "=========================================="
echo ""
echo "LLM Analysis (first 500 chars):"
head -c 500 "$LLM_OUTPUT"
echo ""
echo ""
echo "Raw Log Count:"
python3 -c "import json; data=json.load(open('$LOKI_OUTPUT')); print(f\"  {sum(len(s.get('values', [])) for s in data.get('data', {}).get('result', []))} log entries\")"
echo ""
echo "=========================================="
echo "Full evaluation saved to:"
echo "$OUTPUT_FILE"
echo "=========================================="
echo ""
echo "To review:"
echo "  cat $OUTPUT_FILE | jq ."
echo ""
echo "To compare with agent:"
echo "  # (Future: 'just evaluate-compare $OUTPUT_FILE')"

# Cleanup temp files
rm -f "$LLM_OUTPUT" "$LOKI_OUTPUT"

# Trap will handle port-forward cleanup
