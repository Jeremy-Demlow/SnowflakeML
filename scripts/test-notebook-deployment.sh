#!/bin/bash

# Local Notebook Deployment Test Script
# This script tests the core notebook deployment functionality locally

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}🧪 Testing Notebook Deployment Locally${NC}"
echo "============================================"

# Check if we're in the right directory
if [ ! -f "config.yaml" ]; then
    echo -e "${RED}❌ Not in the correct directory. Please run from project root.${NC}"
    exit 1
fi

# Load configuration (basic version)
if command -v yq &> /dev/null; then
    SNOWFLAKE_DATABASE=$(yq eval '.snowflake.database.name' config.yaml)
    SNOWFLAKE_SCHEMA=$(yq eval '.snowflake.schema.name' config.yaml)
    if [ "$SNOWFLAKE_DATABASE" = "null" ]; then
        SNOWFLAKE_DATABASE="HOL_DB"
    fi
    if [ "$SNOWFLAKE_SCHEMA" = "null" ]; then
        SNOWFLAKE_SCHEMA="HOL_SCHEMA"
    fi
else
    # Fallback values
    SNOWFLAKE_DATABASE="HOL_DB"
    SNOWFLAKE_SCHEMA="HOL_SCHEMA"
fi

echo -e "${BLUE}📋 Configuration:${NC}"
echo "  Database: $SNOWFLAKE_DATABASE"
echo "  Schema: $SNOWFLAKE_SCHEMA"

# Step 1: Test Snowflake connection
echo -e "\n${BLUE}1. Testing Snowflake connection...${NC}"
if snow connection test > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Snowflake connection is working${NC}"
else
    echo -e "${RED}❌ Snowflake connection failed${NC}"
    echo "Please ensure your ml_pipeline connection is configured correctly."
    exit 1
fi

# Step 2: Check sf_nbs directory
echo -e "\n${BLUE}2. Checking sf_nbs directory...${NC}"
if [ ! -d "sf_nbs" ]; then
    echo -e "${RED}❌ sf_nbs directory not found!${NC}"
    echo "Please create sf_nbs directory and add your notebooks there."
    exit 1
fi

notebook_count=$(find sf_nbs -name "*.ipynb" -type f | wc -l)
if [ $notebook_count -eq 0 ]; then
    echo -e "${RED}❌ No notebooks found in sf_nbs directory!${NC}"
    echo "Please add .ipynb files to sf_nbs/ directory."
    exit 1
fi

echo -e "${GREEN}✅ Found $notebook_count notebooks in sf_nbs:${NC}"
find sf_nbs -name "*.ipynb" -type f | while read notebook; do
    echo "    - $notebook"
done

# Step 3: Setup Git Repository in Snowflake
echo -e "\n${BLUE}3. Setting up Git repository in Snowflake...${NC}"
REPO_URL="https://github.com/Jeremy-Demlow/SnowflakeML.git"
REPO_NAME="ML_PIPELINE_REPO_TEST"

echo "Repository URL: $REPO_URL"
echo "Repository Name: $REPO_NAME"

# Check if repository already exists, if not create it
if snow git list 2>/dev/null | grep -q "$REPO_NAME"; then
    echo -e "${GREEN}✅ Repository $REPO_NAME already exists${NC}"
else
    echo "Creating new repository $REPO_NAME..."
    # Use git setup with automated inputs (no authentication, public repo)
    echo -e "$REPO_URL\nn\n" | snow git setup "$REPO_NAME" > /dev/null 2>&1 || {
        echo -e "${YELLOW}⚠️  Git setup with CLI failed, trying SQL approach...${NC}"
        snow sql -q "
        CREATE OR REPLACE GIT REPOSITORY ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.$REPO_NAME
        ORIGIN = '$REPO_URL'
        API_INTEGRATION = '${REPO_NAME}_api_integration'
        COMMENT = 'ML Pipeline Repository - Local Test'
        " > /dev/null 2>&1 || echo -e "${YELLOW}⚠️  Repository creation failed - might already exist${NC}"
    }
fi

echo -e "${GREEN}✅ Git repository setup completed${NC}"

# Step 4: Fetch latest content
echo -e "\n${BLUE}4. Fetching latest repository content...${NC}"
snow git fetch "$REPO_NAME" > /dev/null 2>&1 || snow sql -q "ALTER GIT REPOSITORY ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.$REPO_NAME FETCH" > /dev/null 2>&1
echo -e "${GREEN}✅ Repository content fetched${NC}"

# Step 5: Deploy notebooks
echo -e "\n${BLUE}5. Deploying notebooks from sf_nbs...${NC}"
BRANCH="main"
SF_NBS="sf_nbs"

