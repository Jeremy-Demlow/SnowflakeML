#!/bin/bash

# Customer Conversion ML Pipeline - Snowflake CLI Setup
# This script creates all the necessary Snowflake resources using CLI commands

set -e  # Exit on any error

# Configuration - Load from YAML
CONFIG_FILE="${CONFIG_FILE:-config.yaml}"

# Check if yq is available for YAML parsing
if ! command -v yq &> /dev/null; then
    warn "yq not found. Installing yq for YAML parsing..."
    if command -v brew &> /dev/null; then
        brew install yq
    elif command -v apt-get &> /dev/null; then
        sudo apt-get update && sudo apt-get install -y yq
    else
        error "Please install yq: https://github.com/mikefarah/yq#install"
    fi
fi

# Load configuration from YAML and environment variables
load_config() {
    # Determine environment
    ENV="${ENV:-development}"
    
    # Auto-select environment-specific config file if not explicitly set
    if [ "$CONFIG_FILE" = "config.yaml" ] && [ "$ENV" != "development" ]; then
        ENV_CONFIG_FILE="config-${ENV}.yaml"
        if [ -f "$ENV_CONFIG_FILE" ]; then
            CONFIG_FILE="$ENV_CONFIG_FILE"
            log "Auto-selected environment config: $CONFIG_FILE"
        fi
    fi
    
    # Check for GitHub Actions environment variables first (takes precedence)
    if [ -n "${SNOWFLAKE_DATABASE:-}" ] && [ -n "${SNOWFLAKE_SCHEMA:-}" ] && [ -n "${SNOWFLAKE_WAREHOUSE:-}" ]; then
        log "Using environment variables from GitHub Actions (config file: $CONFIG_FILE for defaults)"
        DATABASE_NAME="${SNOWFLAKE_DATABASE}"
        SCHEMA_NAME="${SNOWFLAKE_SCHEMA}" 
        WAREHOUSE_NAME="${SNOWFLAKE_WAREHOUSE}"
        ROLE_NAME="${SNOWFLAKE_ROLE:-ACCOUNTADMIN}"
        
        # Load additional values from config file if available
        if [ -f "$CONFIG_FILE" ]; then
            COMPUTE_POOL_NAME=$(yq '.snowflake.compute_pool.name // "HOL_COMPUTE_POOL_HIGHMEM"' "$CONFIG_FILE")
            STAGE_NAME_REVIEW=$(yq '.data.stages.review_stage.name // "REVIEW_STAGE"' "$CONFIG_FILE")
            STAGE_NAME_REVIEWS=$(yq '.data.stages.reviews_text_stage.name // "REVIEWS_TEXT_STAGE"' "$CONFIG_FILE")
            NETWORK_RULE_NAME=$(yq '.snowflake.network_rule.name // "INTERNET_ACCESS_RULE"' "$CONFIG_FILE")
            INTEGRATION_NAME=$(yq '.snowflake.external_access_integration.name // "ALLOW_ALL_ACCESS_INTEGRATION"' "$CONFIG_FILE")
            WAREHOUSE_SIZE=$(yq '.snowflake.warehouse.size // "LARGE"' "$CONFIG_FILE")
            MAX_NODES=$(yq '.snowflake.compute_pool.max_nodes // "2"' "$CONFIG_FILE")
            
            # Get additional config for comprehensive setup
            COMPUTE_POOL_FAMILY=$(yq '.snowflake.compute_pool.family // "HIGHMEM_X64_M"' "$CONFIG_FILE")
            MIN_NODES=$(yq '.snowflake.compute_pool.min_nodes // "1"' "$CONFIG_FILE")
            AUTO_SUSPEND=$(yq '.snowflake.compute_pool.auto_suspend // "3600"' "$CONFIG_FILE")
            REVIEW_STAGE_URL=$(yq '.data.stages.review_stage.url // "s3://sfquickstarts/vhol_building_ml_models_to_crack_the_code_of_customer_conversions/csv/"' "$CONFIG_FILE")
            REVIEWS_STAGE_URL=$(yq '.data.stages.reviews_text_stage.url // "s3://sfquickstarts/vhol_building_ml_models_to_crack_the_code_of_customer_conversions/txt/"' "$CONFIG_FILE")
        else
            # Fallback defaults when no config file
            COMPUTE_POOL_NAME="HOL_COMPUTE_POOL_HIGHMEM"
            STAGE_NAME_REVIEW="REVIEW_STAGE"
            STAGE_NAME_REVIEWS="REVIEWS_TEXT_STAGE"
            NETWORK_RULE_NAME="INTERNET_ACCESS_RULE"
            INTEGRATION_NAME="ALLOW_ALL_ACCESS_INTEGRATION"
            WAREHOUSE_SIZE="LARGE"
            MAX_NODES="2"
            COMPUTE_POOL_FAMILY="HIGHMEM_X64_M"
            MIN_NODES="1"
            AUTO_SUSPEND="3600"
            REVIEW_STAGE_URL="s3://sfquickstarts/vhol_building_ml_models_to_crack_the_code_of_customer_conversions/csv/"
            REVIEWS_STAGE_URL="s3://sfquickstarts/vhol_building_ml_models_to_crack_the_code_of_customer_conversions/txt/"
        fi
        
        log "GitHub Actions Mode - Environment: $ENV"
        log "  Database: $DATABASE_NAME"
        log "  Schema: $SCHEMA_NAME"
        log "  Warehouse: $WAREHOUSE_NAME (Size: $WAREHOUSE_SIZE)"
        log "  Config Source: Environment Variables + $CONFIG_FILE defaults"
        
    elif [ -f "$CONFIG_FILE" ]; then
        log "Using comprehensive configuration from $CONFIG_FILE"
        
        # Core Snowflake resources
        WAREHOUSE_NAME=$(yq '.snowflake.warehouse.name' "$CONFIG_FILE")
        DATABASE_NAME=$(yq '.snowflake.database.name' "$CONFIG_FILE")
        SCHEMA_NAME=$(yq '.snowflake.schema.name' "$CONFIG_FILE")
        ROLE_NAME=$(yq '.snowflake.role.name' "$CONFIG_FILE")
        WAREHOUSE_SIZE=$(yq '.snowflake.warehouse.size' "$CONFIG_FILE")
        
        # Compute and networking
        COMPUTE_POOL_NAME=$(yq '.snowflake.compute_pool.name' "$CONFIG_FILE")
        COMPUTE_POOL_FAMILY=$(yq '.snowflake.compute_pool.family' "$CONFIG_FILE")
        MIN_NODES=$(yq '.snowflake.compute_pool.min_nodes' "$CONFIG_FILE")
        MAX_NODES=$(yq '.snowflake.compute_pool.max_nodes' "$CONFIG_FILE")
        AUTO_SUSPEND=$(yq '.snowflake.compute_pool.auto_suspend' "$CONFIG_FILE")
        NETWORK_RULE_NAME=$(yq '.snowflake.network_rule.name' "$CONFIG_FILE")
        INTEGRATION_NAME=$(yq '.snowflake.external_access_integration.name' "$CONFIG_FILE")
        
        # Data stages
        STAGE_NAME_REVIEW=$(yq '.data.stages.review_stage.name' "$CONFIG_FILE")
        STAGE_NAME_REVIEWS=$(yq '.data.stages.reviews_text_stage.name' "$CONFIG_FILE")
        REVIEW_STAGE_URL=$(yq '.data.stages.review_stage.url' "$CONFIG_FILE")
        REVIEWS_STAGE_URL=$(yq '.data.stages.reviews_text_stage.url' "$CONFIG_FILE")
        
        # File formats
        CSV_FORMAT_NAME=$(yq '.data.file_formats.csv_format.name' "$CONFIG_FILE")
        
        log "YAML Config Mode - Environment: $ENV"
        log "  Config File: $CONFIG_FILE"
        log "  Database: $DATABASE_NAME"
        log "  Schema: $SCHEMA_NAME"
        log "  Warehouse: $WAREHOUSE_NAME (Size: $WAREHOUSE_SIZE)"
        log "  Compute Pool: $COMPUTE_POOL_NAME ($COMPUTE_POOL_FAMILY, $MIN_NODES-$MAX_NODES nodes)"
        
    else
        error "Neither environment variables nor configuration file $CONFIG_FILE found. Please provide SNOWFLAKE_DATABASE, SNOWFLAKE_SCHEMA, SNOWFLAKE_WAREHOUSE environment variables or create $CONFIG_FILE"
    fi
    
    # Set defaults for values that might be missing
    CSV_FORMAT_NAME="${CSV_FORMAT_NAME:-HOL_CSV_FORMAT}"
    
    log "Configuration loaded successfully (environment: $ENV)"
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging function
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Check if Snowflake CLI is installed
check_cli() {
    if ! command -v snow &> /dev/null; then
        error "Snowflake CLI is not installed. Please install it first: https://docs.snowflake.com/en/developer-guide/snowflake-cli-v2/installation/installation"
    fi
    log "Snowflake CLI is available"
}

# Create warehouse
create_warehouse() {
    log "Creating warehouse: $WAREHOUSE_NAME (size: $WAREHOUSE_SIZE)"
    snow sql --query "CREATE WAREHOUSE IF NOT EXISTS $WAREHOUSE_NAME
        WAREHOUSE_SIZE = $WAREHOUSE_SIZE
        WAREHOUSE_TYPE = STANDARD
        RESOURCE_CONSTRAINT = STANDARD_GEN_2;" || warn "Failed to create warehouse"
}

# Create database and schema
create_database_schema() {
    log "Creating database: $DATABASE_NAME"
    snow sql --query "CREATE DATABASE IF NOT EXISTS $DATABASE_NAME;" || warn "Failed to create database"
    
    log "Creating schema: $SCHEMA_NAME"
    snow sql --query "CREATE SCHEMA IF NOT EXISTS $DATABASE_NAME.$SCHEMA_NAME;" || warn "Failed to create schema"
}

# Create tables
create_tables() {
    log "Creating TABULAR_DATA table"
    snow sql --query "CREATE TABLE IF NOT EXISTS $DATABASE_NAME.$SCHEMA_NAME.TABULAR_DATA (
        UUID STRING,
        PRODUCT_TYPE STRING,
        PRODUCT_LAYOUT STRING,
        PAGE_LOAD_TIME FLOAT,
        PRODUCT_RATING INT,
        PURCHASE_DECISION INT
    );" || warn "Failed to create TABULAR_DATA table"
    
    log "Creating REVIEWS table"
    snow sql --query "CREATE TABLE IF NOT EXISTS $DATABASE_NAME.$SCHEMA_NAME.REVIEWS (
        UUID STRING,
        REVIEW_TEXT STRING,
        REVIEW_QUALITY STRING,
        REVIEW_SENTIMENT FLOAT
    );" || warn "Failed to create REVIEWS table"
}

