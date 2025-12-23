# GitHub Branch-Out to New Workspace Automation

This repository contains Python scripts that automate the creation of feature workspaces in Microsoft Fabric and synchronize them with GitHub branches. Based on the [custom Branch Out to New Workspace scripts](https://github.com/microsoft/fabric-toolbox/tree/main/accelerators/CICD/Branch-out-to-new-workspace) for Microsoft Fabric provided by Microsoft for Azure DevOps. Which you can find in the [Fabric Toolbox GitHub repository](https://github.com/microsoft/fabric-toolbox/tree/main).

It is designed to streamline the development workflow by enabling developers to quickly create isolated feature workspaces with content sourced from GitHub.

## Overview

The automation consists of two main scripts:

1. **BranchOut-Feature-Workspace-Automation-GitHub.py** - Creates a new Fabric workspace, branches GitHub code, and connects the workspace to the GitHub branch
2. **Run_post_activity.py** - Executes post-creation activities such as copying data, creating shortcuts, and managing connections

## Required Parameters

### BranchOut-Feature-Workspace-Automation-GitHub.py

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--WORKSPACE_NAME` | string | Yes | Name of the feature workspace to be created |
| `--DEVELOPER` | string | Yes | Developer UPN (email) to be added to workspace as admin |
| `--GH_MAIN_BRANCH` | string | Yes | Main development branch to branch from |
| `--GH_GIT_FOLDER` | string | Yes | Folder in the repo where Fabric content is stored (use `/` for root) |
| `--GH_NEW_BRANCH` | string | No | New branch to be created (auto-generated if not provided) |
| `--GH_OWNER` | string | Yes | GitHub organization/user name |
| `--GH_REPO_NAME` | string | Yes | GitHub repository name |
| `--CAPACITY_ID` | string | Yes | Capacity ID to assign the workspace |
| `--GH_API_URL` | string | No | GitHub API base URL (default: `https://api.github.com`) |
| `--TENANT_ID` | string | No | Azure Tenant ID (required if not using FABRIC_TOKEN) |
| `--CLIENT_ID` | string | No | Azure Client ID (required if not using FABRIC_TOKEN) |
| `--USER_NAME` | string | No | Service account username (required if not using FABRIC_TOKEN) |
| `--PASSWORD` | string | No | Service account password (required if not using FABRIC_TOKEN) |
| `--FABRIC_TOKEN` | string | No | Pre-generated Fabric user token (optional, if provided skips token generation). Alternatively adopt the logic in the original [custom Branch Out to New Workspace scripts](https://github.com/microsoft/fabric-toolbox/tree/main/accelerators/CICD/Branch-out-to-new-workspace) repository to get the value from Azure keyVault instead |

### Run_post_activity.py

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `--SOURCE_WORKSPACE` | string | Yes | Source workspace ID or name |
| `--TARGET_WORKSPACE` | string | Yes | Target workspace ID or name |
| `--NOTEBOOK_WORKSPACE_ID` | string | Yes | Workspace GUID where the post activity notebook is saved |
| `--NOTEBOOK_ID` | string | Yes | GUID of the post activity notebook |
| `--FABRIC_TOKEN` | string | No | Fabric user token (required if not using credentials) |
| `--TENANT_ID` | string | No | Azure Tenant ID (required if not using FABRIC_TOKEN) |
| `--CLIENT_ID` | string | No | Azure Client ID (required if not using FABRIC_TOKEN) |
| `--USER_NAME` | string | No | Service account username (required if not using FABRIC_TOKEN) |
| `--PASSWORD` | string | No | Service account password (required if not using FABRIC_TOKEN) |
| `--COPY_LAKEHOUSE` | boolean | No | Copy lakehouse data from source to target (default: False) |
| `--COPY_WAREHOUSE` | boolean | No | Copy warehouse data from source to target (default: False) |
| `--CREATE_SHORTCUTS` | boolean | No | Create shortcuts back to source lakehouse in target (default: False) |
| `--CONNECTIONS_FROM_TO` | string | No | Swap connections in pipelines using names or IDs in format `(from,to)` (default: `()`) |
| `--WH_VIEWS_ON_LH` | boolean | No | Indicates if there are warehouse views on lakehouse (default: False) |

## Required Secrets

### GitHub Secrets

Set these in your GitHub repository settings under **Settings > Secrets and variables > Actions**:

| Secret Name | Description |
|-------------|-------------|
| `GH_PAT_TOKEN` | GitHub Personal Access Token with `repo` access (required for creating branches and connecting workspaces) |

### GitHub Variables

Set these in your GitHub repository settings under **Settings > Secrets and variables > Variables**:

| Variable Name | Description | Example |
|---------------|-------------|---------|
| `GH_OWNER` | GitHub organization or user name | `my-org` or `username` |
| `GH_REPO_NAME` | GitHub repository name | `my-repo` |
| `GH_API_URL` | GitHub API base URL | `https://api.github.com` |
| `TENANT_ID` | Azure Entra ID tenant ID | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `NOTEBOOK_WORKSPACE_ID` | Workspace GUID containing the post activity notebook | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `NOTEBOOK_ID` | GUID of the post activity notebook | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |

## Authentication Methods

The scripts supports the below authentication method for now:

### Method 1: Fabric Token (Recommended)
Provide a pre-generated Fabric token using `--FABRIC_TOKEN`. This bypasses credential-based authentication.

```bash
python BranchOut-Feature-Workspace-Automation-GitHub.py --FABRIC_TOKEN "token_here" ...
```

## Workflow: GitHub Actions

The automation is triggered via GitHub Actions workflow dispatch. The workflow:

1. Checks out the repository
2. Installs required Python packages (`requests`, `msal`)
3. Runs `BranchOut-Feature-Workspace-Automation-GitHub.py` to create workspace and branch
4. Runs `Run_post_activity.py` to execute post-creation tasks

### Workflow Inputs

When manually triggering the workflow, provide:

| Input | Description | Example |
|-------|-------------|---------|
| `source_workspace` | Source workspace for data copy | `Sales_Analytics` |
| `target_workspace` | Target workspace name to create | `Sales_Analytics_Feature_Dev` |
| `copy_lakehouse_data` | Copy lakehouse data (True/False) | `False` |
| `copy_warehouse_data` | Copy warehouse data (True/False) | `False` |
| `developer_email` | Developer email to add as admin | `john.doe@company.com` |
| `capacity_id` | Capacity ID for new workspace | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` |
| `gh_branch` | Source branch name | `main` |
| `gh_git_folder` | Folder containing Fabric content | `/` |
| `gh_new_branch` | New branch name to create | `feature/sales-dev` |
| `connections_from_to` | Connection mapping format `(from,to)` | `()` |
| `create_lakehouse_shortcuts` | Create shortcuts (True/False) | `True` |
| `fabrictoken` | Fabric authentication token | `token_here` |

## Usage Examples

### Command Line - BranchOut Script

```bash
python scripts/BranchOut-Feature-Workspace-Automation-GitHub.py \
  --WORKSPACE_NAME "Sales_Analytics_Dev" \
  --DEVELOPER "john.doe@company.com" \
  --GH_MAIN_BRANCH "main" \
  --GH_GIT_FOLDER "/" \
  --GH_NEW_BRANCH "feature/sales-dev" \
  --GH_OWNER "my-org" \
  --GH_REPO_NAME "my-repo" \
  --CAPACITY_ID "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --FABRIC_TOKEN "your_token_here" \
  --GH_PAT_TOKEN "your_github_pat_token"
```

### Command Line - Post Activity Script

```bash
python scripts/Run_post_activity.py \
  --SOURCE_WORKSPACE "Sales_Analytics" \
  --TARGET_WORKSPACE "Sales_Analytics_Dev" \
  --NOTEBOOK_WORKSPACE_ID "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --NOTEBOOK_ID "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" \
  --FABRIC_TOKEN "your_token_here" \
  --COPY_LAKEHOUSE "False" \
  --COPY_WAREHOUSE "False" \
  --CREATE_SHORTCUTS "True"
```

## Features

- **Workspace Creation** - Automatically creates a new Microsoft Fabric workspace
- **GitHub Branching** - Creates a new branch from a main branch
- **Git Integration** - Connects Fabric workspace to GitHub repository
- **Admin Assignment** - Adds specified developer as workspace admin
- **Post-Activity Execution** - Runs Fabric notebooks for additional setup tasks
- **Data Operations** - Supports lakehouse/warehouse data copying
- **Connection Management** - Handles data source connection updates
- **Shortcut Creation** - Creates lakehouse shortcuts for data sharing

## Logging

Both scripts use Python logging to output detailed execution information. Logs include:
- Authentication steps
- API requests and responses
- Error handling and retry logic
- Long-running operation polling

Configure logging level by modifying the logging setup in each script.

## Error Handling

The scripts include comprehensive error handling for:
- Authentication failures
- API response errors
- Network timeouts
- Long-running operation failures

Review the detailed error messages in logs for troubleshooting.

## Notes

- **GitHub PAT Permissions**: GitHub PAT token must have `repo` scope to create branches and access repository content
- **Capacity Requirements**: Ensure the specified capacity exists and has sufficient quota
- **Workspace Naming**: Workspace names must be unique within the tenant
- **Token Expiration**: Fabric tokens have expiration times; ensure they are fresh when used

## Related Documentation

- [Microsoft Fabric API Documentation](https://learn.microsoft.com/en-us/fabric/api/overview)
- [GitHub API Documentation](https://docs.github.com/en/rest)
- [MSAL Python Documentation](https://github.com/AzureAD/microsoft-authentication-library-for-python)

## License

Refer to the repository license for terms of use.


