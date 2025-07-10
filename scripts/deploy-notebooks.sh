#!/bin/bash

# Deploy notebooks script - automatically uses current branch
# Usage: ./scripts/deploy-notebooks.sh [environment] [setup_infrastructure]

set -e

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
ENVIRONMENT=${1:-development}
SETUP_INFRASTRUCTURE=${2:-false}

echo "🚀 Deploying notebooks..."
echo "  Branch: $CURRENT_BRANCH"
echo "  Environment: $ENVIRONMENT"
echo "  Setup Infrastructure: $SETUP_INFRASTRUCTURE"
echo ""

# Check if we're on a valid branch
if [ -z "$CURRENT_BRANCH" ]; then
    echo "❌ Error: Could not determine current branch"
    exit 1
fi

# Run the workflow on the current branch
echo "🔄 Triggering workflow..."
gh workflow run deploy.yml \
    --ref "$CURRENT_BRANCH" \
    -f environment="$ENVIRONMENT" \
    -f setup_infrastructure="$SETUP_INFRASTRUCTURE"

echo "✅ Workflow triggered successfully!"
echo ""
echo "📋 Monitor the workflow:"
echo "  gh run list --workflow=deploy.yml --branch=$CURRENT_BRANCH"
echo "  gh run watch" 