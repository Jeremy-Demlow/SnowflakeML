#!/bin/bash

# Test Git Repository Setup for Notebook Deployment
# This script tests if the Git repository integration works with branch references

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Git Repository Setup${NC}"
echo "=================================="

# Check if we have a Git repository
if ! git rev-parse --git-dir > /dev/null 2>&1; then
    echo -e "${RED}❌ Not in a Git repository${NC}"
    exit 1
fi

# Get current branch
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${BLUE}📍 Current branch: ${CURRENT_BRANCH}${NC}"

# Get current commit hash
CURRENT_COMMIT=$(git rev-parse HEAD)
CURRENT_COMMIT_SHORT=$(git rev-parse --short HEAD)
echo -e "${BLUE}📍 Current commit: ${CURRENT_COMMIT_SHORT}${NC}"

# Check if we have notebooks
if [ -d "sf_nbs" ] && [ "$(ls -A sf_nbs/*.ipynb 2>/dev/null)" ]; then
    echo -e "${GREEN}✅ Found notebooks in sf_nbs/${NC}"
    ls -la sf_nbs/*.ipynb
else
    echo -e "${YELLOW}⚠️  No notebooks found in sf_nbs/${NC}"
fi

echo -e "\n${BLUE}🔧 Testing Git repository SQL commands${NC}"

# Test the SQL command that will be used in GitHub Actions
echo -e "${YELLOW}Branch-based path:${NC} '@ML_PIPELINE_REPO/branches/${CURRENT_BRANCH}/sf_nbs/'"
echo -e "${YELLOW}Commit-based path:${NC} '@ML_PIPELINE_REPO/commits/${CURRENT_COMMIT_SHORT}/sf_nbs/'"

# Check if connected to Snowflake
if snow connection test &> /dev/null; then
    echo -e "${GREEN}✅ Snowflake connection active${NC}"
    
    # Test if Git repository exists
    if snow sql -q "SHOW GIT REPOSITORIES LIKE 'ML_PIPELINE_REPO';" | grep -q "ML_PIPELINE_REPO"; then
        echo -e "${GREEN}✅ ML_PIPELINE_REPO exists in Snowflake${NC}"
        
        # Test listing files from different references
        echo -e "\n${BLUE}🔍 Testing Git repository file listing${NC}"
        
        echo "Testing branch reference..."
        if snow sql -q "LIST @ML_PIPELINE_REPO/branches/${CURRENT_BRANCH}/sf_nbs/;" 2>/dev/null; then
            echo -e "${GREEN}✅ Branch reference works${NC}"
        else
            echo -e "${YELLOW}⚠️  Branch reference not working, trying commit reference${NC}"
            if snow sql -q "LIST @ML_PIPELINE_REPO/commits/${CURRENT_COMMIT_SHORT}/sf_nbs/;" 2>/dev/null; then
                echo -e "${GREEN}✅ Commit reference works${NC}"
            else
                echo -e "${RED}❌ Neither branch nor commit reference works${NC}"
            fi
        fi
    else
        echo -e "${YELLOW}⚠️  ML_PIPELINE_REPO not found in Snowflake${NC}"
        echo "Run the infrastructure setup or deployment workflow first"
    fi
else
    echo -e "${YELLOW}⚠️  Not connected to Snowflake${NC}"
    echo "This test requires an active Snowflake connection"
fi

echo -e "\n${GREEN}🎯 Recommendations for deployment:${NC}"
echo "• Use branch reference: @ML_PIPELINE_REPO/branches/${CURRENT_BRANCH}/sf_nbs/"
echo "• Alternative commit reference: @ML_PIPELINE_REPO/commits/${CURRENT_COMMIT_SHORT}/sf_nbs/"
echo "• Current GitHub Actions will use: @ML_PIPELINE_REPO/branches/\${{ github.ref_name }}/sf_nbs/"

echo -e "\n${BLUE}✅ Git repository test completed${NC}" 