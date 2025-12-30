# Use safer bash shell with pipefail
set shell := ["bash", "-cuo", "pipefail"]

# Variables
dev_pids := ".dev-pids"

# Default recipe runs dev
default: dev

# Start local development environment
#
# Port-forwards Kubernetes services (Loki, LLaMA, Tempo) to localhost,
# then runs FastAPI locally on your Mac with hot-reload enabled.
#
# Network flow: Mac FastAPI → localhost ports → K8s services
# Use case: Local development with fast iteration
# Stop with: Ctrl+C or 'just stop'
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

# Stop all background development processes
#
# Kills port-forward processes started by 'just dev' or 'just dev-k8s'.
# Safe to run even if nothing is running.
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

# Run unit tests with mocked dependencies
#
# Fast tests that don't require Kubernetes services.
# Dependencies are mocked (Loki, LLaMA).
test:
    @echo "Running unit tests..."
    @cd workloads/log-analyzer && uv run pytest -v

# Run integration tests against real Kubernetes services
#
# Requires: 'just dev' running in another terminal
# Tests use real Loki, LLaMA services via port-forward.
test-int:
    @echo "Running integration tests..."
    @cd workloads/log-analyzer && uv run pytest -m integration -v

# Run all tests (unit + integration)
#
# Requires: 'just dev' running in another terminal
test-all:
    @echo "Running all tests..."
    @cd workloads/log-analyzer && uv run pytest -m "" -v


# Test LOCAL FastAPI server with Kubernetes dependencies
#
# Requires: 'just dev' running in another terminal
# Network flow: Mac curl → Mac FastAPI (localhost:8000) → K8s services
# Use case: Test local code changes with real K8s data
#
# Examples:
#   just test-stream llm 30m          # Last 30 minutes of llm namespace
#   just test-stream kube-system 24h  # Last 24 hours of kube-system
test-stream namespace="kube-system" duration="24h":
    @just-helpers/test-stream.sh {{namespace}} {{duration}}

# Port-forward DEPLOYED log-analyzer service to localhost
#
# Makes the Kubernetes-deployed log-analyzer accessible at localhost:8000.
# FastAPI runs IN Kubernetes, not on your Mac.
# Keeps port-forward open until you press Ctrl+C.
#
# Network flow: Mac → localhost:8000 → port-forward → K8s log-analyzer
# Use case: Interactive debugging, multiple manual curl requests
# Note: For one-off tests, use 'just test-k8s-local' (auto-cleanup)
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
#
# Stops port-forward created by 'just dev-k8s'.
# Safe to run even if nothing is running.
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

# Test DEPLOYED log-analyzer with end-to-end Kubernetes networking
#
# Creates a temporary curl pod INSIDE Kubernetes to test the service.
# Tests full production-like path: K8s DNS, ClusterIP, network policies.
#
# Network flow: curl pod (in K8s) → K8s service DNS → log-analyzer pod
# Use case: Validate deployment, pre-commit checks, CI/CD
# Note: Slower (~5-10s) due to pod creation/deletion
#
# Examples:
#   just test-k8s llm                      # Last 1 hour (default)
#   just test-k8s llm 30m                  # Last 30 minutes
#   just test-k8s namespace=llm duration=24h
test-k8s namespace="log-analyzer" duration="1h":
    @just-helpers/test-k8s.sh {{namespace}} {{duration}}

# Test DEPLOYED log-analyzer via port-forward from your Mac
#
# Self-contained: Sets up port-forward, runs test, cleans up automatically.
# Network flow: Mac curl → localhost:8000 → port-forward → K8s log-analyzer
# Use case: Quick testing of deployed service without manual port-forward management
#
# Examples:
#   just test-k8s-local llm                      # Last 1 hour (default)
#   just test-k8s-local llm 30m                  # Last 30 minutes
#   just test-k8s-local namespace=llm duration=24h
test-k8s-local namespace="log-analyzer" duration="1h":
    @just-helpers/test-k8s-local.sh {{namespace}} {{duration}}

# Evaluate log-analyzer by comparing LLM analysis with raw Loki logs
#
# Queries both log-analyzer (LLM analysis) and Loki (raw logs) with identical
# parameters, then saves outputs side-by-side for human or agent evaluation.
#
# Output: Creates tmp/evaluation-<timestamp>.json with:
#   - query_params: The query used
#   - llm_analysis: Just the LLM analysis text (from /v1/analyze endpoint)
#   - raw_logs: What Loki returned (same query)
#   - metadata: Timestamp, namespace, duration
#   - comparison: Metrics for evaluation (log count, error detection, etc.)
#
# Use case: Validate LLM analysis quality, find missed logs, tune prompts
#
# Examples:
#   just evaluate llm 30m              # Evaluate last 30 min of llm namespace
#   just evaluate kube-system 1h       # Evaluate last 1 hour
evaluate namespace="log-analyzer" duration="1h":
    @uv run python just-helpers/evaluate.py {{namespace}} {{duration}}

# Build log-analyzer Docker image for linux/amd64
#
# Builds the container image locally using the Dockerfile in workloads/log-analyzer.
# Tags with both 'latest' and git commit SHA for versioning.
#
# Requires: .env file with GITHUB_USER defined
# Output: ghcr.io/${GITHUB_USER}/log-analyzer:latest and :${GIT_SHA}
build:
    @just-helpers/build.sh

# Push log-analyzer image to GitHub Container Registry
#
# Authenticates with ghcr.io using GHCR_TOKEN from .env, then pushes
# both the :latest and :${GIT_SHA} tagged images.
#
# Requires: .env file with GITHUB_USER and GHCR_TOKEN
# Requires: 'just build' to have been run first
push:
    @just-helpers/push.sh

# Deploy log-analyzer to Kubernetes via Flux
#
# Updates the deployment image to use the latest SHA, commits to Git,
# and triggers Flux reconciliation.
#
# Requires: .env file with GITHUB_USER
# Workflow: Updates deployment.yaml → git commit → git push → flux reconcile
deploy:
    @just-helpers/deploy.sh

# Build, push, and deploy log-analyzer (full release workflow)
#
# Runs the complete workflow: build → push to ghcr.io → deploy via Flux
#
# Use case: Release a new version of log-analyzer
# Example: just release
release: build push deploy
    @echo ""
    @echo "✓ Release complete!"
    @echo "Monitor deployment: kubectl get pods -n log-analyzer -w"
