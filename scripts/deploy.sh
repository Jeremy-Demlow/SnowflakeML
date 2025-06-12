#!/bin/bash

# Deployment Helper Script for Snowflake ML Pipeline
# Simplifies GitHub Actions deployment commands

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="development"
ACTION="deploy"
FORCE_RECREATE="false"

# Help function
show_help() {
    echo -e "${BLUE}🚀 Snowflake ML Deployment Helper${NC}"
    echo "=================================="
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -e, --environment ENV    Target environment (development|staging|production)"
    echo "  -a, --action ACTION      Action to perform (deploy|infrastructure|status)"
    echo "  -f, --force             Force recreate infrastructure resources"
    echo "  -h, --help              Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0                                    # Deploy to development"
    echo "  $0 -e production                     # Deploy to production"
    echo "  $0 -a infrastructure -e staging      # Setup staging infrastructure"
    echo "  $0 -a status                         # Check deployment status"
    echo "  $0 -e development -f                 # Force recreate dev infrastructure"
    echo ""
    echo "Quick Commands:"
    echo "  $0 dev        # Deploy to development"
    echo "  $0 staging    # Deploy to staging"  
    echo "  $0 prod       # Deploy to production"
    echo "  $0 status     # Check status"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -a|--action)
            ACTION="$2"
            shift 2
            ;;
        -f|--force)
            FORCE_RECREATE="true"
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        dev|development)
            ENVIRONMENT="development"
            shift
            ;;
        staging)
            ENVIRONMENT="staging"
            shift
            ;;
        prod|production)
            ENVIRONMENT="production"
            shift
            ;;
        status)
            ACTION="status"
            shift
            ;;
        infrastructure|infra)
            ACTION="infrastructure"
            shift
            ;;
        *)
            echo -e "${RED}❌ Unknown option: $1${NC}"
            show_help
            exit 1
            ;;
    esac
done

# Check if GitHub CLI is installed and authenticated
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed.${NC}"
    echo "Install it from: https://cli.github.com/"
    exit 1
fi

if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Not authenticated with GitHub CLI.${NC}"
    echo "Please run: gh auth login"
    exit 1
fi

# Execute action
case $ACTION in
    deploy)
        echo -e "${BLUE}🚀 Deploying notebooks to ${ENVIRONMENT} environment...${NC}"
        gh workflow run deploy.yml -f environment="$ENVIRONMENT"
        echo -e "${GREEN}✅ Deployment triggered successfully${NC}"
        echo -e "${YELLOW}💡 Monitor progress with: gh run watch${NC}"
        ;;
    infrastructure|infra)
        echo -e "${BLUE}🏗️  Setting up infrastructure for ${ENVIRONMENT} environment...${NC}"
        if [ "$FORCE_RECREATE" = "true" ]; then
            echo -e "${YELLOW}⚠️  Force recreate enabled${NC}"
            gh workflow run infrastructure.yml -f environment="$ENVIRONMENT" -f force_recreate=true
        else
            gh workflow run infrastructure.yml -f environment="$ENVIRONMENT"
        fi
        echo -e "${GREEN}✅ Infrastructure setup triggered successfully${NC}"
        echo -e "${YELLOW}💡 Monitor progress with: gh run watch${NC}"
        ;;
    status)
        echo -e "${BLUE}📊 Checking deployment status...${NC}"
        echo ""
        echo -e "${YELLOW}Recent workflow runs:${NC}"
        gh run list --limit 10
        echo ""
        echo -e "${YELLOW}💡 For detailed logs: gh run view <run-id> --log${NC}"
        echo -e "${YELLOW}💡 To watch live: gh run watch${NC}"
        ;;
    *)
        echo -e "${RED}❌ Unknown action: $ACTION${NC}"
        show_help
        exit 1
        ;;
esac

# Show next steps
if [ "$ACTION" != "status" ]; then
    echo ""
    echo -e "${BLUE}📋 Next Steps:${NC}"
    echo "1. Monitor deployment: gh run watch"
    echo "2. Check status: $0 status"
    echo "3. View logs: gh run view <run-id> --log"
    
    if [ "$ENVIRONMENT" = "development" ]; then
        echo "4. Promote to staging: $0 staging"
    elif [ "$ENVIRONMENT" = "staging" ]; then
        echo "4. Promote to production: $0 prod"
    fi
fi 