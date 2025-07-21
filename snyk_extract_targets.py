"""
Snyk Target Extraction Script

This script extracts targets (repositories) from source organizations in a Snyk tenant
and prepares them for import into target organizations. It handles both single and
multi-branch repositories by creating separate import entries for each branch.

The script reads from:
- snyk-orgs-to-create.json: Source organization data (from org_extraction.py)  
- snyk-created-orgs.json: Target organization mapping data

Output:
- snyk_import_targets.json: Import-ready JSON file for Snyk API import tool

Required environment variables:
- SOURCE_SNYK_API_TOKEN: API token for the source Snyk tenant

Usage:
    export SOURCE_SNYK_API_TOKEN="your-source-token"
    python snyk_extract_targets.py
"""

import requests
import json
import os

# Configuration - Update these for your environment
SOURCE_API_TOKEN = os.getenv("SOURCE_SNYK_API_TOKEN")
SOURCE_GROUP_ID = "3de0eeb1-20e3-4afd-8a6a-97d57326588d"  # Update as needed


def get_targets_for_org(org_id, api_token):
    """
    Get all targets for an organization with pagination support.
    
    Args:
        org_id (str): The organization ID
        api_token (str): Snyk API token
        
    Returns:
        list: List of all targets for the organization
    """
    headers = {
        "Authorization": f"token {api_token}",
        "Content-Type": "application/json"
    }
    
    all_targets = []
    url = f"https://api.snyk.io/rest/orgs/{org_id}/targets?version=2024-06-18&limit=100"
    
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        targets = data.get("data", [])
        all_targets.extend(targets)
        
        # Check for next page
        links = data.get("links", {})
        next_url = links.get("next")
        
        if next_url:
            url = f"https://api.snyk.io{next_url}" if next_url.startswith("/") else next_url
        else:
            url = None
    
    return all_targets


def get_projects_for_target(org_id, target_id, api_token):
    """
    Get all projects for a specific target with pagination support.
    
    Args:
        org_id (str): The organization ID
        target_id (str): The target ID
        api_token (str): Snyk API token
        
    Returns:
        list: List of all projects for the target
    """
    headers = {
        "Authorization": f"token {api_token}",
        "Content-Type": "application/json"
    }
    
    all_projects = []
    url = f"https://api.snyk.io/rest/orgs/{org_id}/projects?target_id={target_id}&version=2024-06-18&limit=100"
    
    while url:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        data = response.json()
        projects = data.get("data", [])
        all_projects.extend(projects)
        
        # Check for next page
        links = data.get("links", {})
        next_url = links.get("next")
        
        if next_url:
            url = f"https://api.snyk.io{next_url}" if next_url.startswith("/") else next_url
        else:
            url = None
    
    return all_projects


def get_target_org_mapping():
    """
    Load the mapping of source org names to target org data.
    
    Returns:
        dict: Mapping of source org names to target org info
    """
    try:
        with open("snyk-created-orgs.json", "r") as f:
            created_orgs = json.load(f)
        
        orgs_data = created_orgs.get("orgData", [])
        org_mapping = {}
        
        for org in orgs_data:
            if isinstance(org, dict) and "origName" in org and "id" in org:
                org_mapping[org["origName"]] = {
                    "orgId": org["id"],
                    "integrations": org.get("integrations", {})
                }
                
        return org_mapping
        
    except FileNotFoundError:
        print("ERROR: snyk-created-orgs.json not found.")
        print("Please run the organization creation script first to generate this file.")
        return {}


def get_source_orgs_from_json():
    """
    Load source organization data from the source organizations JSON file.
    
    Returns:
        list: List of source organization data
    """
    try:
        with open("snyk-source-orgs.json", "r") as f:
            data = json.load(f)
        return data.get("sourceOrgs", [])
        
    except FileNotFoundError:
        print("ERROR: snyk-source-orgs.json not found.")
        print("Please run org_extraction.py first to generate this file.")
        return []