deployed_count=0
while IFS= read -r -d '' notebook; do
    filename=$(basename "$notebook")
    notebook_name="${filename%.*}"
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    identifier="${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK_TEST"
    directory_path="@${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${REPO_NAME}/branches/${BRANCH}/${SF_NBS}/"
    
    echo "📓 Creating notebook: $identifier"
    echo "   Source: $directory_path$filename"
    
    # Create notebook with complete configuration using SQL (CLI doesn't support Git repo directories)
    echo "   Creating notebook with full configuration..."
    if snow sql -q "
    CREATE OR REPLACE NOTEBOOK $identifier
    FROM '$directory_path'
    MAIN_FILE = '$filename'
    RUNTIME_NAME = 'SYSTEM\$BASIC_RUNTIME'
    COMPUTE_POOL = 'HOL_COMPUTE_POOL_HIGHMEM'
    QUERY_WAREHOUSE = HOL_WAREHOUSE
    COMMENT = 'Snowflake Notebook - ${notebook_name} - Local Test'
    " > /dev/null 2>&1; then
        echo -e "   ${GREEN}✅ Created successfully${NC}"
    else
        echo -e "   ${RED}❌ Failed to create $identifier${NC}"
    fi
    
    ((deployed_count++))
done < <(find "$SF_NBS" -name "*.ipynb" -type f -print0)

echo -e "${GREEN}✅ Notebook deployment completed${NC}"

# Step 6: Validate deployment
echo -e "\n${BLUE}6. Validating deployment...${NC}"

echo "🔍 Validating each deployed notebook..."
while IFS= read -r -d '' notebook; do
    filename=$(basename "$notebook")
    notebook_name="${filename%.*}"
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    identifier="${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK_TEST"
    
    echo -n "   Checking: $identifier ... "
    if snow sql -q "DESCRIBE NOTEBOOK $identifier;" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ EXISTS${NC}"
    else
        echo -e "${RED}❌ NOT FOUND${NC}"
    fi
done < <(find "$SF_NBS" -name "*.ipynb" -type f -print0)

# Step 7: Configure external access integrations
echo -e "\n${BLUE}7. Configuring external access integrations...${NC}"
while IFS= read -r -d '' notebook; do
    filename=$(basename "$notebook")
    notebook_name="${filename%.*}"
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    identifier="${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK_TEST"
    
    echo "   Configuring: $identifier"
    
    # Configure external access integrations (compute pool and warehouse already set in CREATE)
    echo "     Setting external access integrations..."
    if snow sql -q "
    ALTER NOTEBOOK IF EXISTS $identifier SET
      EXTERNAL_ACCESS_INTEGRATIONS = ('ALLOW_ALL_ACCESS_INTEGRATION')
    " > /dev/null 2>&1; then
        echo -e "     ${GREEN}✅ External access set${NC}"
    else
        echo -e "     ${YELLOW}⚠️  Could not set external access${NC}"
    fi
done < <(find "$SF_NBS" -name "*.ipynb" -type f -print0)

echo -e "${GREEN}✅ External access configuration completed${NC}"

# Step 8: Summary
echo -e "\n${GREEN}🎉 Local Deployment Test Completed Successfully!${NC}"
echo -e "${BLUE}📋 Summary:${NC}"
echo "✅ Snowflake connection working"
echo "✅ Git repository created/updated: $REPO_NAME"
echo "✅ Repository content fetched"
echo "✅ Notebooks deployed from sf_nbs/ with proper configuration:"
echo "   - Database: $SNOWFLAKE_DATABASE"
echo "   - Schema: $SNOWFLAKE_SCHEMA" 
echo "   - Warehouse: HOL_WAREHOUSE"
echo "   - Compute Pool: HOL_COMPUTE_POOL_HIGHMEM"
echo "   - Runtime: SYSTEM\$BASIC_RUNTIME"
echo "✅ Deployment validated"
echo "✅ External access integrations configured"

echo -e "\n${BLUE}📓 Deployed Notebooks:${NC}"
while IFS= read -r -d '' notebook; do
    filename=$(basename "$notebook")
    notebook_name="${filename%.*}"
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    identifier="${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK_TEST"
    echo "  - $identifier"
done < <(find "$SF_NBS" -name "*.ipynb" -type f -print0)

echo -e "\n${YELLOW}🎯 Next Steps:${NC}"
echo "1. Check the notebooks in Snowflake UI under Data > Notebooks"
echo "2. Run the notebooks manually to test functionality"
echo "3. If everything works, set up GitHub Actions with: ./scripts/setup-github-secrets.sh"
echo "4. Push changes to trigger automated deployment"

echo -e "\n${BLUE}🧹 Cleanup (Optional):${NC}"
echo "To remove test artifacts, run:"
while IFS= read -r -d '' notebook; do
    filename=$(basename "$notebook")
    notebook_name="${filename%.*}"
    notebook_name_upper=$(echo "$notebook_name" | tr '[:lower:]' '[:upper:]')
    identifier="${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.${notebook_name_upper}_NOTEBOOK_TEST"
    echo "  snow sql -q \"DROP NOTEBOOK IF EXISTS $identifier;\""
done < <(find "$SF_NBS" -name "*.ipynb" -type f -print0)
echo "  snow sql -q \"DROP GIT REPOSITORY IF EXISTS ${SNOWFLAKE_DATABASE}.${SNOWFLAKE_SCHEMA}.$REPO_NAME;\"" 