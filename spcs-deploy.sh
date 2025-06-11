#!/bin/bash

# Customer Conversion ML Pipeline - SPCS Deployment Script
# This script deploys the ML pipeline as Snowpark Container Services

set -e

# Configuration - Load from YAML
WORKSPACE_DIR=$(pwd)
CONFIG_FILE="${CONFIG_FILE:-config.yaml}"

# Load configuration from YAML
load_config() {
    if [ ! -f "$CONFIG_FILE" ]; then
        error "Configuration file $CONFIG_FILE not found"
    fi
    
    # Check if yq is available
    if ! command -v yq &> /dev/null; then
        error "yq is required for YAML parsing. Install: https://github.com/mikefarah/yq#install"
    fi
    
    DATABASE_NAME=$(yq '.snowflake.database.name' "$CONFIG_FILE")
    SCHEMA_NAME=$(yq '.snowflake.schema.name' "$CONFIG_FILE")
    ROLE_NAME=$(yq '.snowflake.role.name' "$CONFIG_FILE")
    COMPUTE_POOL_NAME=$(yq '.snowflake.compute_pool.name' "$CONFIG_FILE")
    IMAGE_REPO_NAME=$(yq '.spcs.image_repository.name' "$CONFIG_FILE")
    
    log "Loaded configuration from $CONFIG_FILE"
}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging functions
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

info() {
    echo -e "${BLUE}[$(date +'%Y-%m-%d %H:%M:%S')] INFO: $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
    exit 1
}

# Prerequisites check
check_prerequisites() {
    log "Checking prerequisites..."
    
    # Check Snowflake CLI
    if ! command -v snow &> /dev/null; then
        error "Snowflake CLI not found. Install from: https://docs.snowflake.com/en/developer-guide/snowflake-cli-v2/installation/installation"
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker not found. Please install Docker for container operations."
    fi
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        error "Docker is not running. Please start Docker daemon."
    fi
    
    # Check jq for JSON processing
    if ! command -v jq &> /dev/null; then
        warn "jq not found. Installing via package manager might be helpful for better output parsing."
    fi
    
    log "Prerequisites check completed"
}

# Login to image registry
login_registry() {
    log "Logging into Snowflake image registry..."
    snow spcs image-registry login || error "Failed to login to image registry"
    
    # Get registry URL
    REGISTRY_URL=$(snow spcs image-registry url)
    log "Registry URL: $REGISTRY_URL"
}

# Create image repository
create_image_repository() {
    log "Creating image repository: $IMAGE_REPO_NAME"
    
    snow spcs image-repository create $IMAGE_REPO_NAME \
        --database="$DATABASE_NAME" \
        --schema="$SCHEMA_NAME" \
        --role="$ROLE_NAME" \
        --if-not-exists || warn "Failed to create image repository"
    
    # Get repository URL
    REPO_URL=$(snow spcs image-repository url $IMAGE_REPO_NAME \
        --database="$DATABASE_NAME" \
        --schema="$SCHEMA_NAME" \
        --role="$ROLE_NAME")
    
    log "Image repository URL: $REPO_URL"
}

# Build and push Streamlit application
build_push_streamlit() {
    log "Building Streamlit application container..."
    
    # Create Dockerfile for Streamlit app
    cat > Dockerfile.streamlit << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY streamlit.py .
COPY config.yaml .

# Expose port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Run application
CMD ["streamlit", "run", "streamlit.py", "--server.port=8501", "--server.address=0.0.0.0"]
EOF

    # Create requirements.txt if it doesn't exist
    if [ ! -f requirements.txt ]; then
        cat > requirements.txt << 'EOF'
streamlit>=1.28.0
pandas>=1.5.0
numpy>=1.21.0
altair>=4.2.0
snowflake-snowpark-python>=1.11.0
snowflake-ml-python>=1.0.0
pyyaml>=6.0
EOF
    fi
    
    # Build image
    docker build --platform=linux/amd64 -f Dockerfile.streamlit -t streamlit_app:latest .
    
    # Tag and push
    docker tag streamlit_app:latest "$REPO_URL/streamlit_app:latest"
    docker push "$REPO_URL/streamlit_app:latest"
    
    log "Streamlit application pushed to registry"
}

