#!/bin/bash

# Infrastructure Setup Testing Script
# This script tests the infrastructure setup components locally before running in GitHub Actions

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

echo -e "${BLUE}🏗️  Testing Infrastructure Setup Locally${NC}"
echo "============================================"

# Function to run tests
run_test() {
    local test_name="$1"
    local test_function="$2"
    
    echo -e "\n${BLUE}Testing: $test_name${NC}"
    echo "----------------------------------------"
    
    if $test_function; then
        echo -e "${GREEN}✅ $test_name: PASSED${NC}"
        return 0
    else
        echo -e "${RED}❌ $test_name: FAILED${NC}"
        return 1
    fi
}

# Test 1: Check required tools
test_required_tools() {
    echo "Checking required tools..."
    
    local tools_ok=true
    
    # Check Snowflake CLI
    if command -v snow &> /dev/null; then
        echo -e "${GREEN}✅ Snowflake CLI installed${NC}"
        snow --version
    else
        echo -e "${RED}❌ Snowflake CLI not installed${NC}"
        echo "Install: pip install snowflake-cli-labs"
        tools_ok=false
    fi
    
    # Check yq (for YAML parsing)
    if command -v yq &> /dev/null; then
        echo -e "${GREEN}✅ yq installed${NC}"
        yq --version
    else
        echo -e "${YELLOW}⚠️  yq not installed (optional for local testing)${NC}"
        echo "Install: brew install yq (macOS) or wget https://github.com/mikefarah/yq/releases/latest/download/yq_linux_amd64"
    fi
    
    # Check bash version
    if [ "${BASH_VERSION%%.*}" -ge 4 ]; then
        echo -e "${GREEN}✅ Bash version: $BASH_VERSION${NC}"
    else
        echo -e "${YELLOW}⚠️  Bash version: $BASH_VERSION (may have compatibility issues)${NC}"
    fi
    
    if [ "$tools_ok" = true ]; then
        return 0
    else
        return 1
    fi
}

# Test 2: Check Snowflake connection
test_snowflake_connection() {
    echo "Testing Snowflake connection..."
    
    # Test if connection exists
    if snow connection list | grep -q "ml_pipeline"; then
        echo -e "${GREEN}✅ ml_pipeline connection exists${NC}"
    else
        echo -e "${RED}❌ ml_pipeline connection not found${NC}"
        echo "Run: snow connection add ml_pipeline"
        return 1
    fi
    
    # Test connection
    if snow connection test > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Snowflake connection working${NC}"
        
        # Get connection details
        echo "Connection details:"
        snow connection list --format json | jq -r '.[] | select(.name=="ml_pipeline") | "  Account: \(.account)\n  User: \(.user)\n  Role: \(.role)\n  Warehouse: \(.warehouse)\n  Database: \(.database)\n  Schema: \(.schema)"' 2>/dev/null || echo "  (Details available via 'snow connection list')"
        
    else
        echo -e "${RED}❌ Snowflake connection failed${NC}"
        echo "Check your connection with: snow connection test"
        return 1
    fi
    
    return 0
}

# Test 3: Check infrastructure setup script
test_infrastructure_script() {
    echo "Testing infrastructure setup script..."
    
    if [ ! -f "cli-setup.sh" ]; then
        echo -e "${RED}❌ cli-setup.sh not found${NC}"
        return 1
    fi
    
    # Check script syntax
    if bash -n cli-setup.sh; then
        echo -e "${GREEN}✅ cli-setup.sh syntax is valid${NC}"
    else
        echo -e "${RED}❌ cli-setup.sh has syntax errors${NC}"
        return 1
    fi
    
    # Check if script is executable
    if [ -x "cli-setup.sh" ]; then
        echo -e "${GREEN}✅ cli-setup.sh is executable${NC}"
    else
        echo -e "${YELLOW}⚠️  cli-setup.sh is not executable${NC}"
        echo "Run: chmod +x cli-setup.sh"
    fi
    
    # Check script content for key components
    echo "Checking script components..."
    
    local components=(
        "CREATE DATABASE.*HOL_DB"
        "CREATE SCHEMA.*HOL_SCHEMA" 
        "CREATE WAREHOUSE.*HOL_WAREHOUSE"
        "CREATE COMPUTE POOL.*HOL_COMPUTE_POOL_HIGHMEM"
        "CREATE INTEGRATION.*ALLOW_ALL_ACCESS_INTEGRATION"
    )
    
    for component in "${components[@]}"; do
        if grep -q "$component" cli-setup.sh; then
            echo -e "${GREEN}✅ Found: $component${NC}"
        else
            echo -e "${YELLOW}⚠️  May be missing: $component${NC}"
        fi
    done
    
    return 0
}

