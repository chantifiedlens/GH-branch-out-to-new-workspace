# Note that this is a customized version of the original script found at: https://github.com/microsoft/fabric-toolbox/tree/main/accelerators/CICD/Branch-out-to-new-workspace
# It has been changed by GitHub Copilot to support GitHub instead of Azure DevOps repos.
import argparse
import json
import logging
import time

import msal
import requests

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Starting GitHub branch-out script...')

# Constants (defaults can be overridden via CLI args)
FABRIC_API_URL = "https://api.fabric.microsoft.com/v1"
GH_API_URL = "https://api.github.com"
CAPACITY_ID = ""
WORKSPACE_NAME = ""
DEVELOPER = ""
GH_MAIN_BRANCH = ""
GH_NEW_BRANCH = ""
GH_GIT_FOLDER = ""
GH_OWNER = ""
GH_REPO_NAME = ""
CLIENT_ID = ""
CLIENT_SECRET = ""
TENANT_ID = ""
USERNAME = ""
PASSWORD = ""
FABRIC_TOKEN = ""
GH_PAT_TOKEN = ""


# ------------------------- Auth helpers -------------------------

def acquire_token_user_id_password(tenant_id, client_id, user_name, password):
    """Acquire Fabric token using username/password (no MFA)."""
    authority = f'https://login.microsoftonline.com/{tenant_id}'
    app = msal.PublicClientApplication(client_id, authority=authority)
    scopes = ['https://api.fabric.microsoft.com/.default']
    result = app.acquire_token_by_username_password(user_name, password, scopes)
    if 'access_token' in result:
        return result['access_token']
    logging.error('Error: Fabric token could not be obtained: %s', result)
    return None


# ------------------------- Fabric helpers -------------------------

def create_fabric_workspace(workspace_name, cpty_id, token):
    try:
        logging.info("Creating Fabric Workspace %s...", workspace_name)
        headers = {"Authorization": f"Bearer {token}"}
        data = {"displayName": workspace_name, "capacityId": cpty_id}
        response = requests.post(f"{FABRIC_API_URL}/workspaces", headers=headers, json=data)
        logging.info("Fabric workspace create response: %s - %s", response.status_code, response.text)

        if response.status_code == 409:
            logging.error("Workspace '%s' already exists.", workspace_name)
            raise ValueError("Fabric workspace already exists. Please specify a new workspace as target.")
        if response.status_code == 201:
            workspace_id = response.json().get('id')
            logging.info("Fabric Workspace %s created with ID: %s", workspace_name, workspace_id)
            return workspace_id

        logging.error("Could not create workspace. Error: %s", response.text)
        return None
    except requests.exceptions.RequestException as e:
        logging.error("Error creating workspace: %s", e)
        return None


def add_workspace_admins(workspace_id, developer, token):
    try:
        logging.info("Adding developer %s to workspace %s as Admin", developer, workspace_id)
        headers = {"Authorization": f"Bearer {token}"}
        data = {"emailAddress": developer, "groupUserAccessRight": "Admin"}
        response = requests.post(
            f"https://api.powerbi.com/v1.0/myorg/admin/groups/{workspace_id}/users",
            headers=headers,
            json=data,
        )
        response.raise_for_status()
        logging.info("Admin added")
    except requests.exceptions.RequestException as e:
        logging.error("Error adding workspace admin: %s", e)


# ------------------------- GitHub helpers -------------------------

def _github_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
    }


def get_github_branch_sha(owner, repo_name, branch_name, token):
    try:
        logging.info("Retrieving SHA for branch '%s'", branch_name)
        response = requests.get(
            f"{GH_API_URL}/repos/{owner}/{repo_name}/git/ref/heads/{branch_name}",
            headers=_github_headers(token),
        )
        response.raise_for_status()
        sha = response.json()["object"]["sha"]
        logging.info("Found base SHA %s for branch %s", sha, branch_name)
        return sha
    except requests.exceptions.RequestException as e:
        logging.error("Error getting GitHub branch SHA: %s", e)
        return None


def branch_exists(owner, repo_name, branch_name, token):
    """Check if a branch exists in the GitHub repository."""
    try:
        response = requests.get(
            f"{GH_API_URL}/repos/{owner}/{repo_name}/git/ref/heads/{branch_name}",
            headers=_github_headers(token),
        )
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False


