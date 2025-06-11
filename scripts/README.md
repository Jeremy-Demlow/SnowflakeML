# 📁 Scripts Directory

This directory contains helper scripts for testing and setting up the Snowflake ML Pipeline deployment.

## 🧪 Testing Scripts

### `test-infrastructure-setup.sh`
**Purpose**: Comprehensive testing of infrastructure setup components before running GitHub Actions workflows.

**Usage**:
```bash
# Run all infrastructure tests (recommended before first deployment)
./scripts/test-infrastructure-setup.sh

# Show help
./scripts/test-infrastructure-setup.sh --help

# Skip interactive components
./scripts/test-infrastructure-setup.sh --dry-run
```

**What it tests**:
- ✅ Required tools (Snowflake CLI, yq, bash version)
- ✅ Snowflake connection (ml_pipeline connection)
- ✅ Infrastructure setup script (cli-setup.sh syntax and components)
- ✅ Current infrastructure state (what exists vs. what needs to be created)
- ✅ GitHub Actions workflow files (YAML syntax validation)
- ✅ Notebook directory structure (sf_nbs/ directory and .ipynb files)
- ✅ GitHub environment variables (required secrets/variables)
- ✅ Infrastructure deployment dry run (with option to run actual setup)

**When to use**: 
- Before running GitHub Actions workflows for the first time
- After making changes to cli-setup.sh
- When troubleshooting infrastructure issues
- Before deploying to new environments

### `test-notebook-deployment.sh`
**Purpose**: Test notebook deployment functionality locally.

**Usage**:
```bash
# Test all notebooks in sf_nbs/
./scripts/test-notebook-deployment.sh

# Test specific notebook
./scripts/test-notebook-deployment.sh sf_nbs/my_notebook.ipynb
```

**What it tests**:
- ✅ Notebook file validation
- ✅ Snowflake Git repository setup
- ✅ Notebook deployment simulation
- ✅ External access configuration

### `test-workflow-locally.sh`
**Purpose**: General workflow testing including tools and configuration validation.

**Usage**:
```bash
./scripts/test-workflow-locally.sh
```

**What it tests**:
- ✅ Required tools installation
- ✅ Snowflake connection
- ✅ Configuration files
- ✅ Python dependencies
- ✅ GitHub Actions workflow syntax

## ⚙️ Setup Scripts

### `setup-github-secrets.sh`
**Purpose**: Automatically configure GitHub repository secrets and variables.

**Usage**:
```bash
./scripts/setup-github-secrets.sh
```

**What it does**:
- 🔧 Sets up GitHub repository variables (SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, etc.)
- 🔐 Sets up GitHub repository secrets (SNOWFLAKE_PASSWORD)
- 📋 Uses GitHub CLI to automate the configuration
- ✅ Validates the setup after configuration

**Requirements**:
- GitHub CLI (`gh`) installed and authenticated
- Repository write permissions

## 🚀 Recommended Testing Workflow

### First Time Setup:
```bash
# 1. Test infrastructure setup comprehensively
./scripts/test-infrastructure-setup.sh

# 2. Set up GitHub secrets and variables
./scripts/setup-github-secrets.sh

# 3. Test notebook deployment
./scripts/test-notebook-deployment.sh

# 4. Run general workflow tests
./scripts/test-workflow-locally.sh
```

### Before Each Deployment:
```bash
# Quick infrastructure check
./scripts/test-infrastructure-setup.sh --dry-run

# Test notebook deployment
./scripts/test-notebook-deployment.sh
```

### Troubleshooting:
```bash
# Comprehensive testing with interactive fixes
./scripts/test-infrastructure-setup.sh

# Check specific components
./scripts/test-workflow-locally.sh
```

## 📋 Test Categories

### Infrastructure Tests (`test-infrastructure-setup.sh`)
- **Scope**: Complete infrastructure readiness
- **Focus**: GitHub Actions preparation, resource validation
- **Interactive**: Yes (offers to create directories, run setup)
- **Time**: ~2-5 minutes
- **Best for**: First-time setup, infrastructure changes

### Notebook Tests (`test-notebook-deployment.sh`)
- **Scope**: Notebook deployment pipeline
- **Focus**: Git repository, notebook creation, access configuration
- **Interactive**: Moderate
- **Time**: ~1-3 minutes
- **Best for**: Notebook changes, deployment validation

### General Tests (`test-workflow-locally.sh`)
- **Scope**: Overall workflow components
- **Focus**: Tools, connections, configuration files
- **Interactive**: Minimal
- **Time**: ~1-2 minutes
- **Best for**: Quick validation, CI/CD preparation

## 🔧 Dependencies

All scripts require:
- **Snowflake CLI**: `pip install snowflake-cli-labs`
- **Configured ml_pipeline connection**: Run `snow connection add ml_pipeline`
- **Bash 4+**: For script compatibility

Optional but recommended:
- **yq**: For YAML validation (`brew install yq` or download from GitHub)
- **jq**: For JSON parsing (usually pre-installed)
- **GitHub CLI**: For automated secrets setup (`brew install gh`)
- **Python 3**: For YAML validation and notebook testing

## 📚 Integration with GitHub Actions

These scripts mirror the checks performed by the GitHub Actions workflows:

| Local Script | GitHub Workflow | Purpose |
|--------------|-----------------|---------|
| `test-infrastructure-setup.sh` | `setup-infrastructure.yml` | Infrastructure validation |
| `test-notebook-deployment.sh` | `deploy-notebooks.yml` | Notebook deployment |
| `test-workflow-locally.sh` | All workflows | General validation |

Running these scripts locally helps catch issues before they occur in GitHub Actions, saving time and debugging effort.

## 🎯 Best Practices

1. **Run tests before commits**: Especially `test-infrastructure-setup.sh`
2. **Use dry-run mode**: For quick validation without interactive prompts
3. **Test infrastructure changes**: Always run full infrastructure tests after modifying `cli-setup.sh`
4. **Validate before production**: Run all tests before deploying to production environments
5. **Keep scripts updated**: Update test scripts when workflow files change

## 🆘 Troubleshooting

### Common Issues:

**"Snowflake CLI not found"**
```bash
pip install snowflake-cli-labs
```

**"ml_pipeline connection not found"**
```bash
snow connection add ml_pipeline --account your_account --user your_user ...
```

**"Permission denied"**
```bash
chmod +x scripts/*.sh
```

**"YAML validation failed"**
```bash
pip install PyYAML  # For Python YAML validation
brew install yq     # For advanced YAML processing
```

For more help, run any script with `--help` flag or check the GitHub Actions workflow logs for detailed error messages.

## 🎉 Result

These scripts ensure your GitHub Actions workflow will work correctly before you deploy it, saving time and reducing deployment failures! 