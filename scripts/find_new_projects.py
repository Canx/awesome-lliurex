# -*- coding: utf-8 -*-
import os
import yaml
import requests
import base64
from typing import List, Dict, Any, Set
from dotenv import load_dotenv

# Importar google.generativeai de forma opcional
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Advertencia: google-generativeai no está disponible. La clasificación automática no funcionará.")

# --- Constants ---
PROJECTS_YAML_PATH = "projects.yaml"
GITHUB_API_URL = "https://api.github.com"
# We can expand this query to be more specific if needed
GITHUB_SEARCH_QUERY = "lliurex in:name,description,readme,topics"



# --- Helper Functions ---

def get_existing_repos(file_path: str) -> Set[str]:
    """Reads the YAML file and returns a set of existing repository URLs."""
    if not os.path.exists(file_path):
        return set()
    
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and 'projects' in data and isinstance(data['projects'], list):
                return {p['url'] for p in data['projects'] if 'url' in p}
            return set()
        except yaml.YAMLError:
            return set()


def get_project_categories(file_path: str) -> List[str]:
    """Reads the YAML file and returns a list of unique categories."""
    if not os.path.exists(file_path):
        return []

    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = yaml.safe_load(f)
            if isinstance(data, dict) and 'projects' in data and isinstance(data['projects'], list):
                return sorted(list(set(p['category'] for p in data['projects'] if 'category' in p)))
            return []
        except yaml.YAMLError:
            return []

def search_github_repos(query: str, token: str = None) -> List[Dict[str, Any]]:
    """Searches GitHub for repositories matching the query."""
    if not token:
        print("ERROR: GitHub's search API requires authentication. Please provide a valid GitHub token.")
        print("For more information, see CONTRIBUTING.md")
        return []

    # Check if it's a fine-grained token (starts with github_pat_) or classic token
    if token.startswith("github_pat_"):
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github.v3+json"
        }
    else:
        # Classic token format
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }

    url = f"{GITHUB_API_URL}/search/repositories"
    params = {'q': query, 'per_page': 100} # Fetch up to 100 results

    print(f"Searching GitHub with query: {query}")
    print(f"  URL: {url}")
    print(f"  Params: {params}")
    response = requests.get(url, headers=headers, params=params)
    response.raise_for_status()

    json_response = response.json()
    total_count = json_response.get('total_count', 0)
    print(f"  GitHub API returned {total_count} total results for the query.")
    return json_response.get('items', [])

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

def classify_repo_with_gemini(repo: Dict[str, Any], readme: str, categories: List[str], gemini_api_key: str) -> str:
    """
    Classifies a repository into one of the given categories using the Gemini API.
    """
    if not GEMINI_AVAILABLE:
        print("Gemini API no está disponible. Skipping classification.")
        return "Sin clasificar"

    if not gemini_api_key:
        print("GEMINI_API_KEY not found. Skipping classification.")
        return "Sin clasificar"

    print(f"Attempting to use Gemini API for classification. API Key present: {bool(gemini_api_key)}")

    try:
        genai.configure(api_key=gemini_api_key)
        # Intentar usar diferentes modelos en orden de preferencia, empezando con el más asequible
        for model_name in ['gemini-1.5-flash', 'gemini-flash', 'gemini-1.5-pro', 'gemini-pro', 'gemini-1.0-pro']:
            try:
                model = genai.GenerativeModel(model_name)
                print(f"Using model: {model_name}")
                break
            except Exception as e:
                print(f"Model {model_name} not available: {e}")
                continue
        else:
            print("No Gemini models available, defaulting to 'Sin clasificar'")
            return "Sin clasificar"
    except Exception as e:
        print(f"Error configuring Gemini model or model not found: {e}")
        print("Please check your GEMINI_API_KEY and ensure 'gemini-pro' is available in your region.")
        print("Attempting to list available models for debugging:")
        try:
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    print(f"- {m.name} (supported)")
                else:
                    print(f"- {m.name} (not supported for generateContent)")
        except Exception as list_e:
            print(f"Could not list models: {list_e}")
        return "Sin clasificar"

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

        # Clean up the category response - sometimes the model returns extra text
        # Extract just the category by looking for the last meaningful word
        possible_categories = [cat.strip() for cat in category.split()]
        # Check if any of the possible categories match our valid categories
        for possible_cat in reversed(possible_categories):
            cleaned_cat = possible_cat.strip(' .:,;')
            if cleaned_cat in categories:
                return cleaned_cat
            elif cleaned_cat == "General":
                return cleaned_cat

        # If no match found in the above process, try to match exactly
        if category in categories or category == "General":
            return category
        else:
            print(f"Warning: Model returned an invalid category '{category}'. Available categories: {categories}. Defaulting to 'General'.")
            return "General"
    except Exception as e:
        print(f"Error during classification with Gemini for {repo['full_name']}: {e}")
        print("This might be due to API rate limits, an invalid prompt, or temporary service issues.")
        return "Sin clasificar"


def save_projects(file_path: str, projects: List[Dict[str, Any]]):
    """Saves the list of projects to the YAML file."""
    # Sort projects by category, then by name for consistency
    projects.sort(key=lambda p: (p.get('category', 'zzz'), p.get('name', 'zzz')))
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump({'projects': projects}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"Successfully saved {len(projects)} projects to {file_path}")