def extract_target_attributes_from_projects(projects):
    """
    Extract target-level attributes from projects (branch information).
    
    Args:
        projects (list): List of project data from Snyk API
        
    Returns:
        dict: Dictionary containing branch information for the target
    """
    if not projects:
        return {}
    
    print(f"        Analyzing {len(projects)} projects for this target")
    
    branches = set()
    
    for project in projects:
        project_attrs = project.get("attributes", {})
        project_name = project_attrs.get("name", "")
        
        # Extract branch from multiple possible sources
        branch = None
        
        # Priority order: target_reference, branch field, project name patterns
        if project_attrs.get("target_reference"):
            branch = project_attrs["target_reference"]
        elif project_attrs.get("branch"):
            branch = project_attrs["branch"]
        elif ":" in project_name:
            # Pattern: "repo:branch"
            potential_branch = project_name.split(":")[-1].strip()
            if potential_branch and "/" not in potential_branch:  # Avoid URLs
                branch = potential_branch
        elif " (" in project_name and ")" in project_name:
            # Pattern: "repo (branch)"
            potential_branch = project_name.split(" (")[1].split(")")[0].strip()
            if potential_branch:
                branch = potential_branch
        
        if branch:
            branches.add(branch)
            print(f"          Project '{project_name}' -> branch: {branch}")
    
    # Determine target attributes based on branch information
    target_attributes = {}
    
    if branches:
        print(f"        Found branches: {', '.join(sorted(branches))}")
        
        if len(branches) == 1:
            # Single branch case
            target_attributes["branch"] = list(branches)[0]
        else:
            # Multiple branches case - create info for separate entries
            sorted_branches = sorted(branches)
            
            # Determine primary branch
            if "main" in branches:
                primary_branch = "main"
            elif "master" in branches:
                primary_branch = "master"
            else:
                primary_branch = sorted_branches[0]
            
            target_attributes["branches"] = sorted_branches
            target_attributes["primary_branch"] = primary_branch
            
            print(f"        Multiple branches detected - will create separate import entries for each")
            print(f"        Primary branch: {primary_branch}, Other branches: {', '.join([b for b in sorted_branches if b != primary_branch])}")
    
    return target_attributes


def create_target_entry(target_org_id, github_integration_id, target_info, branch=None):
    """
    Create a target entry for the import JSON.
    
    Args:
        target_org_id (str): Target organization ID
        github_integration_id (str): GitHub integration ID
        target_info (dict): Target information (name, owner)
        branch (str, optional): Branch name
        
    Returns:
        dict: Target entry for import
    """
    target_data = {
        "orgId": target_org_id,
        "integrationId": github_integration_id
    }
    
    if target_info:
        target_data["target"] = target_info.copy()
        if branch:
            target_data["target"]["branch"] = branch
    
    # Add empty exclusionGlobs for import structure
    target_data["exclusionGlobs"] = ""
    
    return target_data


