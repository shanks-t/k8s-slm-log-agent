#!/usr/bin/env bash
# Deploy log-analyzer to Kubernetes via Flux
# Updates deployment image, commits to Git, and triggers Flux reconciliation

set -euo pipefail

# Load environment variables
if [ ! -f .env ]; then
    echo "Error: .env file not found"
    exit 1
fi
source .env

if [ -z "${GITHUB_USER:-}" ]; then
    echo "Error: GITHUB_USER not set in .env"
    exit 1
fi

GIT_SHA=$(git rev-parse --short HEAD)
NEW_IMAGE="ghcr.io/${GITHUB_USER}/log-analyzer:${GIT_SHA}"

echo "Updating deployment to use ${NEW_IMAGE}..."

# Update the image in deployment.yaml
sed -i.bak "s|image: ghcr.io/.*/log-analyzer:.*|image: ${NEW_IMAGE}|" \
    workloads/log-analyzer/deployment.yaml
rm -f workloads/log-analyzer/deployment.yaml.bak

# Check if there are changes to commit
if git diff --quiet workloads/log-analyzer/deployment.yaml; then
    echo "No changes to deployment.yaml (already using ${NEW_IMAGE})"
else
    echo "Committing deployment update..."
    git add workloads/log-analyzer/deployment.yaml
    git commit -m "chore: update log-analyzer image to ${GIT_SHA}"

    echo "Pushing to remote..."
    git push
fi

echo "Triggering Flux reconciliation..."
flux reconcile source git flux-system
flux reconcile kustomization workloads

echo "✓ Deployment updated and reconciled"
echo "Check status with: kubectl get pods -n log-analyzer"
