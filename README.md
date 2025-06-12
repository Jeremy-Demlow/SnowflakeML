# Snowflake ML DevOps Pipeline

A production-ready DevOps pipeline for deploying Machine Learning notebooks and infrastructure to Snowflake, showcasing modern MLOps practices with automated CI/CD, environment management, and infrastructure as code.

## 🚀 What We've Built

This project demonstrates **enterprise-grade MLOps** for Snowflake, featuring:

### 🏗️ **Infrastructure as Code**
- **Declarative Configuration**: YAML-based infrastructure definitions (`config.yaml`, `config-production.yaml`)
- **Environment Separation**: Development, staging, and production environments with isolated resources
- **Automated Provisioning**: Warehouses, databases, schemas, compute pools, and security integrations
- **Resource Management**: Intelligent setup with dependency resolution and verification

### 🔄 **CI/CD Pipeline**
- **GitHub Actions Workflows**: Automated infrastructure setup and notebook deployment
- **Smart Connectivity**: Connection testing without database dependencies (solves chicken-and-egg problems)
- **Git Integration**: Direct deployment from GitHub repositories to Snowflake notebooks
- **Environment-Specific Deployment**: Separate pipelines for dev/staging/production

### 📊 **ML Notebook Management**
- **Automated Deployment**: Jupyter notebooks deployed as Snowflake notebooks with compute pools
- **Version Control**: Git-based versioning with branch/commit references
- **Runtime Configuration**: Configurable compute resources and external access
- **Deployment Verification**: Automated testing and validation of deployed notebooks

### 🛡️ **Security & Governance**
- **Secret Management**: GitHub secrets for credentials with environment isolation
- **Role-Based Access**: Configurable Snowflake roles and permissions
- **Network Security**: External access integrations and network rules
- **Audit Trail**: Complete deployment history and logging

## 📁 Project Structure

```
SnowflakeML/
├── 📋 config.yaml                    # Main infrastructure configuration
├── 📋 config-production.yaml         # Production-specific overrides
├── 🔧 cli-setup.sh                   # Infrastructure setup script
├── 📓 sf_nbs/                        # ML notebooks directory
│   └── ml_pipeline.ipynb             # Example ML pipeline notebook
├── 🔄 .github/workflows/             # CI/CD workflows
│   ├── infrastructure.yml            # Infrastructure setup workflow
│   └── deploy.yml                    # Notebook deployment workflow
└── 🛠️ scripts/                       # Helper scripts
    ├── setup-github-secrets.sh       # GitHub Actions configuration
    └── test-git-repo.sh              # Git repository testing
```

## 🎯 Key Features Demonstrated

### **Modern MLOps Practices**
- ✅ **Infrastructure as Code** - Declarative, version-controlled infrastructure
- ✅ **GitOps Workflow** - Git-driven deployments with automated CI/CD
- ✅ **Environment Parity** - Consistent dev/staging/production environments
- ✅ **Automated Testing** - Connection testing and deployment verification
- ✅ **Secret Management** - Secure credential handling with GitHub secrets

### **Snowflake-Specific Innovations**
- ✅ **Compute Pool Management** - Automated setup of ML compute resources
- ✅ **Git Repository Integration** - Direct GitHub-to-Snowflake deployment
- ✅ **External Access Configuration** - Secure external API access for ML workloads
- ✅ **Notebook Lifecycle Management** - Automated deployment and versioning

### **Enterprise Readiness**
- ✅ **Multi-Environment Support** - Separate dev/staging/production pipelines
- ✅ **Error Handling** - Robust error detection and reporting
- ✅ **Rollback Capability** - Version-controlled deployments enable easy rollbacks
- ✅ **Monitoring & Logging** - Comprehensive deployment tracking

## 🚀 Quick Start

### 1. **Setup GitHub Secrets**
```bash
./scripts/setup-github-secrets.sh
```

