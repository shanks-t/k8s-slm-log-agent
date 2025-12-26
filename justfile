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

    echo "Waiting for dependencies..."
    helpers/wait-for.sh http://localhost:3100/ready
    helpers/wait-for.sh http://localhost:8080/v1/models

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
