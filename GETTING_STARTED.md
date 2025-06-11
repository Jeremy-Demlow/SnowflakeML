# Getting Started - Customer Conversion ML Pipeline

## 🚀 Quick Setup (5 minutes)

### 1. Prerequisites Check
```bash
# Check if Snowflake CLI is installed
snow --version

# If not installed:
pip install snowflake-cli-labs

# Configure your Snowflake connection
snow connection add --connection-name default \
  --account <your-account> \
  --user <your-username> \
  --role ACCOUNTADMIN
```

### 2. Infrastructure Setup
```bash
# Clone or ensure you're in the project directory
cd /path/to/SnowflakeML

# Run the automated setup
./cli-setup.sh

# Verify everything is created
./cli-setup.sh verify
```

### 3. Run the ML Pipeline
```bash
# Option A: Use Jupyter Notebook
jupyter notebook notebook.ipynb

# Option B: Use Snowflake CLI (if supported)
snow notebook execute notebook.ipynb
```

### 4. View Results
```bash
# Run Streamlit dashboard locally
streamlit run streamlit.py

# Access at: http://localhost:8501
```

## 🐳 Production Deployment (Optional)

### Prerequisites
- Docker installed and running
- SPCS enabled on your Snowflake account

### Deploy to SPCS
```bash
# Deploy containerized services
./spcs-deploy.sh

# Monitor deployment
./spcs-deploy.sh monitor

# Get service URLs
./spcs-deploy.sh endpoints
```

## 🔧 Common Commands

### Infrastructure Management
```bash
# Setup everything
./cli-setup.sh

# Verify setup
./cli-setup.sh verify

# Cleanup all resources
./cli-setup.sh cleanup
```

### SPCS Management
```bash
# Deploy services
./spcs-deploy.sh

# Monitor services
./spcs-deploy.sh monitor

# Get endpoints
./spcs-deploy.sh endpoints

# Cleanup SPCS resources
./spcs-deploy.sh cleanup
```

### Manual Snowflake CLI Commands
```bash
# Check compute pool status
snow spcs compute-pool status HOL_COMPUTE_POOL_HIGHMEM

# List services
snow spcs service list --database=HOL_DB --schema=HOL_SCHEMA --role=HOL_ROLE

# Check warehouse status
snow sql --query "SHOW WAREHOUSES LIKE 'HOL_WAREHOUSE'"
```

## 📊 What Gets Created

### Snowflake Resources
- **Warehouse**: `HOL_WAREHOUSE` (MEDIUM, auto-suspend)
- **Database**: `HOL_DB`
- **Schema**: `HOL_SCHEMA`
- **Role**: `HOL_ROLE` (with appropriate permissions)
- **Compute Pool**: `HOL_COMPUTE_POOL_HIGHMEM` (1-3 nodes)
- **Tables**: `TABULAR_DATA`, `REVIEWS`
- **Stages**: `REVIEW_STAGE`, `REVIEWS` (connected to S3)

### SPCS Resources (if deployed)
- **Image Repository**: `ml_models_repo`
- **Streamlit Service**: `customer_conversion_app`
- **ML API Service**: `ml_inference_service`

## 🎯 Key Features

### Automated Setup
- ✅ One-command infrastructure creation
- ✅ Automatic data loading from S3
- ✅ Role and permission management
- ✅ Compute resource provisioning

### ML Pipeline
- ✅ Ray-based distributed processing
- ✅ HuggingFace transformer models
- ✅ Snowflake Cortex AI integration
- ✅ XGBoost model training

### Production Ready
- ✅ Containerized deployment
- ✅ Auto-scaling services
- ✅ Health monitoring
- ✅ Load balancing

## 🚨 Troubleshooting

### Connection Issues
```bash
# Test your connection
snow connection test

# List available connections
snow connection list

# Re-configure if needed
snow connection add
```

### Permission Issues
```bash
# Ensure you're using ACCOUNTADMIN role
snow sql --query "USE ROLE ACCOUNTADMIN;"

# Check current role
snow sql --query "SELECT CURRENT_ROLE();"
```

### Resource Issues
```bash
# Check if resources exist
snow sql --query "SHOW WAREHOUSES;"
snow sql --query "SHOW DATABASES;"
snow spcs compute-pool list
```

## 💡 Tips

1. **Start Small**: Use the basic setup first before moving to SPCS
2. **Check Logs**: Use `snow spcs service logs` for troubleshooting
3. **Monitor Costs**: Warehouses and compute pools consume credits
4. **Use Auto-Suspend**: Automatically configured to minimize costs
5. **Environment Variables**: Configure different environments in `config.yaml`

## 📚 Next Steps

1. **Explore the Notebook**: Understand the ML pipeline step-by-step
2. **Customize Models**: Modify model parameters in the configuration
3. **Add Data Sources**: Connect your own data sources
4. **Production Deployment**: Use SPCS for scalable production deployment
5. **Monitoring**: Set up custom monitoring and alerting

## 🔗 Quick Links

- [Full Documentation](PROJECT_README.md)
- [Configuration Reference](config.yaml)
- [Original Setup SQL](setup.sql)
- [Snowflake CLI Docs](https://docs.snowflake.com/en/developer-guide/snowflake-cli-v2/index)

---

**Need help?** Check the troubleshooting section or open an issue with your error logs. 