# Create network rule and external access integration
create_network_integration() {
    log "Creating network rule: $NETWORK_RULE_NAME"
    snow sql --query "CREATE OR REPLACE NETWORK RULE $NETWORK_RULE_NAME 
        MODE = EGRESS 
        TYPE = HOST_PORT 
        VALUE_LIST = ('0.0.0.0:443', '0.0.0.0:80');" || warn "Failed to create network rule"
    
    log "Creating external access integration: $INTEGRATION_NAME"
    snow sql --query "CREATE OR REPLACE EXTERNAL ACCESS INTEGRATION $INTEGRATION_NAME 
        ALLOWED_NETWORK_RULES = ($NETWORK_RULE_NAME) 
        ENABLED = true;" || warn "Failed to create external access integration"
}

# Create role and grant permissions
create_role_permissions() {
    log "Creating role: $ROLE_NAME"
    snow sql --query "CREATE ROLE IF NOT EXISTS $ROLE_NAME;" || warn "Failed to create role"
    
    log "Granting permissions to role"
    snow sql --query "GRANT ALL PRIVILEGES ON INTEGRATION $INTEGRATION_NAME TO ROLE $ROLE_NAME;" || warn "Failed to grant integration privileges"
    snow sql --query "GRANT EXECUTE TASK ON ACCOUNT TO ROLE $ROLE_NAME;" || warn "Failed to grant task execution"
    snow sql --query "GRANT ALL PRIVILEGES ON DATABASE $DATABASE_NAME TO ROLE $ROLE_NAME;" || warn "Failed to grant database privileges"
    snow sql --query "GRANT ALL PRIVILEGES ON SCHEMA $DATABASE_NAME.$SCHEMA_NAME TO ROLE $ROLE_NAME;" || warn "Failed to grant schema privileges"
    snow sql --query "GRANT ALL PRIVILEGES ON TABLE $DATABASE_NAME.$SCHEMA_NAME.TABULAR_DATA TO ROLE $ROLE_NAME;" || warn "Failed to grant table privileges"
    snow sql --query "GRANT ALL PRIVILEGES ON TABLE $DATABASE_NAME.$SCHEMA_NAME.REVIEWS TO ROLE $ROLE_NAME;" || warn "Failed to grant reviews table privileges"
    snow sql --query "GRANT USAGE ON WAREHOUSE $WAREHOUSE_NAME TO ROLE $ROLE_NAME;" || warn "Failed to grant warehouse usage"
}

