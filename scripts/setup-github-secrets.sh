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
echo -e "${BLUE}💡 Note: For environments, we'll create environment-specific versions:${NC}"
echo -e "   ${BLUE}• Development: [YOUR_DB]_DEV, [YOUR_SCHEMA]_DEV${NC}"
echo -e "   ${BLUE}• Staging: [YOUR_DB]_STAGING, [YOUR_SCHEMA]_STAGING${NC}" 
echo -e "   ${BLUE}• Production: [YOUR_DB]_PROD, [YOUR_SCHEMA]_PROD${NC}"
echo ""

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

read -p "Base Database Name (default: HOL_DB): " SNOWFLAKE_DATABASE
SNOWFLAKE_DATABASE=${SNOWFLAKE_DATABASE:-HOL_DB}
echo -e "   ${GREEN}→ Will create: ${SNOWFLAKE_DATABASE}_DEV, ${SNOWFLAKE_DATABASE}_STAGING, ${SNOWFLAKE_DATABASE}_PROD${NC}"

read -p "Base Schema Name (default: HOL_SCHEMA): " SNOWFLAKE_SCHEMA
SNOWFLAKE_SCHEMA=${SNOWFLAKE_SCHEMA:-HOL_SCHEMA}
echo -e "   ${GREEN}→ Will create: ${SNOWFLAKE_SCHEMA}_DEV, ${SNOWFLAKE_SCHEMA}_STAGING, ${SNOWFLAKE_SCHEMA}_PROD${NC}"

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
    
    # Ask about database naming strategy
    echo -e "\n${YELLOW}📋 Database Naming Strategy:${NC}"
    echo "1. Use environment-specific names (${SNOWFLAKE_DATABASE}_DEV, ${SNOWFLAKE_DATABASE}_PROD, etc.) - Recommended for new setups"
    echo "2. Use existing infrastructure names ($SNOWFLAKE_DATABASE, $SNOWFLAKE_SCHEMA for all environments) - Use if infrastructure already exists"
    read -p "Choose option (1 or 2): " naming_strategy
    
    echo -e "\n${BLUE}🏗️  Environment Resources to be Created:${NC}"
    if [ "$naming_strategy" = "1" ]; then
        echo -e "   ${GREEN}• Development: ${SNOWFLAKE_DATABASE}_DEV.${SNOWFLAKE_SCHEMA}_DEV${NC}"
        echo -e "   ${GREEN}• Staging: ${SNOWFLAKE_DATABASE}_STAGING.${SNOWFLAKE_SCHEMA}_STAGING${NC}"
        echo -e "   ${GREEN}• Production: ${SNOWFLAKE_DATABASE}_PROD.${SNOWFLAKE_SCHEMA}_PROD${NC}"
    else
        echo -e "   ${YELLOW}• All environments: ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA} (shared)${NC}"
    fi
    echo ""
    
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
        
        # Environment-specific or shared database/schema based on user choice
        if [ "$naming_strategy" = "1" ]; then
            # Environment-specific naming
            if [ "$env" = "production" ]; then
                ENV_DB="${SNOWFLAKE_DATABASE}_PROD"
                ENV_SCHEMA="${SNOWFLAKE_SCHEMA}_PROD"
            elif [ "$env" = "staging" ]; then
                ENV_DB="${SNOWFLAKE_DATABASE}_STAGING"
                ENV_SCHEMA="${SNOWFLAKE_SCHEMA}_STAGING"
            else
                ENV_DB="${SNOWFLAKE_DATABASE}_DEV"
                ENV_SCHEMA="${SNOWFLAKE_SCHEMA}_DEV"
            fi
            gh variable set SNOWFLAKE_DATABASE --env $env --body "$ENV_DB"
            gh variable set SNOWFLAKE_SCHEMA --env $env --body "$ENV_SCHEMA"
            echo -e "   ${GREEN}✅ Database: $ENV_DB, Schema: $ENV_SCHEMA${NC}"
        else
            # Use existing infrastructure names for all environments
            gh variable set SNOWFLAKE_DATABASE --env $env --body "$SNOWFLAKE_DATABASE"
            gh variable set SNOWFLAKE_SCHEMA --env $env --body "$SNOWFLAKE_SCHEMA"
            echo -e "   ${GREEN}✅ Database: $SNOWFLAKE_DATABASE, Schema: $SNOWFLAKE_SCHEMA${NC}"
        fi
        
        # Set environment secrets
        echo "$SNOWFLAKE_PASSWORD" | gh secret set SNOWFLAKE_PASSWORD --env $env
        
        echo -e "${GREEN}✅ Environment $env configured${NC}"
    done
    
    if [ "$naming_strategy" = "2" ]; then
        echo -e "\n${YELLOW}⚠️  Note: All environments will use the same infrastructure.${NC}"
        echo "Database: $SNOWFLAKE_DATABASE"
        echo "Schema: $SNOWFLAKE_SCHEMA"
        echo "Consider creating separate environments for production safety."
    else
        echo -e "\n${GREEN}🎯 Environment-specific infrastructure configured!${NC}"
        echo -e "${BLUE}Next: Run 'ENV=development ./cli-setup.sh' to create the development infrastructure${NC}"
    fi
fi

echo -e "\n${GREEN}🎉 GitHub Actions setup completed successfully!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "Repository: $REPO"
echo "Variables configured: ✅"
echo "Secrets configured: ✅"

if [[ $setup_environments =~ ^[Yy]$ ]]; then
    echo "Environments: ✅"
    echo -e "\n${BLUE}🌍 Environment Configuration:${NC}"
    if [ "${naming_strategy:-1}" = "1" ]; then
        echo -e "  ${GREEN}• Development: ${SNOWFLAKE_DATABASE}_DEV.${SNOWFLAKE_SCHEMA}_DEV${NC}"
        echo -e "  ${GREEN}• Staging: ${SNOWFLAKE_DATABASE}_STAGING.${SNOWFLAKE_SCHEMA}_STAGING${NC}"
        echo -e "  ${GREEN}• Production: ${SNOWFLAKE_DATABASE}_PROD.${SNOWFLAKE_SCHEMA}_PROD${NC}"
    else
        echo -e "  ${YELLOW}• All environments: ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}${NC}"
    fi
else
    echo "Environments: ❌"
fi

echo -e "\n${YELLOW}🚀 Next Steps:${NC}"
if [[ $setup_environments =~ ^[Yy]$ ]] && [ "${naming_strategy:-1}" = "1" ]; then
    echo "1. Create development infrastructure: ENV=development ./cli-setup.sh"
    echo "2. Add notebooks to sf_nbs/ directory"
    echo "3. Commit and push to trigger deployment"
    echo "4. Later create staging/production infrastructure as needed"
else
    echo "1. Commit and push your changes to trigger the workflow"
    echo "2. Or manually run the workflow from GitHub Actions tab"
    echo "3. Monitor the deployment in the Actions tab"
    echo "4. Check your Snowflake account for the deployed notebook"
fi

echo -e "\n${BLUE}📚 For more information, see GITHUB_ACTIONS_SETUP.md${NC}" 