def extract_targets():
    """
    Main function to extract targets from source orgs and prepare for import.
    """
    print("=== Snyk Target Extraction Script ===")
    
    if not SOURCE_API_TOKEN:
        print("ERROR: SOURCE_SNYK_API_TOKEN environment variable is not set.")
        print("Please set it with your source Snyk API token:")
        print("  export SOURCE_SNYK_API_TOKEN='your-token-here'")
        return
    
    # Load target organization mapping
    target_org_mapping = get_target_org_mapping()
    if not target_org_mapping:
        print("No target org mapping found.")
        return
    
    # Load source organization data
    print("Loading source organizations from saved data...")
    all_source_orgs = get_source_orgs_from_json()
    if not all_source_orgs:
        print("No source org data found. Make sure to run org_extraction.py first.")
        return
    
    # Filter to only orgs that have target mappings
    source_orgs_to_process = []
    for source_org in all_source_orgs:
        source_org_name = source_org["name"]
        if source_org_name in target_org_mapping:
            source_orgs_to_process.append({
                "id": source_org["id"],
                "attributes": {"name": source_org_name}
            })
    
    print(f"Processing {len(source_orgs_to_process)} orgs (filtered from {len(all_source_orgs)} total)")
    
    all_targets = []
    
    # Process each source organization
    for source_org in source_orgs_to_process:
        source_org_id = source_org["id"]
        source_org_name = source_org["attributes"]["name"]
        
        target_org_data = target_org_mapping.get(source_org_name)
        if not target_org_data:
            print(f"WARNING: No target org found for '{source_org_name}', skipping...")
            continue
        
        target_org_id = target_org_data["orgId"]
        target_integrations = target_org_data["integrations"]
        
        print(f"\nProcessing org: {source_org_name} -> {target_org_id}")
        
        try:
            targets = get_targets_for_org(source_org_id, SOURCE_API_TOKEN)
            print(f"  Found {len(targets)} targets")
            
            # Process each target
            for target in targets:
                target_attrs = target.get("attributes", {})
                target_id = target.get("id")
                
                # Get display name - this contains owner/repo information
                display_name = target_attrs.get("display_name", "")
                print(f"  Processing target: {display_name}")
                
                # Verify GitHub integration exists
                github_integration_id = target_integrations.get("github")
                if not github_integration_id:
                    print(f"    WARNING: No GitHub integration found for org {source_org_name}")
                    continue
                
                # Parse target information from display_name
                target_info = {}
                if display_name and "/" in display_name:
                    owner, name = display_name.split("/", 1)
                    target_info["owner"] = owner
                    target_info["name"] = name
                elif display_name and display_name != "unknown":
                    target_info["name"] = display_name
                
                # Get project information to extract branch data
                try:
                    projects = get_projects_for_target(source_org_id, target_id, SOURCE_API_TOKEN)
                    print(f"    Found {len(projects)} projects for target")
                    project_attributes = extract_target_attributes_from_projects(projects)
                    
                except Exception as e:
                    print(f"    Warning: Could not fetch projects for target {target_id}: {e}")
                    project_attributes = {}
                
                # Create target entries based on branch information
                if project_attributes:
                    if "branch" in project_attributes:
                        # Single branch case
                        target_entry = create_target_entry(
                            target_org_id, 
                            github_integration_id, 
                            target_info, 
                            project_attributes["branch"]
                        )
                        all_targets.append(target_entry)
                        
                        repo_info = f"{target_info.get('owner', '')}/{target_info.get('name', display_name or 'unknown')}"
                        print(f"    Added target: {repo_info} (branch: {project_attributes['branch']})")
                        
                    else:  # Multiple branches case
                        branches = project_attributes["branches"]
                        primary_branch = project_attributes.get("primary_branch")
                        
                        for branch in branches:
                            target_entry = create_target_entry(
                                target_org_id, 
                                github_integration_id, 
                                target_info, 
                                branch
                            )
                            all_targets.append(target_entry)
                            
                            repo_info = f"{target_info.get('owner', '')}/{target_info.get('name', display_name or 'unknown')}:{branch}"
                            primary_note = " (primary)" if branch == primary_branch else ""
                            print(f"    Added target: {repo_info}{primary_note}")
                        
        except Exception as e:
            print(f"Error processing org {source_org_name}: {e}")
    
    # Save results to JSON file
    result = {"targets": all_targets}
    
    output_filename = "snyk_import_targets.json"
    with open(output_filename, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nExtraction complete!")
    print(f"Total targets extracted: {len(all_targets)}")
    print(f"Results saved to: {output_filename}")


def main():
    """
    Main entry point for the target extraction script.
    """
    try:
        extract_targets()
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"Error: {e}")
        print("Please check your configuration and try again.")


if __name__ == "__main__":
    main()