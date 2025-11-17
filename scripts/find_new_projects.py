# -*- coding: utf-8 -*-
import os
import yaml
import requests
import base64
import google.generativeai as genai
from typing import List, Dict, Any, Set

# --- Constants ---
PROJECTS_YAML_PATH = "projects.yaml"
GITHUB_API_URL = "https://api.github.com"
# We can expand this query to be more specific if needed
GITHUB_SEARCH_QUERY = "lliurex in:name,description,readme,topics"

# --- Environment Variables ---
# The default token provided by GitHub Actions
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
# User-provided secret for the classification AI
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Helper Functions ---

def get_existing_repos(file_path: str) -> Set[str]:
    """Reads the YAML file and returns a set of existing repository URLs."""
    if not os.path.exists(file_path):
        return set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        # Handle empty file
        try:
            projects = yaml.safe_load(f)
            if not projects:
                return set()
            return {p['repo'] for p in projects if 'repo' in p}
        except yaml.YAMLError:
            return set()


def get_project_categories(file_path: str) -> List[str]:
    """Reads the YAML file and returns a list of unique categories."""
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            projects = yaml.safe_load(f)
            if not projects:
                return []
            return sorted(list(set(p['category'] for p in projects if 'category' in p)))
        except yaml.YAMLError:
            return []

def search_github_repos(query: str, token: str) -> List[Dict[str, Any]]:
    """Searches GitHub for repositories matching the query."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    url = f"{GITHUB_API_URL}/search/repositories"
    params = {'q': query, 'per_page': 100} # Fetch up to 100 results
    
    print(f"Searching GitHub with query: {query}")
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response.json().get('items', [])

def get_readme_content(repo_full_name: str, token: str) -> str:
    """Fetches the README content for a given repository."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw" # Get raw content
    }
    url = f"{GITHUB_API_URL}/repos/{repo_full_name}/readme"
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        # Decode from bytes to string
        return response.text
    except requests.exceptions.HTTPError as e:
        print(f"Could not fetch README for {repo_full_name}: {e}")
        return ""

def classify_repo_with_gemini(repo: Dict[str, Any], readme: str, categories: List[str]) -> str:
    """
    Classifies a repository into one of the given categories using the Gemini API.
    """
    if not GEMINI_API_KEY:
        print("GEMINI_API_KEY not found. Skipping classification.")
        return "Sin clasificar"

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')

    prompt = f"""
    Eres un experto en el ecosistema de software LliureX. Tu tarea es clasificar un repositorio de GitHub en una de las siguientes categorías predefinidas.

    **Categorías disponibles:**
    {', '.join(categories)}

    **Información del repositorio:**
    - **Nombre:** {repo['name']}
    - **Descripción:** {repo.get('description', 'N/A')}
    - **Topics:** {', '.join(repo.get('topics', []))}
    - **README:**
    ---
    {readme[:2000]}
    ---

    Basándote en la información anterior, ¿cuál es la categoría más adecuada para este repositorio? Responde únicamente con el nombre de la categoría. Si ninguna categoría parece adecuada, responde "General".
    """

    try:
        print(f"Classifying repo: {repo['full_name']}")
        response = model.generate_content(prompt)
        category = response.text.strip()
        # Ensure the model returns a valid category
        if category in categories or category == "General":
            return category
        else:
            print(f"Warning: Model returned an invalid category '{category}'. Defaulting to 'General'.")
            return "General"
    except Exception as e:
        print(f"Error during classification with Gemini: {e}")
        return "Sin clasificar"


def save_projects(file_path: str, projects: List[Dict[str, Any]]):
    """Saves the list of projects to the YAML file."""
    # Sort projects by category, then by name for consistency
    projects.sort(key=lambda p: (p['category'], p['name']))
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump(projects, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"Successfully saved {len(projects)} projects to {file_path}")


# --- Main Execution ---

def main():
    """Main function to find, classify, and add new projects."""
    if not GITHUB_TOKEN:
        print("Error: GITHUB_TOKEN environment variable not set.")
        return

    # The script is in scripts/, so the project root is one level up.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yaml_path = os.path.join(project_root, PROJECTS_YAML_PATH)

    print("Starting process to find new LliureX projects...")
    
    existing_repos = get_existing_repos(yaml_path)
    print(f"Found {len(existing_repos)} existing repositories.")
    
    categories = get_project_categories(yaml_path)
    if not categories:
        print("Warning: No categories found in projects.yaml. Classification might be poor.")
        # Add a default list if empty
        categories = ["Aplicaciones", "Desarrollo", "Infraestructura", "Utilidades", "Documentación", "General", "Sin clasificar"]

    all_projects = []
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            all_projects = yaml.safe_load(f) or []

    found_repos = search_github_repos(GITHUB_SEARCH_QUERY, GITHUB_TOKEN)
    print(f"Found {len(found_repos)} potential repositories on GitHub.")

    new_projects_added = 0
    for repo in found_repos:
        repo_url = repo['html_url']
        if repo_url in existing_repos:
            continue

        print(f"\nProcessing new repository: {repo['full_name']}")
        
        readme_content = get_readme_content(repo['full_name'], GITHUB_TOKEN)
        
        # If classification is enabled, use it
        if GEMINI_API_KEY:
            category = classify_repo_with_gemini(repo, readme_content, categories)
        else:
            category = "Sin clasificar"
        
        print(f"  -> Classified as: {category}")

        new_project = {
            'name': repo['name'],
            'repo': repo_url,
            'desc': repo.get('description', 'Sin descripción.') or 'Sin descripción.',
            'category': category
        }
        
        all_projects.append(new_project)
        existing_repos.add(repo_url)
        new_projects_added += 1

    if new_projects_added > 0:
        print(f"\nAdded {new_projects_added} new projects. Saving to YAML file...")
        save_projects(yaml_path, all_projects)
    else:
        print("\nNo new projects found to add.")

if __name__ == "__main__":
    main()