def create_github_branch(owner, repo_name, main_branch, new_branch, token):
    if not token:
        raise ValueError("GitHub PAT token is required to create branches.")

    # Check if the branch already exists
    if branch_exists(owner, repo_name, new_branch, token):
        logging.info("GitHub branch '%s' already exists, skipping creation", new_branch)
        return

    base_sha = get_github_branch_sha(owner, repo_name, main_branch, token)
    if not base_sha:
        raise ValueError(f"Could not find base branch '{main_branch}' in repo '{owner}/{repo_name}'.")

    try:
        logging.info("Creating GitHub branch '%s' from '%s'...", new_branch, main_branch)
        payload = {"ref": f"refs/heads/{new_branch}", "sha": base_sha}
        response = requests.post(
            f"{GH_API_URL}/repos/{owner}/{repo_name}/git/refs",
            headers=_github_headers(token),
            json=payload,
        )
        response.raise_for_status()
        logging.info("GitHub branch '%s' created", new_branch)
    except requests.exceptions.RequestException as e:
        logging.error("Error creating GitHub branch: %s", e)
        raise


# ------------------------- Fabric connection helpers -------------------------

def _fabric_headers(token):
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }


def list_connections(token):
    """List all Fabric connections and return JSON list (or empty list)."""
    try:
        resp = requests.get(f"{FABRIC_API_URL}/connections", headers=_fabric_headers(token))
        resp.raise_for_status()
        data = resp.json()
        # Some APIs return {"value": [...]}
        if isinstance(data, dict) and "value" in data:
            return data["value"]
        # Or a direct list
        if isinstance(data, list):
            return data
        return []
    except requests.exceptions.RequestException as e:
        logging.error("Error listing Fabric connections: %s", e)
        return []


def get_or_create_github_pat_connection(connection_name, pat_token, token):
    """
    Get a Fabric GitHub PAT connection by display name, or create it if missing.

    Returns the connection id (string) or None on failure.
    """
    if not pat_token:
        logging.error("GitHub PAT token is required to create or use a GitHub connection.")
        return None

    # Try to find existing connection by displayName
    connections = list_connections(token)
    for c in connections:
        if c.get("displayName") == connection_name:
            cid = c.get("id")
            if cid:
                logging.info("Found existing GitHub connection '%s' with ID: %s", connection_name, cid)
                return cid

    # Create new connection
    body = {
        "connectivityType": "ShareableCloud",
        "displayName": connection_name,
        "connectionDetails": {
            "type": "GitHubSourceControl",
            "creationMethod": "GitHubSourceControl.Contents",
        },
        "credentialDetails": {
            "credentials": {
                "credentialType": "Key",
                "key": pat_token,
            }
        }
    }
    try:
        logging.info("Creating GitHub PAT connection '%s'...", connection_name)
        resp = requests.post(f"{FABRIC_API_URL}/connections", headers=_fabric_headers(token), json=body)
        if resp.status_code == 201:
            cid = resp.json().get("id")
            logging.info("GitHub connection created with ID: %s", cid)
            return cid
        else:
            logging.error("Failed to create GitHub connection. Status: %s - %s", resp.status_code, resp.text)
            return None
    except requests.exceptions.RequestException as e:
        logging.error("Error creating GitHub connection: %s", e)
        return None




def connect_branch_to_workspace(workspace_id, org_name, repo_name, branch_name, git_folder, token):
    try:
        logging.info(
            "Connecting workspace %s to GitHub branch %s at folder %s", workspace_id, branch_name, git_folder
        )
        headers = _fabric_headers(token)
        # For root, docs indicate blank directoryName; otherwise use relative path without trailing slash
        directory_name = git_folder.rstrip("/") if git_folder and git_folder not in ("/", "\\") else ""

        # Obtain or create a GitHub credentials connection (PAT-based)
        connection_display_name = f"GitHub PAT - {org_name}/{repo_name}"
        connection_id = get_or_create_github_pat_connection(connection_display_name, GH_PAT_TOKEN, token)
        if not connection_id:
            logging.error("Failed to acquire GitHub credentials connection. Aborting connect.")
            raise ValueError("Could not obtain/create GitHub credentials connection.")

        data = {
            "gitProviderDetails": {
                "ownerName": org_name,
                "gitProviderType": "GitHub",
                "repositoryName": repo_name,
                "branchName": branch_name,
                "directoryName": directory_name,
            },
            "myGitCredentials": {
                "source": "ConfiguredConnection",
                "connectionId": connection_id,
            },
        }
        response = requests.post(
            f"{FABRIC_API_URL}/workspaces/{workspace_id}/git/connect",
            headers=headers,
            json=data,
        )
        if response.status_code != 200:
            logging.error("Git connect failed: %s - %s", response.status_code, response.text)
            response.raise_for_status()
        logging.info("Workspace connected to GitHub branch")
    except requests.exceptions.RequestException as e:
        logging.error("Error connecting branch to workspace: %s", e)
        raise