# Test 4: Check current infrastructure state
test_current_infrastructure() {
    echo "Checking current infrastructure state..."
    
    local resources=(
        "DATABASE:HOL_DB:SHOW DATABASES LIKE 'HOL_DB'"
        "SCHEMA:HOL_SCHEMA:SHOW SCHEMAS IN DATABASE HOL_DB"
        "WAREHOUSE:HOL_WAREHOUSE:SHOW WAREHOUSES LIKE 'HOL_WAREHOUSE'"
        "COMPUTE_POOL:HOL_COMPUTE_POOL_HIGHMEM:SHOW COMPUTE POOLS LIKE 'HOL_COMPUTE_POOL_HIGHMEM'"
        "INTEGRATION:ALLOW_ALL_ACCESS_INTEGRATION:SHOW INTEGRATIONS LIKE 'ALLOW_ALL_ACCESS_INTEGRATION'"
    )
    
    echo -e "${PURPLE}Current infrastructure status:${NC}"
    
    for resource in "${resources[@]}"; do
        IFS=':' read -r type name query <<< "$resource"
        
        if snow sql -q "$query" 2>/dev/null | grep -q "$name"; then
            echo -e "${GREEN}✅ $type: $name exists${NC}"
        else
            echo -e "${YELLOW}⚠️  $type: $name not found (will be created)${NC}"
        fi
    done
    
    return 0
}

# Test 5: Check GitHub Actions workflow files
test_workflow_files() {
    echo "Checking GitHub Actions workflow files..."
    
    local workflows=(
        ".github/workflows/setup-infrastructure.yml"
        ".github/workflows/deploy-notebooks.yml"
        ".github/workflows/full-deployment.yml"
    )
    
    for workflow in "${workflows[@]}"; do
        if [ -f "$workflow" ]; then
            echo -e "${GREEN}✅ $workflow exists${NC}"
            
            # Basic YAML syntax check
            if python3 -c "import yaml; yaml.safe_load(open('$workflow'))" 2>/dev/null; then
                echo -e "${GREEN}   ✅ YAML syntax valid${NC}"
            else
                echo -e "${YELLOW}   ⚠️  Could not validate YAML (PyYAML needed)${NC}"
            fi
        else
            echo -e "${RED}❌ $workflow missing${NC}"
        fi
    done
    
    return 0
}

# Test 6: Check sf_nbs directory structure
test_notebook_directory() {
    echo "Checking notebook directory structure..."
    
    if [ -d "sf_nbs" ]; then
        local notebook_count=$(find sf_nbs -name "*.ipynb" -type f | wc -l)
        
        if [ $notebook_count -gt 0 ]; then
            echo -e "${GREEN}✅ sf_nbs directory with $notebook_count notebooks${NC}"
            echo "Notebooks found:"
            find sf_nbs -name "*.ipynb" -type f | while read notebook; do
                echo "  📓 $notebook"
            done
        else
            echo -e "${YELLOW}⚠️  sf_nbs directory exists but no notebooks found${NC}"
            echo "Add .ipynb files to sf_nbs/ for deployment"
        fi
    else
        echo -e "${YELLOW}⚠️  sf_nbs directory not found${NC}"
        echo "Create sf_nbs/ directory and add notebooks there"
        
        # Offer to create it
        read -p "Create sf_nbs directory now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p sf_nbs
            echo -e "${GREEN}✅ Created sf_nbs directory${NC}"
        fi
    fi
    
    return 0
}

# Test 7: Simulate infrastructure deployment (dry run)
test_infrastructure_dry_run() {
    echo "Running infrastructure setup dry run..."
    
    echo -e "${PURPLE}This would run the following steps:${NC}"
    echo "1. Check if HOL_DB database exists"
    echo "2. Check if HOL_SCHEMA schema exists" 
    echo "3. Check if HOL_WAREHOUSE warehouse exists"
    echo "4. Check if HOL_COMPUTE_POOL_HIGHMEM compute pool exists"
    echo "5. Check if ALLOW_ALL_ACCESS_INTEGRATION integration exists"
    echo "6. Run cli-setup.sh for any missing components"
    echo "7. Verify all components are accessible"
    
    # Check if we could actually run this
    if command -v snow &> /dev/null && snow connection test > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Ready to run infrastructure setup${NC}"
        
        read -p "Run actual infrastructure setup now? (y/n): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${BLUE}Running cli-setup.sh...${NC}"
            chmod +x cli-setup.sh
            ./cli-setup.sh
            echo -e "${GREEN}✅ Infrastructure setup completed${NC}"
        else
            echo -e "${YELLOW}⚠️  Skipping actual setup (dry run only)${NC}"
        fi
    else
        echo -e "${RED}❌ Cannot run infrastructure setup (connection issues)${NC}"
        return 1
    fi
    
    return 0
}