# Create compute pool using CLI
create_compute_pool() {
    log "Creating compute pool: $COMPUTE_POOL_NAME (family: $COMPUTE_POOL_FAMILY, nodes: $MIN_NODES-$MAX_NODES)"
    snow spcs compute-pool create $COMPUTE_POOL_NAME \
        --family "$COMPUTE_POOL_FAMILY" \
        --min-nodes="$MIN_NODES" \
        --max-nodes="$MAX_NODES" \
        --if-not-exists || warn "Failed to create compute pool"
    
    log "Granting compute pool usage to role"
    snow sql --query "GRANT USAGE ON COMPUTE POOL $COMPUTE_POOL_NAME TO ROLE $ROLE_NAME;" || warn "Failed to grant compute pool usage"
}

# Grant role to current user
grant_role_to_user() {
    log "Granting role to current user"
    snow sql --query "EXECUTE IMMEDIATE \$$
    DECLARE 
        stmt STRING;
    BEGIN
        stmt := CONCAT('GRANT ROLE $ROLE_NAME TO USER ', CURRENT_USER(), ';');
        EXECUTE IMMEDIATE stmt;
    END;
    \$$;" || warn "Failed to grant role to user"
}

# Create stages
create_stages() {
    log "Switching to role: $ROLE_NAME"
    snow sql --query "USE ROLE $ROLE_NAME;" || warn "Failed to switch role"
    
    log "Creating stage: $STAGE_NAME_REVIEW"
    snow sql --query "CREATE STAGE IF NOT EXISTS $DATABASE_NAME.$SCHEMA_NAME.$STAGE_NAME_REVIEW
        URL = '$REVIEW_STAGE_URL'
        DIRECTORY = (ENABLE = TRUE)
        FILE_FORMAT = (TYPE = 'CSV' FIELD_OPTIONALLY_ENCLOSED_BY = '\"');" || warn "Failed to create review stage"
    
    log "Creating stage: $STAGE_NAME_REVIEWS"
    snow sql --query "CREATE STAGE IF NOT EXISTS $DATABASE_NAME.$SCHEMA_NAME.$STAGE_NAME_REVIEWS
        URL = '$REVIEWS_STAGE_URL'
        DIRECTORY = (ENABLE = TRUE);" || warn "Failed to create reviews stage"
}