# ------------------------- Git initialization helpers -------------------------

def long_running_operation_polling(uri, retry_after, headers):
    keep_polling = True
    try:
        logging.info(
            "Polling long running operation ID %s started with retry-after %s seconds.",
            uri,
            retry_after,
        )
        while keep_polling:
            response = requests.get(uri, headers=headers)
            operation_state = response.json()
            logging.info('operation state = %s', operation_state)
            logging.info("Long running operation status: %s", operation_state['status'])
            if operation_state['status'] in ["NotStarted", "Running"]:
                time.sleep(retry_after)
            else:
                keep_polling = False
        if operation_state['status'] == "Failed":
            logging.info(
                "The long running operation failed. Error response: %s",
                json.dumps(operation_state.get('Error', {})),
            )
        else:
            logging.info("The long running operation has been successfully completed.")
            return operation_state['status']
    except Exception as e:  # pylint: disable=broad-except
        logging.error("The long running operation failed with error: %s", e)


def initialize_workspace_from_git(workspace_id, token):
    try:
        logging.info("Initializing workspace %s to Git branch %s ...", workspace_id, GH_NEW_BRANCH)
        headers = {"Authorization": f"Bearer {token}"}

        git_initialize_url = f"{FABRIC_API_URL}/workspaces/{workspace_id}/git/initializeConnection"
        response = requests.post(git_initialize_url, headers=headers)

        if response.status_code == 200:
            git_status = response.json()
            remote_commit_hash = git_status.get('remoteCommitHash')
            workspace_head = git_status.get('workspaceHead')

            update_params = {
                'workspaceHead': workspace_head,
                'remoteCommitHash': remote_commit_hash,
                'options': {
                    'allowOverrideItems': True,
                    'conflictResolution': 'RemoteSync',
                },
            }

            update_url = f"{FABRIC_API_URL}/workspaces/{workspace_id}/git/updateFromGit"
            update_response = requests.post(update_url, headers=headers, json=update_params)

            if update_response.status_code == 200:
                logging.info(
                    "Feature workspace %s is synchronizing with branch %s",
                    WORKSPACE_NAME,
                    GH_NEW_BRANCH,
                )
            elif update_response.status_code == 202:
                logging.info('Request accepted, update workspace is in progress...')
                location_url = update_response.headers.get("Location")
                logging.info("Polling URL to track operation status is %s", location_url)
                time.sleep(15)
                long_running_operation_polling(location_url, 15, headers)
            else:
                logging.error(
                    'Failed to update the workspace. Status Code: %s - %s',
                    update_response.status_code,
                    update_response.text,
                )

        elif response.status_code == 202:
            logging.info('Request accepted, get initialize in progress. Retry after some time')

        else:
            logging.info('Failed to Git initialize. Status Code: %s', response.status_code)

    except requests.exceptions.RequestException as e:
        logging.error("An error occurred during workspace initialization: %s", e)


# ------------------------- CLI argument binding -------------------------