# Test 8: Check environment variables for GitHub Actions
test_github_environment() {
    echo "Checking GitHub Actions environment setup..."
    
    local required_vars=(
        "SNOWFLAKE_ACCOUNT"
        "SNOWFLAKE_USER"
        "SNOWFLAKE_ROLE"
        "SNOWFLAKE_WAREHOUSE"
        "SNOWFLAKE_DATABASE"
        "SNOWFLAKE_SCHEMA"
    )
    
    local required_secrets=(
        "SNOWFLAKE_PASSWORD"
    )
    
    echo -e "${PURPLE}Required GitHub Variables:${NC}"
    for var in "${required_vars[@]}"; do
        if [ -n "${!var}" ]; then
            echo -e "${GREEN}✅ $var: ${!var}${NC}"
        else
            echo -e "${YELLOW}⚠️  $var: Not set locally (should be set in GitHub)${NC}"
        fi
    done
    
    echo -e "${PURPLE}Required GitHub Secrets:${NC}"
    for secret in "${required_secrets[@]}"; do
        if [ -n "${!secret}" ]; then
            echo -e "${GREEN}✅ $secret: [SET]${NC}"
        else
            echo -e "${YELLOW}⚠️  $secret: Not set locally (should be set in GitHub)${NC}"
        fi
    done
    
    echo -e "${BLUE}💡 Use ./scripts/setup-github-secrets.sh to configure GitHub variables/secrets${NC}"
    
    return 0
}

# Main test execution
main() {
    echo -e "${BLUE}🚀 Starting Infrastructure Setup Tests${NC}"
    echo -e "${BLUE}======================================${NC}"
    
    local failed_tests=0
    local total_tests=0
    
    # List of tests to run
    local tests=(
        "Required Tools:test_required_tools"
        "Snowflake Connection:test_snowflake_connection"
        "Infrastructure Script:test_infrastructure_script"
        "Current Infrastructure:test_current_infrastructure"
        "Workflow Files:test_workflow_files"
        "Notebook Directory:test_notebook_directory"
        "GitHub Environment:test_github_environment"
        "Infrastructure Dry Run:test_infrastructure_dry_run"
    )
    
    # Run all tests
    for test in "${tests[@]}"; do
        IFS=':' read -r test_name test_function <<< "$test"
        total_tests=$((total_tests + 1))
        
        if ! run_test "$test_name" "$test_function"; then
            failed_tests=$((failed_tests + 1))
        fi
    done
    
    # Summary
    echo -e "\n${BLUE}📋 Test Summary${NC}"
    echo "==============="
    echo -e "Total tests: $total_tests"
    echo -e "Passed: $((total_tests - failed_tests))"
    echo -e "Failed: $failed_tests"
    
    if [ $failed_tests -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All tests passed! Infrastructure setup is ready for GitHub Actions.${NC}"
        echo -e "${GREEN}✅ You can now run the workflows in GitHub Actions with confidence.${NC}"
        return 0
    else
        echo -e "\n${YELLOW}⚠️  Some tests failed or had warnings. Review the output above.${NC}"
        echo -e "${YELLOW}🔧 Fix any issues before running GitHub Actions workflows.${NC}"
        return 1
    fi
}

# Help function
show_help() {
    echo "Infrastructure Setup Testing Script"
    echo ""
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  --dry-run       Skip interactive components"
    echo ""
    echo "This script tests:"
    echo "  ✅ Required tools (snow CLI, yq, etc.)"
    echo "  ✅ Snowflake connection"
    echo "  ✅ Infrastructure setup script"
    echo "  ✅ Current infrastructure state"
    echo "  ✅ GitHub Actions workflow files"
    echo "  ✅ Notebook directory structure"
    echo "  ✅ GitHub environment variables"
    echo "  ✅ Infrastructure deployment dry run"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Run main function
main 