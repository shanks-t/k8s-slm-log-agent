#!/usr/bin/env bash
# Create Grafana dashboard ConfigMap from exported JSON
# Takes dashboard name as argument and reads from tmp/dashboard.json in repo root

set -euo pipefail

# Check if name argument provided
if [ $# -ne 1 ]; then
    echo "❌ Error: Dashboard name required"
    echo ""
    echo "Usage: just dashboard-cm <name>"
    echo ""
    echo "Example: just dashboard-cm kubernetes"
    exit 1
fi

name="$1"

# Validate input file exists (relative to repo root)
dashboard_file="tmp/dashboard.json"
if [ ! -f "${dashboard_file}" ]; then
    echo "❌ Error: ${dashboard_file} not found"
    echo ""
    echo "Please export your dashboard from Grafana:"
    echo "  1. Open dashboard in Grafana UI"
    echo "  2. Click Settings (gear icon)"
    echo "  3. Go to JSON Model"
    echo "  4. Copy all JSON (Cmd+A, Cmd+C)"
    echo "  5. Paste into ${dashboard_file}"
    echo ""
    exit 1
fi

# Validate JSON is valid
if ! jq empty "${dashboard_file}" 2>/dev/null; then
    echo "❌ Error: ${dashboard_file} is not valid JSON"
    echo "Please check the file contents"
    exit 1
fi

# Set variables
cm_name="grafana-dashboard-${name}"
output_dir="infrastructure/logging/dashboards"
output_file="${output_dir}/${name}-configmap.yaml"

# Create output directory if it doesn't exist
mkdir -p "${output_dir}"

echo "Creating ConfigMap '${cm_name}'..."

# Create base ConfigMap from JSON file
kubectl create configmap "${cm_name}" \
    --from-file="${name}-dashboard.json=${dashboard_file}" \
    --namespace=logging \
    --dry-run=client -o yaml > /tmp/cm-base.yaml

# Add the grafana_dashboard label using awk
# This label is required for the Grafana sidecar to discover the dashboard
awk '
/^metadata:/ {
    print;
    print "  labels:";
    print "    grafana_dashboard: \"1\"";
    next;
}
{ print }
' /tmp/cm-base.yaml > /tmp/cm-labeled.yaml

# Add header comments and write to final location
cat > "${output_file}" << EOF
---
# Grafana Dashboard ConfigMap: ${name}
# Auto-generated from Grafana UI export
#
# This dashboard is automatically loaded by the Grafana sidecar container.
# The 'grafana_dashboard: "1"' label enables automatic discovery.
#
# To update this dashboard:
#   1. Edit in Grafana UI
#   2. Export JSON to tmp/dashboard.json
#   3. Run: just dashboard-cm ${name}
#   4. Apply: kubectl apply -f ${output_file}
#   5. Commit to Git for persistence
EOF
cat /tmp/cm-labeled.yaml >> "${output_file}"

# Validate the generated ConfigMap
if kubectl apply -f "${output_file}" --dry-run=server &>/dev/null; then
    echo "✅ ConfigMap created: ${output_file}"
    echo ""
    echo "Dashboard info:"
    jq -r '.title // "Unknown"' "${dashboard_file}" | sed 's/^/  Title: /'
    jq -r '.uid // "Unknown"' "${dashboard_file}" | sed 's/^/  UID: /'
    wc -l "${output_file}" | awk '{print "  Size: " $1 " lines"}'
    echo ""
    echo "Next steps:"
    echo "  1. Test: kubectl apply -f ${output_file}"
    echo "  2. Verify in Grafana UI (wait ~10s for sidecar reload)"
    echo "  3. Commit: git add ${output_file} && git commit -m 'feat: add ${name} dashboard'"
else
    echo "❌ Error: Generated ConfigMap failed validation"
    echo "Check ${output_file} for issues"
    exit 1
fi

# Cleanup temp files
rm -f /tmp/cm-base.yaml /tmp/cm-labeled.yaml