# Create file format
create_file_format() {
    log "Creating file format: $CSV_FORMAT_NAME"
    snow sql --query "CREATE FILE FORMAT IF NOT EXISTS $CSV_FORMAT_NAME
        TYPE = 'CSV'
        FIELD_OPTIONALLY_ENCLOSED_BY = '\"';" || warn "Failed to create file format"
}

# Load data
load_data() {
    log "Loading tabular data"
    snow sql --query "INSERT INTO $DATABASE_NAME.$SCHEMA_NAME.TABULAR_DATA (
        UUID,
        PRODUCT_TYPE,
        PRODUCT_LAYOUT,
        PAGE_LOAD_TIME,
        PRODUCT_RATING,
        PURCHASE_DECISION
    )
    SELECT
        t.\$1,
        t.\$2,
        t.\$3,
        t.\$4::FLOAT,
        t.\$5::INT,
        t.\$6::INT
    FROM @$STAGE_NAME_REVIEW/tabular_table.csv (FILE_FORMAT => $CSV_FORMAT_NAME) t;" || warn "Failed to load tabular data"
    
    log "Loading reviews data"
    snow sql --query "INSERT INTO $DATABASE_NAME.$SCHEMA_NAME.REVIEWS (
        UUID,
        REVIEW_TEXT,
        REVIEW_QUALITY
    )
    SELECT
        t.\$1,
        t.\$2,
        t.\$3
    FROM @$STAGE_NAME_REVIEW (FILE_FORMAT => $CSV_FORMAT_NAME) t
    WHERE REGEXP_LIKE(METADATA\$FILENAME, '.*review_table__.*\\.csv\$');" || warn "Failed to load reviews data"
}

# Verify setup
verify_setup() {
    log "Verifying setup..."
    
    # Check warehouse
    WAREHOUSE_COUNT=$(snow sql --query "SHOW WAREHOUSES LIKE '$WAREHOUSE_NAME';" --format json | jq length)
    if [ "$WAREHOUSE_COUNT" -gt 0 ]; then
        log "✓ Warehouse $WAREHOUSE_NAME exists"
    else
        warn "✗ Warehouse $WAREHOUSE_NAME not found"
    fi
    
    # Check database and schema
    DB_COUNT=$(snow sql --query "SHOW DATABASES LIKE '$DATABASE_NAME';" --format json | jq length)
    if [ "$DB_COUNT" -gt 0 ]; then
        log "✓ Database $DATABASE_NAME exists"
    else
        warn "✗ Database $DATABASE_NAME not found"
    fi
    
    # Check compute pool
    POOL_STATUS=$(snow spcs compute-pool status $COMPUTE_POOL_NAME --format json 2>/dev/null | jq -r '.status // "NOT_FOUND"')
    if [ "$POOL_STATUS" != "NOT_FOUND" ]; then
        log "✓ Compute pool $COMPUTE_POOL_NAME exists (Status: $POOL_STATUS)"
    else
        warn "✗ Compute pool $COMPUTE_POOL_NAME not found"
    fi
    
    # Check data
    TABULAR_COUNT=$(snow sql --query "SELECT COUNT(*) as count FROM $DATABASE_NAME.$SCHEMA_NAME.TABULAR_DATA;" --format json | jq -r '.[0].count')
    REVIEWS_COUNT=$(snow sql --query "SELECT COUNT(*) as count FROM $DATABASE_NAME.$SCHEMA_NAME.REVIEWS;" --format json | jq -r '.[0].count')
    
    log "✓ Tabular data rows: $TABULAR_COUNT"
    log "✓ Reviews data rows: $REVIEWS_COUNT"
}