### 2. **Deploy Infrastructure**
```bash
# Development environment
ENV=development ./cli-setup.sh

# Production environment  
ENV=production ./cli-setup.sh
```

### 3. **Deploy Notebooks**
- Add notebooks to `sf_nbs/` directory
- Deploy using the helper script: `./scripts/deploy.sh dev`
- Or commit and push to trigger automated deployment
- Or manually trigger via GitHub Actions

### 4. **Verify Deployment**
```bash
./scripts/test-git-repo.sh
```

## 🎮 Deployment Commands

### **Simple Deployment Helper** (Easiest)

We've included a deployment helper script for maximum convenience:

```bash
# Quick deployments
./scripts/deploy.sh dev        # Deploy to development
./scripts/deploy.sh staging    # Deploy to staging  
./scripts/deploy.sh prod       # Deploy to production

# Infrastructure setup
./scripts/deploy.sh infra -e staging    # Setup staging infrastructure
./scripts/deploy.sh infra -f            # Force recreate dev infrastructure

# Check status
./scripts/deploy.sh status     # View recent deployments
```

### **GitHub CLI Commands** (Full Control)

Install GitHub CLI if you haven't already:
```bash
# macOS
brew install gh

# Windows
winget install --id GitHub.cli

# Linux
sudo apt install gh
```

#### **Infrastructure Deployment**
```bash
# Deploy to development
gh workflow run infrastructure.yml -f environment=development

# Deploy to staging  
gh workflow run infrastructure.yml -f environment=staging

# Deploy to production
gh workflow run infrastructure.yml -f environment=production

# Force recreate resources
gh workflow run infrastructure.yml -f environment=development -f force_recreate=true
```

#### **Notebook Deployment**
```bash
# Deploy notebooks to development
gh workflow run deploy.yml -f environment=development

# Deploy to staging
gh workflow run deploy.yml -f environment=staging

# Deploy to production  
gh workflow run deploy.yml -f environment=production

# Deploy without infrastructure setup (if infrastructure already exists)
gh workflow run deploy.yml -f environment=development -f setup_infrastructure=false
```

#### **Check Deployment Status**
```bash
# List recent workflow runs
gh run list

# Watch a specific run in real-time
gh run watch

# View logs for a specific run
gh run view <run-id> --log
```


### **Automated Triggers**

The workflows also trigger automatically:

#### **Infrastructure Workflow** triggers on:
```yaml
# When config files change
push:
  paths:
    - 'config*.yaml'
    - 'cli-setup.sh'
  branches: [main]
```

#### **Deploy Workflow** triggers on:
```yaml
# When notebooks change
push:
  paths:
    - 'sf_nbs/**'
  branches: [main]
```

### **Quick Deployment Patterns**

#### **Development Workflow**
```bash
# 1. Make changes to notebook
vim sf_nbs/ml_pipeline.ipynb

# 2. Test locally (optional)
./scripts/test-git-repo.sh

# 3. Deploy via CLI
gh workflow run deploy.yml -f environment=development

# 4. Or just push (auto-triggers)
git add . && git commit -m "Updated model" && git push
```

### **Monitoring Commands**
```bash
# Watch all workflows
gh run list --limit 10

# Monitor specific environment
gh run list --workflow=deploy.yml --json environment

# Get deployment status
gh api repos/:owner/:repo/actions/runs --jq '.workflow_runs[] | select(.name=="Deploy Notebooks") | {status, conclusion, created_at}'
```

## 🌍 Environment Management

The pipeline supports multiple deployment environments:

| Environment | Database | Schema | Use Case |
|-------------|----------|--------|----------|
| **Development** | `HOL_DB_DEV` | `HOL_SCHEMA_DEV` | Feature development and testing |
| **Staging** | `HOL_DB_STAGING` | `HOL_SCHEMA_STAGING` | Pre-production validation |
| **Production** | `HOL_DB_PROD` | `HOL_SCHEMA_PROD` | Live ML workloads |

## 🔧 Configuration

