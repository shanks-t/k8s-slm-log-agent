# Use safer bash shell with pipefail
set shell := ["bash", "-cuo", "pipefail"]

# Variables
dev_pids := ".dev-pids"

# Default recipe runs dev
default: dev

# Start the development environment
dev: stop
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Starting Loki port-forward..."
    # Run in background, redirect stdout to suppress spam, keep stderr for errors
    kubectl port-forward -n logging svc/loki 3100:3100 > /dev/null 2>&1 &
    # Save PID to file
    echo $! >> {{dev_pids}}

    echo "Starting LLaMA port-forward..."
    kubectl port-forward -n llm svc/llama-cpp 8080:8080 > /dev/null 2>&1 &
    echo $! >> {{dev_pids}}

    echo "Starting Tempo port-forward..."
    kubectl port-forward -n logging svc/tempo 4317:4317 3200:3200 > /dev/null 2>&1 &
    echo $! >> {{dev_pids}}

    echo "Waiting for dependencies..."
    helpers/wait-for.sh http://localhost:3100/ready
    helpers/wait-for.sh http://localhost:8080/v1/models
    helpers/wait-for.sh http://localhost:3200/ready

    echo "Starting FastAPI..."
    # When script exits (including ctrl-c), run 'just stop' for clean shutdown
    trap 'just stop' EXIT
    cd workloads/log-analyzer
    uv run fastapi dev src/log_analyzer/main.py

# Stop all dev processes
stop:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Stopping dev processes..."
    # If PID file exists, kill the PIDs listed in it
    if [ -f {{dev_pids}} ]; then
        while read -r pid; do
            # Check if process exists before killing
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < {{dev_pids}}
    fi
    # Remove runtime state
    rm -f {{dev_pids}}

# Run unit tests (fast, mocked dependencies)
test:
    @echo "Running unit tests..."
    @cd workloads/log-analyzer && uv run pytest -v

# Run integration tests (requires services running via 'just dev')
test-int:
    @echo "Running integration tests..."
    @cd workloads/log-analyzer && uv run pytest -m integration -v

# Run all tests (unit + integration)
test-all:
    @echo "Running all tests..."
    @cd workloads/log-analyzer && uv run pytest -m "" -v

# Test the streaming analyze endpoint with optional namespace filter (local dev)
test-stream namespace="kube-system":
    #!/usr/bin/env bash
    set -euo pipefail

    START=$(date -u -v-24H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ)
    END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    curl -N -X POST http://127.0.0.1:8000/v1/analyze/stream \
      -H "Content-Type: application/json" \
      -d "{
        \"time_range\": {
          \"start\": \"$START\",
          \"end\": \"$END\"
        },
        \"filters\": {
          \"namespace\": \"{{namespace}}\"
        },
        \"limit\": 2
      }"

# Port-forward log-analyzer service from Kubernetes
dev-k8s: stop-k8s
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Starting log-analyzer port-forward from Kubernetes..."
    kubectl port-forward -n log-analyzer svc/log-analyzer 8000:8000 > /dev/null 2>&1 &
    echo $! >> {{dev_pids}}

    echo "Waiting for log-analyzer..."
    helpers/wait-for.sh http://localhost:8000/health

    echo "✓ log-analyzer is ready at http://localhost:8000"
    echo "Press Ctrl+C to stop port-forwarding"

    # Keep the script running and cleanup on exit
    trap 'just stop-k8s' EXIT
    wait

# Stop Kubernetes port-forwards
stop-k8s:
    #!/usr/bin/env bash
    set -euo pipefail

    echo "Stopping Kubernetes port-forwards..."
    if [ -f {{dev_pids}} ]; then
        while read -r pid; do
            if kill -0 "$pid" 2>/dev/null; then
                kill "$pid" 2>/dev/null || true
            fi
        done < {{dev_pids}}
    fi
    rm -f {{dev_pids}}

# Test the Kubernetes-deployed log-analyzer service
test-k8s namespace="log-analyzer":
    #!/usr/bin/env bash
    set -euo pipefail

    START=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
    END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    echo "Testing log-analyzer in Kubernetes (namespace: {{namespace}})..."

    # Test via kubectl run to call from inside the cluster
    kubectl run test-log-analyzer --rm -i --tty --image=curlimages/curl --restart=Never -- \
      curl -N -X POST "http://log-analyzer.log-analyzer.svc.cluster.local:8000/v1/analyze/stream" \
      -H "Content-Type: application/json" \
      -d "{
        \"time_range\": {
          \"start\": \"$START\",
          \"end\": \"$END\"
        },
        \"filters\": {
          \"namespace\": \"{{namespace}}\"
        },
        \"limit\": 15
      }"

# Test the Kubernetes service via port-forward (requires 'just dev-k8s' running)
test-k8s-local namespace="log-analyzer":
    #!/usr/bin/env bash
    set -euo pipefail

    START=$(date -u -v-1H +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%SZ)
    END=$(date -u +%Y-%m-%dT%H:%M:%SZ)

    curl -N -X POST http://127.0.0.1:8000/v1/analyze/stream \
      -H "Content-Type: application/json" \
      -d "{
        \"time_range\": {
          \"start\": \"$START\",
          \"end\": \"$END\"
        },
        \"filters\": {
          \"namespace\": \"{{namespace}}\"
        },
        \"limit\": 15
      }"