# Main execution
main() {
    log "Starting Snowflake Customer Conversion ML Pipeline Setup"
    
    check_cli
    load_config
    
    # Show what will be created
    log "Environment-Aware Resource Creation:"
    log "  🎯 Environment: $ENV"
    log "  🏢 Database: $DATABASE_NAME"
    log "  📂 Schema: $SCHEMA_NAME"
    log "  ⚡ Warehouse: $WAREHOUSE_NAME (Size: $WAREHOUSE_SIZE)"
    log "  🖥️  Compute Pool: $COMPUTE_POOL_NAME (Max Nodes: $MAX_NODES)"
    log "  🌐 Integration: $INTEGRATION_NAME"
    log ""
    
    # Switch to ACCOUNTADMIN role for setup
    log "Switching to ACCOUNTADMIN role"
    snow sql --query "USE ROLE ACCOUNTADMIN;" || error "Failed to switch to ACCOUNTADMIN"
    
    create_warehouse
    create_database_schema
    create_tables
    create_network_integration
    create_role_permissions
    create_compute_pool
    grant_role_to_user
    create_stages
    create_file_format
    load_data
    
    verify_setup
    
    log "Setup completed successfully for environment: $ENV!"
    log ""
    log "🎯 Environment-Specific Resources Created:"
    log "  📊 Environment: $ENV"
    log "  🏢 Database: $DATABASE_NAME"
    log "  📂 Schema: $DATABASE_NAME.$SCHEMA_NAME"
    log "  ⚡ Warehouse: $WAREHOUSE_NAME (Size: $WAREHOUSE_SIZE)"
    log "  🔐 Role: $ROLE_NAME"
    log "  🖥️  Compute Pool: $COMPUTE_POOL_NAME (Max Nodes: $MAX_NODES)"
    log "  🌐 External Access: $INTEGRATION_NAME"
    log ""
    log "🚀 Next Steps:"
    log "  1. Deploy notebooks via GitHub Actions (they will connect to these resources)"
    log "  2. Run the ML pipeline in this isolated $ENV environment"
    log "  3. If this is dev, changes won't affect staging/production"
    log ""
    log "📋 For GitHub Actions, ensure these environment variables match:"
    log "  SNOWFLAKE_DATABASE=$DATABASE_NAME"
    log "  SNOWFLAKE_SCHEMA=$SCHEMA_NAME"
    log "  SNOWFLAKE_WAREHOUSE=$WAREHOUSE_NAME"
}

# Cleanup function (optional)
cleanup() {
    read -p "Are you sure you want to cleanup all resources? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Cleaning up resources..."
        snow sql --query "USE ROLE ACCOUNTADMIN;"
        snow spcs compute-pool drop $COMPUTE_POOL_NAME --if-exists || warn "Failed to drop compute pool"
        snow sql --query "DROP INTEGRATION IF EXISTS $INTEGRATION_NAME;" || warn "Failed to drop integration"
        snow sql --query "DROP NETWORK RULE IF EXISTS $NETWORK_RULE_NAME;" || warn "Failed to drop network rule"
        snow sql --query "DROP DATABASE IF EXISTS $DATABASE_NAME CASCADE;" || warn "Failed to drop database"
        snow sql --query "DROP WAREHOUSE IF EXISTS $WAREHOUSE_NAME;" || warn "Failed to drop warehouse"
        snow sql --query "DROP ROLE IF EXISTS $ROLE_NAME;" || warn "Failed to drop role"
        log "Cleanup completed"
    fi
}

# Handle command line arguments
case "${1:-}" in
    "cleanup")
        cleanup
        ;;
    "verify")
        load_config
        verify_setup
        ;;
    *)
        main
        ;;
esac 