### Infrastructure Configuration (`config.yaml`)
```yaml
snowflake:
  warehouse: HOL_WAREHOUSE
  database: HOL_DB
  schema: HOL_SCHEMA
  compute_pool: HOL_COMPUTE_POOL_HIGHMEM

ml_config:
  models:
    - name: customer_churn_model
      type: classification
  ray:
    min_nodes: 1
    max_nodes: 3
```

### GitHub Actions Configuration
- **Repository Variables**: Account, user, role, warehouse settings
- **Environment Variables**: Environment-specific database/schema names
- **Secrets**: Snowflake password and sensitive credentials

## 🎉 What Makes This Special

### **Solves Real MLOps Challenges**
1. **Environment Consistency** - Same infrastructure across all environments
2. **Deployment Automation** - Zero-touch deployments from Git commits
3. **Resource Management** - Automated compute pool and warehouse management
4. **Security Integration** - Proper secret management and access controls

### **Snowflake-Native Approach**
- Leverages Snowflake's native Git integration
- Uses Snowflake compute pools for ML workloads
- Integrates with Snowflake's security model
- Utilizes Snowflake CLI for automation

### **Production-Ready Features**
- Environment isolation and promotion workflows
- Comprehensive error handling and rollback capabilities
- Audit trails and deployment verification
- Team collaboration with proper access controls

## 🏆 Why This Matters for ML Teams

### **Developer Experience**
- **Simple Workflow**: `git push` → automatic deployment
- **Local Testing**: Test infrastructure and deployments locally
- **Clear Feedback**: Detailed deployment status and error reporting

### **Operations Excellence**
- **Consistent Environments**: Eliminate "works on my machine" issues
- **Automated Rollbacks**: Quick recovery from deployment issues
- **Audit Compliance**: Complete deployment history and change tracking

### **Business Value**
- **Faster Time-to-Market**: Automated deployments reduce manual overhead
- **Reduced Risk**: Consistent, tested deployment processes
- **Scalability**: Easy replication across teams and projects


## 📚 Learn More

- [Snowflake ML Documentation](https://docs.snowflake.com/en/developer-guide/snowpark-ml/index)
- [Snowflake CLI Reference](https://docs.snowflake.com/en/developer-guide/snowflake-cli/index)
- [GitHub Actions for MLOps](https://github.com/features/actions)

---

**Built with ❄️ Snowflake • 🐙 GitHub Actions • 🐍 Python • 📊 MLOps Best Practices**

*This project demonstrates enterprise-grade MLOps for Snowflake, showcasing automated infrastructure management, CI/CD pipelines, and production-ready ML deployment workflows.*

### **Quick Reference Card**

| Scenario | Helper Script | GitHub CLI |
|----------|---------------|------------|
| **Deploy notebook to dev** | `./scripts/deploy.sh dev` | `gh workflow run deploy.yml -f environment=development` |
| **Deploy to production** | `./scripts/deploy.sh prod` | `gh workflow run deploy.yml -f environment=production` |
| **Setup new environment** | `./scripts/deploy.sh infra -e staging` | `gh workflow run infrastructure.yml -f environment=staging` |
| **Force recreate resources** | `./scripts/deploy.sh infra -f` | `gh workflow run infrastructure.yml -f environment=development -f force_recreate=true` |
| **Check deployment status** | `./scripts/deploy.sh status` | `gh run list --limit 5` |
| **Watch deployment live** | `gh run watch` | `gh run watch` |
| **Emergency rollback** | `git checkout <commit> && ./scripts/deploy.sh prod` | `git checkout <previous-commit> && gh workflow run deploy.yml -f environment=production` |

### **Troubleshooting Commands**
```bash
# Check if GitHub CLI is authenticated
gh auth status

# View failed workflow logs
gh run list --status=failure
gh run view <failed-run-id> --log

# Test local Snowflake connection
snow connection test

# Verify Git repository setup
./scripts/test-git-repo.sh

# Check environment variables
gh variable list
gh secret list
```