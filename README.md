# Snyk Organization Migration Tool

This project provides scripts to migrate organizations and their targets (repositories) from one Snyk group to another. The migration process is split into two main phases: organization extraction and target extraction.

## Overview

The migration tool consists of two Python scripts:
1. **`org_extraction.py`** - Extracts organization data from a source Snyk group
2. **`snyk_extract_targets.py`** - Extracts targets (repositories) from source organizations for import into target organizations

## Prerequisites

- Python 3.7+ (tested with Python 3.13.5)
- Snyk API tokens for both source and target tenants
- Access to both source and target Snyk groups

## Installation & Setup

### 1. Clone or Download the Project

```bash
cd /path/to/snyk-org-project-migration
```

### 2. Set Up Python Environment

Create and activate a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# or
venv\Scripts\activate  # On Windows
```

### 3. Install Dependencies

Install the required Python packages:

```bash
pip install requests
```

Alternatively, you can create a `requirements.txt` file:

```bash
echo "requests>=2.25.0" > requirements.txt
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Set the following environment variables before running the scripts:

```bash
export SOURCE_SNYK_API_TOKEN="your-source-snyk-api-token"
```

### Script Configuration

Update the configuration constants in `org_extraction.py`:

```python
TARGET_GROUP_ID = "your-target-group-id"
SOURCE_GROUP_ID = "your-source-group-id"  
TEMPLATE_ORG_ID = "your-template-org-id"  # Organization in target group to copy settings from
```

## How To Run Script

The complete migration process involves 4 steps. Steps 1 & 3 use the Python scripts in this repository, while Steps 2 & 4 use Snyk's API Import Tool to actually create the organizations and import the projects.

### Step 1: Extract Organizations from Source Tenant

Extract organization data from the source group and prepare for migration.

**Prerequisites:**
- Update configuration constants in `org_extraction.py`:
  - Replace `SOURCE_GROUP_ID` with your source group ID
  - Replace `TARGET_GROUP_ID` with your target group ID  
  - Replace `TEMPLATE_ORG_ID` with your template organization ID

**Terminal Commands:**
```bash
export SOURCE_SNYK_API_TOKEN="your-source-tenant-api-token"
python3 org_extraction.py
```

**Output:** Creates `snyk-orgs-to-create.json` file

**Important:** Keep the source default organization from the file. Make sure the target group's default organization name matches the source group's default organization name so targets map properly (names should match by default).

### Step 2: Create Shell Organizations in Target Tenant

Use Snyk's API Import Tool to create the shell organizations in the target tenant.

**Terminal Commands:**
```bash
# Install the API Import Tool
npm install -g snyk-api-import

# Set environment variables for target tenant
export SNYK_TOKEN="your-target-tenant-api-token"
export SNYK_LOG_PATH="/Users/brookecastleberry/snyk-logs"

# Create log directory
mkdir -p /Users/brookecastleberry/snyk-logs

# Create organizations
DEBUG=snyk* snyk-api-import orgs:create --file="snyk-orgs-to-create.json"
```

**Output:** Generates `snyk-created-orgs.json` file (move this file to the repository directory)

### Step 3: Extract Targets from Source Organizations

Extract targets (repositories) from the source organizations for import.

**Terminal Commands:**
```bash
python3 snyk_extract_targets.py
```

**Prerequisites:**
- `snyk-orgs-to-create.json` (from Step 1)
- `snyk-created-orgs.json` (from Step 2)

**Output:** Creates `snyk-import-targets.json` ready for import

### Step 4: Import Targets to Target Organizations

Use the API Import Tool to import all targets and create projects in the target tenant.

**Terminal Commands:**
```bash
snyk-api-import import --file=snyk-import-targets.json
```

**Post-Import:** Check logs in `/Users/brookecastleberry/snyk-logs` for any project import failures that may need manual attention.

## File Structure

```
snyk-org-project-migration/
├── README.md                    # This file
├── mcp.json                     # MCP server configuration
├── org_extraction.py            # Phase 1: Organization extraction
├── snyk_extract_targets.py      # Phase 2: Target extraction
├── requirements.txt             # Python dependencies (optional)
├── venv/                        # Virtual environment (created)
└── Output files:
    ├── snyk-orgs-to-create.json    # Phase 1 output
    ├── snyk-created-orgs.json      # Manual input for Phase 2
    ├── snyk-source-orgs.json       # Source org references
    └── snyk-import-targets.json    # Phase 2 output
```

## Dependencies

### Required Python Packages

- **requests** (>=2.25.0) - HTTP library for Snyk API calls

### Built-in Python Modules

- **json** - JSON parsing and manipulation
- **os** - Environment variable access
- **sys** - System operations
- **typing** - Type hints support

## API Permissions

Ensure your Snyk API tokens have the following permissions:

### Source Token
- Read access to source group organizations
- Read access to organization targets
- Read access to target attributes and metadata

### Target Token (for organization creation)
- Write access to target group
- Organization creation permissions

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify API tokens are correctly set
   - Check token permissions and expiration

2. **Rate Limiting**
   - The scripts include pagination and error handling
   - Add delays between requests if needed

3. **Missing Organizations**
   - Ensure `snyk-created-orgs.json` is properly formatted
   - Verify organization IDs match between source and target

### Debug Mode

Enable verbose logging by modifying the scripts to include debug prints:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## Contributing

1. Follow Python PEP 8 style guidelines
2. Add type hints for new functions
3. Include docstrings for all functions
4. Test with multiple organization sizes