def set_main_parameters():
    global TENANT_ID
    global USERNAME
    global PASSWORD
    global WORKSPACE_NAME
    global DEVELOPER
    global GH_MAIN_BRANCH
    global GH_NEW_BRANCH
    global GH_GIT_FOLDER
    global GH_OWNER
    global GH_REPO_NAME
    global GH_API_URL
    global CLIENT_ID
    global CLIENT_SECRET
    global CAPACITY_ID
    global FABRIC_TOKEN
    global GH_PAT_TOKEN

    try:
        parser = argparse.ArgumentParser(description="Branch-out automation for GitHub + Fabric")
        parser.add_argument('--TENANT_ID', type=str, required=False, help='Tenant ID passed from pipeline')
        parser.add_argument('--CLIENT_ID', type=str, required=False, help='Client ID passed from pipeline')
        parser.add_argument('--USER_NAME', type=str, required=False, help='User Name passed from pipeline')
        parser.add_argument('--PASSWORD', type=str, required=False, help='User password (MFA disabled)')
        parser.add_argument('--WORKSPACE_NAME', type=str, required=True, help='Name of the feature workspace to be created')
        parser.add_argument('--DEVELOPER', type=str, required=True, help='Developer UPN to be added to workspace as admin')
        parser.add_argument('--GH_MAIN_BRANCH', type=str, required=True, help='Main development branch')
        parser.add_argument('--GH_GIT_FOLDER', type=str, required=True, help='Folder where Fabric content is stored')
        parser.add_argument('--GH_NEW_BRANCH', type=str, required=False, help='New branch to be created')
        parser.add_argument('--GH_OWNER', type=str, required=True, help='GitHub organization/user name')
        parser.add_argument('--GH_REPO_NAME', type=str, required=True, help='GitHub repository name')
        parser.add_argument('--GH_API_URL', type=str, default='https://api.github.com', help='GitHub API base URL')
        parser.add_argument('--CAPACITY_ID', type=str, required=True, help='Capacity ID to assign the workspace')
        parser.add_argument('--FABRIC_TOKEN', type=str, default='', help='Fabric user token (optional)')
        parser.add_argument('--GH_PAT_TOKEN', type=str, required=True, help='GitHub PAT token with repo access')

        args = parser.parse_args()
    except Exception as e:  # pylint: disable=broad-except
        logging.error('Error parsing parameters: %s', e)
        raise ValueError(f"Could not extract parameters: {e}") from e

    logging.info('Binding parameters...')
    TENANT_ID = args.TENANT_ID
    USERNAME = args.USER_NAME
    PASSWORD = args.PASSWORD
    WORKSPACE_NAME = args.WORKSPACE_NAME
    DEVELOPER = args.DEVELOPER
    GH_MAIN_BRANCH = args.GH_MAIN_BRANCH
    GH_NEW_BRANCH = args.GH_NEW_BRANCH
    GH_GIT_FOLDER = args.GH_GIT_FOLDER
    GH_OWNER = args.GH_OWNER
    GH_REPO_NAME = args.GH_REPO_NAME
    GH_API_URL = args.GH_API_URL or GH_API_URL
    CLIENT_ID = args.CLIENT_ID
    CAPACITY_ID = args.CAPACITY_ID
    FABRIC_TOKEN = args.FABRIC_TOKEN
    GH_PAT_TOKEN = args.GH_PAT_TOKEN
    # CLIENT_SECRET reserved for future SPN support


# ------------------------- Main -------------------------

def main():
    logging.info('Starting branch-out main flow...')

    set_main_parameters()

    if not GH_PAT_TOKEN:
        raise ValueError("GitHub PAT token was not provided. Set --GH_PAT_TOKEN.")

    token = ""
    if FABRIC_TOKEN:
        logging.info('Fabric token found, using provided token...')
        token = FABRIC_TOKEN
        token_preview = token[:20] + "..." if len(token) > 20 else token
        logging.info('Token preview (first 20 chars): %s', token_preview)
        logging.info('Token length: %s', len(token))
    else:
        logging.info('Generating Fabric token using service account credentials...')
        token = acquire_token_user_id_password(TENANT_ID, CLIENT_ID, USERNAME, PASSWORD)

    if not token:
        logging.error(
            "Terminating branch out process due to Fabric credential error. Provide a valid token or use a service account without MFA."
        )
        raise ValueError("Could not generate authentication token. Please review the debug logs.")

    logging.info('Invoking new workspace routine...')
    workspace_id = create_fabric_workspace(WORKSPACE_NAME, CAPACITY_ID, token)
    if not workspace_id:
        logging.error(
            "Terminating branch out process as target workspace could not be created. Check permissions or provide a valid Fabric token."
        )
        raise ValueError("Could not create Fabric workspace.")

    logging.info('Adding workspace admin %s...', DEVELOPER)
    add_workspace_admins(workspace_id, DEVELOPER, token)

    logging.info('Creating GitHub branch %s from %s...', GH_NEW_BRANCH, GH_MAIN_BRANCH)
    create_github_branch(GH_OWNER, GH_REPO_NAME, GH_MAIN_BRANCH, GH_NEW_BRANCH, GH_PAT_TOKEN)

    logging.info('Connecting workspace to GitHub branch %s...', GH_NEW_BRANCH)
    connect_branch_to_workspace(
        workspace_id,
        GH_OWNER,
        GH_REPO_NAME,
        GH_NEW_BRANCH,
        GH_GIT_FOLDER,
        token,
    )

    logging.info('Initialize workspace from GitHub branch...')
    initialize_workspace_from_git(workspace_id, token)


if __name__ == "__main__":
    main()