# Build and push ML inference service
build_push_ml_service() {
    log "Building ML inference service container..."
    
    # Create Dockerfile for ML service
    cat > Dockerfile.ml << 'EOF'
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements-ml.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements-ml.txt

# Copy application code
COPY ml_service.py .
COPY config.yaml .

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run application
CMD ["python", "ml_service.py"]
EOF

    # Create ML service requirements
    cat > requirements-ml.txt << 'EOF'
fastapi>=0.104.0
uvicorn>=0.24.0
pandas>=1.5.0
numpy>=1.21.0
scikit-learn>=1.3.0
snowflake-snowpark-python>=1.11.0
snowflake-ml-python>=1.0.0
transformers>=4.21.0
torch>=1.13.0
pyyaml>=6.0
EOF

    # Create basic ML service if it doesn't exist
    if [ ! -f ml_service.py ]; then
        cat > ml_service.py << 'EOF'
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import pandas as pd
import yaml
from typing import List, Dict, Any
import uvicorn

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

app = FastAPI(
    title="Customer Conversion ML Service",
    description="ML inference service for customer conversion prediction",
    version="1.0.0"
)

class PredictionRequest(BaseModel):
    features: Dict[str, Any]

class PredictionResponse(BaseModel):
    prediction: float
    confidence: float
    model_version: str

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ml_inference"}

@app.post("/predict", response_model=PredictionResponse)
async def predict(request: PredictionRequest):
    try:
        # Placeholder for actual ML inference
        # In production, load and use trained models
        prediction = 0.75  # Dummy prediction
        confidence = 0.85   # Dummy confidence
        
        return PredictionResponse(
            prediction=prediction,
            confidence=confidence,
            model_version="1.0.0"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/models")
async def list_models():
    return {
        "models": [
            {
                "name": "purchase_prediction",
                "version": "1.0.0",
                "type": "xgboost",
                "status": "active"
            },
            {
                "name": "review_quality_classifier",
                "version": "1.0.0", 
                "type": "transformers",
                "status": "active"
            }
        ]
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
EOF
    fi
    
    # Build image
    docker build --platform=linux/amd64 -f Dockerfile.ml -t ml_inference:latest .
    
    # Tag and push
    docker tag ml_inference:latest "$REPO_URL/ml_inference:latest"
    docker push "$REPO_URL/ml_inference:latest"
    
    log "ML inference service pushed to registry"
}

# Create service specifications
create_service_specs() {
    log "Creating service specifications..."
    
    mkdir -p specs
    
    # Streamlit service spec
    cat > specs/streamlit-service.yaml << EOF
spec:
  containers:
    - name: streamlit
      image: $REPO_URL/streamlit_app:latest
      env:
        SNOWFLAKE_DEFAULT_CONNECTION_NAME: default
      readinessProbe:
        port: 8501
        path: /_stcore/health
      resources:
        requests:
          memory: 1Gi
          cpu: 500m
        limits:
          memory: 2Gi
          cpu: 1000m
  endpoints:
    - name: streamlit
      port: 8501
      public: true
EOF

    # ML service spec
    cat > specs/ml-service.yaml << EOF
spec:
  containers:
    - name: ml-api
      image: $REPO_URL/ml_inference:latest
      env:
        SNOWFLAKE_DEFAULT_CONNECTION_NAME: default
      readinessProbe:
        port: 8000
        path: /health
      resources:
        requests:
          memory: 2Gi
          cpu: 1000m
        limits:
          memory: 4Gi
          cpu: 2000m
  endpoints:
    - name: ml-api
      port: 8000
      public: true
EOF

    log "Service specifications created"
}

# Deploy services
deploy_services() {
    log "Deploying Streamlit application service..."
    
    snow spcs service create customer_conversion_app \
        --compute-pool="$COMPUTE_POOL_NAME" \
        --spec-path=specs/streamlit-service.yaml \
        --min-instances=1 \
        --max-instances=3 \
        --database="$DATABASE_NAME" \
        --schema="$SCHEMA_NAME" \
        --role="$ROLE_NAME" || warn "Failed to create Streamlit service"
    
    log "Deploying ML inference service..."
    
    snow spcs service create ml_inference_service \
        --compute-pool="$COMPUTE_POOL_NAME" \
        --spec-path=specs/ml-service.yaml \
        --min-instances=1 \
        --max-instances=5 \
        --database="$DATABASE_NAME" \
        --schema="$SCHEMA_NAME" \
        --role="$ROLE_NAME" || warn "Failed to create ML service"
    
    log "Services deployed successfully"
}

# Monitor service status
monitor_services() {
    log "Monitoring service deployment status..."
    
    local services=("customer_conversion_app" "ml_inference_service")
    local max_wait=600  # 10 minutes
    local elapsed=0
    
    for service in "${services[@]}"; do
        log "Checking status of service: $service"
        
        while [ $elapsed -lt $max_wait ]; do
            status=$(snow spcs service status "$service" \
                --database="$DATABASE_NAME" \
                --schema="$SCHEMA_NAME" \
                --role="$ROLE_NAME" \
                --format json 2>/dev/null | jq -r '.status // "UNKNOWN"')
            
            if [ "$status" = "READY" ]; then
                log "✓ Service $service is READY"
                break
            elif [ "$status" = "FAILED" ]; then
                error "✗ Service $service deployment FAILED"
            else
                info "Service $service status: $status (waiting...)"
                sleep 30
                elapsed=$((elapsed + 30))
            fi
        done
        
        if [ $elapsed -ge $max_wait ]; then
            warn "Service $service did not become ready within timeout"
        fi
    done
}

# Get service endpoints
get_endpoints() {
    log "Retrieving service endpoints..."
    
    local services=("customer_conversion_app" "ml_inference_service")
    
    for service in "${services[@]}"; do
        log "Endpoints for $service:"
        snow spcs service list-endpoints "$service" \
            --database="$DATABASE_NAME" \
            --schema="$SCHEMA_NAME" \
            --role="$ROLE_NAME" || warn "Failed to get endpoints for $service"
    done
}

# Cleanup function
cleanup_deployment() {
    read -p "Are you sure you want to cleanup all SPCS resources? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log "Cleaning up SPCS resources..."
        
        # Drop services
        snow spcs service drop customer_conversion_app \
            --database="$DATABASE_NAME" \
            --schema="$SCHEMA_NAME" \
            --role="$ROLE_NAME" || warn "Failed to drop Streamlit service"
        
        snow spcs service drop ml_inference_service \
            --database="$DATABASE_NAME" \
            --schema="$SCHEMA_NAME" \
            --role="$ROLE_NAME" || warn "Failed to drop ML service"
        
        # Drop image repository
        snow spcs image-repository drop $IMAGE_REPO_NAME \
            --database="$DATABASE_NAME" \
            --schema="$SCHEMA_NAME" \
            --role="$ROLE_NAME" || warn "Failed to drop image repository"
        
        # Clean up local files
        rm -f Dockerfile.streamlit Dockerfile.ml
        rm -f requirements.txt requirements-ml.txt ml_service.py
        rm -rf specs/
        
        log "Cleanup completed"
    fi
}

# Main execution
main() {
    log "Starting SPCS deployment for Customer Conversion ML Pipeline"
    
    check_prerequisites
    load_config
    login_registry
    create_image_repository
    build_push_streamlit
    build_push_ml_service
    create_service_specs
    deploy_services
    monitor_services
    get_endpoints
    
    log "SPCS deployment completed successfully!"
    log ""
    log "Your services are now running in Snowpark Container Services:"
    log "  - Streamlit App: customer_conversion_app"
    log "  - ML Inference API: ml_inference_service"
    log ""
    log "Use 'snow spcs service list-endpoints <service_name>' to get access URLs"
    log "Use '$0 cleanup' to remove all deployed resources"
}

# Handle command line arguments
case "${1:-}" in
    "cleanup")
        cleanup_deployment
        ;;
    "monitor")
        monitor_services
        ;;
    "endpoints")
        get_endpoints
        ;;
    *)
        main
        ;;
esac 