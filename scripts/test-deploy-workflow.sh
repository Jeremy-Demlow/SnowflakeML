#!/bin/bash

# Test Deploy Notebooks Workflow Locally
# This script simulates the exact steps from deploy-notebooks.yml

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}🧪 Testing Deploy Notebooks Workflow Locally${NC}"
echo "=============================================="

# Simulate GitHub Actions environment variables
export GITHUB_REPOSITORY="Jeremy-Demlow/SnowflakeML"
export GITHUB_REF_NAME="main"

# Use ml_pipeline connection values
SNOWFLAKE_DATABASE="HOL_DB"
SNOWFLAKE_SCHEMA="HOL_SCHEMA"
SNOWFLAKE_WAREHOUSE="HOL_WAREHOUSE"

echo -e "${BLUE}📋 Configuration:${NC}"
echo "Repository: $GITHUB_REPOSITORY"
echo "Branch: $GITHUB_REF_NAME"
echo "Database: $SNOWFLAKE_DATABASE"
echo "Schema: $SNOWFLAKE_SCHEMA"
echo "Warehouse: $SNOWFLAKE_WAREHOUSE"

# Step 1: Test Snowflake Connection (from workflow)
echo -e "\n${BLUE}1. Testing Snowflake Connection${NC}"
if snow connection test > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Snowflake connection verified${NC}"
else
    echo -e "${RED}❌ Snowflake connection failed${NC}"
    exit 1
fi

# Step 2: Check for Notebooks (from workflow)
echo -e "\n${BLUE}2. Checking for Notebooks${NC}"
if [ ! -d "sf_nbs" ]; then
    echo -e "${RED}❌ sf_nbs directory not found${NC}"
    exit 1
fi

notebook_count=$(find sf_nbs -name "*.ipynb" | wc -l)
if [ $notebook_count -eq 0 ]; then
    echo -e "${RED}❌ No .ipynb files found in sf_nbs directory${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Found $notebook_count notebook(s) to deploy${NC}"
find sf_nbs -name "*.ipynb" | while read notebook; do
    echo "  📓 $notebook"
done

# Step 3: Setup Git Repository (EXACT workflow logic)
echo -e "\n${BLUE}3. Setting up Git Repository (Workflow Logic)${NC}"

# Clean up any existing test repository first
snow sql -q "DROP GIT REPOSITORY IF EXISTS ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_REPO;" > /dev/null 2>&1 || true

# Direct SQL approach (as per updated workflow)
echo "Using workflow SQL approach (API_INTEGRATION)..."
if snow sql -q "
CREATE OR REPLACE GIT REPOSITORY ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_REPO
ORIGIN = 'https://github.com/$GITHUB_REPOSITORY'
API_INTEGRATION = 'GITHUB_ALL'
" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Git repository created${NC}"
    SQL_WORKFLOW_SUCCESS=true
else
    echo -e "${RED}❌ Git repository creation failed${NC}"
    SQL_WORKFLOW_SUCCESS=false
    exit 1
fi

# Fetch repository
echo "Fetching repository content..."
if snow sql -q "ALTER GIT REPOSITORY ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_REPO FETCH" > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Repository content fetched${NC}"
else
    echo -e "${RED}❌ Repository fetch failed${NC}"
    exit 1
fi

# Step 4: Deploy Notebooks (EXACT workflow logic)
echo -e "\n${BLUE}4. Deploying Notebooks (Workflow Logic)${NC}"

deploy_failed=false

find sf_nbs -name "*.ipynb" | while read -r notebook_path; do
    # Extract notebook name without extension and path
    notebook_name=$(basename "$notebook_path" .ipynb)
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    
    echo "📓 Deploying notebook: $notebook_path -> ${notebook_name_upper}_NOTEBOOK"
    
    # Use EXACT workflow SQL command
    if snow sql -q "
    CREATE OR REPLACE NOTEBOOK ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK
    FROM '@${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_REPO/branches/${GITHUB_REF_NAME}/sf_nbs/'
    MAIN_FILE = '$(basename "$notebook_path")'
    RUNTIME_NAME = 'SYSTEM\$BASIC_RUNTIME'
    COMPUTE_POOL = 'HOL_COMPUTE_POOL_HIGHMEM'
    QUERY_WAREHOUSE = '${SNOWFLAKE_WAREHOUSE}'
    EXTERNAL_ACCESS_INTEGRATIONS = ('ALLOW_ALL_ACCESS_INTEGRATION')
    " > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Successfully deployed ${notebook_name_upper}_NOTEBOOK${NC}"
    else
        echo -e "${RED}❌ Failed to deploy ${notebook_name_upper}_NOTEBOOK${NC}"
        deploy_failed=true
    fi
done

if [ "$deploy_failed" = true ]; then
    echo -e "${RED}❌ Some notebook deployments failed${NC}"
    exit 1
fi

echo -e "${GREEN}🎉 All notebooks deployed successfully!${NC}"

# Step 5: Validation
echo -e "\n${BLUE}5. Validating Deployment${NC}"
echo "Checking deployed notebooks..."
snow sql -q "SHOW NOTEBOOKS IN SCHEMA ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA};" | grep -q "NOTEBOOK" && echo -e "${GREEN}✅ Notebooks found in schema${NC}" || echo -e "${RED}❌ No notebooks found${NC}"

# Summary
echo -e "\n${BLUE}📋 Test Results Summary${NC}"
echo "========================="
echo -e "Git Repository Setup (SQL): $([ "$SQL_WORKFLOW_SUCCESS" = true ] && echo -e "${GREEN}✅ SUCCESS${NC}" || echo -e "${RED}❌ FAILED${NC}")"
echo -e "Notebook Deployment: $([ "$deploy_failed" = false ] && echo -e "${GREEN}✅ SUCCESS${NC}" || echo -e "${RED}❌ FAILED${NC}")"

if [ "$SQL_WORKFLOW_SUCCESS" = true ] && [ "$deploy_failed" = false ]; then
    echo -e "\n${GREEN}🎉 WORKFLOW IS READY:${NC}"
    echo "The simplified deploy-notebooks.yml workflow should work perfectly in GitHub Actions!"
    echo "✅ Uses direct SQL approach (no CLI complexity)"
    echo "✅ API_INTEGRATION = 'GITHUB_ALL' for GitHub repositories"
    echo "✅ Automated and reliable"
else
    echo -e "\n${RED}🔧 WORKFLOW HAS ISSUES:${NC}"
    echo "Check the API_INTEGRATION setup in Snowflake"
fi

# # Cleanup
# echo -e "\n${BLUE}🧹 Cleaning up test artifacts${NC}"
# snow sql -q "DROP NOTEBOOK IF EXISTS ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_NOTEBOOK;" > /dev/null 2>&1 || true
# snow sql -q "DROP GIT REPOSITORY IF EXISTS ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.ML_PIPELINE_REPO;" > /dev/null 2>&1 || true
# echo -e "${GREEN}✅ Cleanup completed${NC}" 