# --- Main Execution ---

def main(github_token: str = None, gemini_api_key: str = None):
    """Main function to find, classify, and add new projects."""
    load_dotenv() # Load environment variables from .env file
    
    if github_token is None:
        github_token = os.getenv("GITHUB_TOKEN")
    if gemini_api_key is None:
        gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not github_token:
        print("Error: GITHUB_TOKEN environment variable not set.")
        return

    # The script is in scripts/, so the project root is one level up.
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    yaml_path = os.path.join(project_root, PROJECTS_YAML_PATH)

    print("Starting process to find new LliureX projects...")
    
    # Load existing projects into a map for efficient lookup and modification
    existing_projects_map: Dict[str, Dict[str, Any]] = {}
    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            loaded_data = yaml.safe_load(f)
            if isinstance(loaded_data, dict) and 'projects' in loaded_data and isinstance(loaded_data['projects'], list):
                for p in loaded_data['projects']:
                    if 'url' in p:
                        existing_projects_map[p['url']] = p
            elif loaded_data is not None:
                print(f"Warning: {yaml_path} exists but its content is not a dictionary with a 'projects' list. Initializing with an empty list.")
    
    print(f"Found {len(existing_projects_map)} existing repositories in {PROJECTS_YAML_PATH}.")
    if existing_projects_map:
        print(f"  First 5 existing project URLs: {[url for url in existing_projects_map.keys()][:5]}")
    print(f"Existing projects map keys: {list(existing_projects_map.keys())[:5]}...") # Print first 5 keys for debugging
    
    categories = get_project_categories(yaml_path)
    if not categories:
        print("Warning: No categories found in projects.yaml. Using default categories.")
        # Add a default list if empty
        categories = ["AD/LDAP", "Aplicaciones", "Desarrollo", "Documentación", "Infraestructura", "Utilidades", "General", "Sin clasificar"]
    else:
        print(f"Found {len(categories)} existing categories: {categories}")

    found_repos = search_github_repos(GITHUB_SEARCH_QUERY, github_token)
    print(f"Found {len(found_repos)} potential repositories on GitHub.")

    new_projects_added = 0
    projects_reclassified = 0
    
    # This list will hold all projects, including new, re-classified, and unchanged ones
    updated_all_projects: List[Dict[str, Any]] = []
    # Use a set to track repo URLs that have been processed from found_repos
    processed_found_repo_urls: Set[str] = set()

    for repo in found_repos:
        repo_url = repo['html_url']
        
        if repo_url in processed_found_repo_urls: # Skip if already processed from search results
            continue

        processed_found_repo_urls.add(repo_url)

        if repo_url in existing_projects_map:
            existing_project = existing_projects_map[repo_url]
            
            if existing_project.get('category') == "Sin clasificar":
                print(f"\nRe-classifying existing project: {repo['full_name']}")
                readme_content = get_readme_content(repo['full_name'], github_token)
                
                if gemini_api_key and GEMINI_AVAILABLE:
                    category = classify_repo_with_gemini(repo, readme_content, categories, gemini_api_key)
                else:
                    category = "Sin clasificar"
                
                print(f"  -> Re-classified as: {category}")
                
                # Update the existing project entry
                existing_project['name'] = repo['name'] # Update name in case it changed
                existing_project['description'] = repo.get('description', 'Sin descripción.') or 'Sin descripción.'
                existing_project['category'] = category
                updated_all_projects.append(existing_project)
                projects_reclassified += 1
                # Remove from existing_projects_map so it's not added again later
                del existing_projects_map[repo_url]
            else:
                # Project exists and is already properly classified, just add it to the updated list
                updated_all_projects.append(existing_project)
                # Remove from existing_projects_map so it's not added again later
                del existing_projects_map[repo_url]
        else:
            # This is a completely new project
            print(f"\nProcessing new repository: {repo['full_name']}")
            readme_content = get_readme_content(repo['full_name'], github_token)
            
            if gemini_api_key and GEMINI_AVAILABLE:
                category = classify_repo_with_gemini(repo, readme_content, categories, gemini_api_key)
            else:
                category = "Sin clasificar"
            
            print(f"  -> Classified as: {category}")

            new_project_entry = {
                'name': repo['name'],
                'url': repo_url,
                'description': repo.get('description', 'Sin descripción.') or 'Sin descripción.',
                'category': category
            }
            updated_all_projects.append(new_project_entry)
            new_projects_added += 1

    # Add back any remaining projects from existing_projects_map
    # These are projects that were in projects.yaml but not found in the GitHub search results
    # (e.g., deleted from GitHub, or didn't match the search query anymore)
    for repo_url, project_data in existing_projects_map.items():
        updated_all_projects.append(project_data)

    if new_projects_added > 0 or projects_reclassified > 0:
        print(f"\nAdded {new_projects_added} new projects and re-classified {projects_reclassified} projects. Saving to YAML file...")
        save_projects(yaml_path, updated_all_projects)
    else:
        print("\nNo new projects found or projects to re-classify.")


if __name__ == "__main__":
    main()