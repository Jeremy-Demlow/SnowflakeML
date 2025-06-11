#!/bin/bash

# GitHub Actions Setup Script for Snowflake ML Pipeline
# This script helps set up GitHub repository secrets and variables

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🚀 GitHub Actions Setup for Snowflake ML Pipeline${NC}"
echo "=================================================="

# Check if GitHub CLI is installed
if ! command -v gh &> /dev/null; then
    echo -e "${RED}❌ GitHub CLI (gh) is not installed.${NC}"
    echo "Please install it from: https://cli.github.com/"
    exit 1
fi

# Check if user is authenticated
if ! gh auth status &> /dev/null; then
    echo -e "${RED}❌ Not authenticated with GitHub CLI.${NC}"
    echo "Please run: gh auth login"
    exit 1
fi

echo -e "${GREEN}✅ GitHub CLI is installed and authenticated${NC}"

# Get current repository info
REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner)
echo -e "${BLUE}📍 Repository: ${REPO}${NC}"

# Prompt for Snowflake credentials
echo -e "\n${YELLOW}📝 Please provide your Snowflake connection details:${NC}"

read -p "Snowflake Account (default: trb65519): " SNOWFLAKE_ACCOUNT
SNOWFLAKE_ACCOUNT=${SNOWFLAKE_ACCOUNT:-trb65519}

read -p "Snowflake User (default: jd_service_account_admin): " SNOWFLAKE_USER
SNOWFLAKE_USER=${SNOWFLAKE_USER:-jd_service_account_admin}

read -s -p "Snowflake Password: " SNOWFLAKE_PASSWORD
echo

read -p "Snowflake Role (default: ACCOUNTADMIN): " SNOWFLAKE_ROLE
SNOWFLAKE_ROLE=${SNOWFLAKE_ROLE:-ACCOUNTADMIN}

read -p "Snowflake Warehouse (default: HOL_WAREHOUSE): " SNOWFLAKE_WAREHOUSE
SNOWFLAKE_WAREHOUSE=${SNOWFLAKE_WAREHOUSE:-HOL_WAREHOUSE}

read -p "Snowflake Database (default: HOL_DB): " SNOWFLAKE_DATABASE
SNOWFLAKE_DATABASE=${SNOWFLAKE_DATABASE:-HOL_DB}

read -p "Snowflake Schema (default: HOL_SCHEMA): " SNOWFLAKE_SCHEMA
SNOWFLAKE_SCHEMA=${SNOWFLAKE_SCHEMA:-HOL_SCHEMA}

echo -e "\n${BLUE}🔧 Setting up GitHub repository variables...${NC}"

# Set repository variables
gh variable set SNOWFLAKE_ACCOUNT --body "$SNOWFLAKE_ACCOUNT"
gh variable set SNOWFLAKE_USER --body "$SNOWFLAKE_USER"
gh variable set SNOWFLAKE_ROLE --body "$SNOWFLAKE_ROLE"
gh variable set SNOWFLAKE_WAREHOUSE --body "$SNOWFLAKE_WAREHOUSE"
gh variable set SNOWFLAKE_DATABASE --body "$SNOWFLAKE_DATABASE"
gh variable set SNOWFLAKE_SCHEMA --body "$SNOWFLAKE_SCHEMA"

echo -e "${GREEN}✅ Repository variables set successfully${NC}"

echo -e "\n${BLUE}🔐 Setting up GitHub repository secrets...${NC}"

# Set repository secrets
echo "$SNOWFLAKE_PASSWORD" | gh secret set SNOWFLAKE_PASSWORD

echo -e "${GREEN}✅ Repository secrets set successfully${NC}"

# Optional: Set up environments
echo -e "\n${YELLOW}🌍 Would you like to set up GitHub Environments? (y/n)${NC}"
read -p "This will create development, staging, and production environments: " setup_environments

if [[ $setup_environments =~ ^[Yy]$ ]]; then
    echo -e "${BLUE}🌍 Setting up GitHub Environments...${NC}"
    
    # Create environments
    for env in development staging production; do
        echo -e "${BLUE}Creating environment: $env${NC}"
        
        # Create environment (this may fail if environment already exists, which is OK)
        gh api repos/$REPO/environments/$env -X PUT --input - <<< '{}' || true
        
        # Set environment variables
        gh variable set SNOWFLAKE_ACCOUNT --env $env --body "$SNOWFLAKE_ACCOUNT"
        gh variable set SNOWFLAKE_USER --env $env --body "$SNOWFLAKE_USER"
        gh variable set SNOWFLAKE_ROLE --env $env --body "$SNOWFLAKE_ROLE"
        gh variable set SNOWFLAKE_WAREHOUSE --env $env --body "$SNOWFLAKE_WAREHOUSE"
        
        # Environment-specific database/schema
        if [ "$env" = "production" ]; then
            gh variable set SNOWFLAKE_DATABASE --env $env --body "${SNOWFLAKE_DATABASE}_PROD"
            gh variable set SNOWFLAKE_SCHEMA --env $env --body "${SNOWFLAKE_SCHEMA}_PROD"
        elif [ "$env" = "staging" ]; then
            gh variable set SNOWFLAKE_DATABASE --env $env --body "${SNOWFLAKE_DATABASE}_STAGING"
            gh variable set SNOWFLAKE_SCHEMA --env $env --body "${SNOWFLAKE_SCHEMA}_STAGING"
        else
            gh variable set SNOWFLAKE_DATABASE --env $env --body "${SNOWFLAKE_DATABASE}_DEV"
            gh variable set SNOWFLAKE_SCHEMA --env $env --body "${SNOWFLAKE_SCHEMA}_DEV"
        fi
        
        # Set environment secrets
        echo "$SNOWFLAKE_PASSWORD" | gh secret set SNOWFLAKE_PASSWORD --env $env
        
        echo -e "${GREEN}✅ Environment $env configured${NC}"
    done
fi

echo -e "\n${GREEN}🎉 GitHub Actions setup completed successfully!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "Repository: $REPO"
echo "Variables configured: ✅"
echo "Secrets configured: ✅"
echo "Environments: $([ \"$setup_environments\" = \"y\" ] && echo \"✅\" || echo \"❌\")"

echo -e "\n${YELLOW}🚀 Next Steps:${NC}"
echo "1. Commit and push your changes to trigger the workflow"
echo "2. Or manually run the workflow from GitHub Actions tab"
echo "3. Monitor the deployment in the Actions tab"
echo "4. Check your Snowflake account for the deployed notebook"

echo -e "\n${BLUE}📚 For more information, see GITHUB_ACTIONS_SETUP.md${NC}" 