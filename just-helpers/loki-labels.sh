#!/usr/bin/env bash
# Discover available Loki labels and their values
# Useful for understanding what labels you can filter on
set -euo pipefail

echo "=== Loki Label Discovery ==="
echo ""

echo "📋 All available labels:"
curl -s "http://localhost:3100/loki/api/v1/labels" | jq -r '.data[]' | sort

echo ""
echo "Example values for common labels:"
echo ""

echo "📦 Namespaces:"
curl -s "http://localhost:3100/loki/api/v1/label/namespace/values" | jq -r '.data[]' | sort | head -10

echo ""
echo "🏷️  Containers:"
curl -s "http://localhost:3100/loki/api/v1/label/container/values" | jq -r '.data[]' | sort | head -10

echo ""
echo "🖥️  Nodes:"
curl -s "http://localhost:3100/loki/api/v1/label/node/values" | jq -r '.data[]' | sort | head -10

echo ""
echo "💡 Tip: Use these labels in your LogQL queries"
echo "   Example: {namespace=\"llm\",container=\"llama-cpp\"}"
