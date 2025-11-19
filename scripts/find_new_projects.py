# -*- coding: utf-8 -*-
import os
import yaml
import requests
import base64
import time
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
GITHUB_SEARCH_QUERY = "lliurex in:name,description,topics"



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
    """Searches GitHub for repositories matching the query, handling pagination."""
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
    params = {'q': query, 'per_page': 100, 'page': 1}  # Start with page 1
    all_items = []

    print(f"Searching GitHub with query: {query}")
    print(f"  URL: {url}")

    # Fetch multiple pages of results (GitHub API has a maximum of 1000 results for search)
    while True:
        print(f"  Fetching page {params['page']}, params: {params}")
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()

        json_response = response.json()
        items = json_response.get('items', [])
        total_count = json_response.get('total_count', 0)

        print(f"  Page {params['page']}: GitHub API returned {len(items)} results.")

        all_items.extend(items)

        # Check if we've reached the last page or hit the GitHub API limit (max 1000 results)
        if len(items) < 100 or len(all_items) >= min(total_count, 1000):
            break

        # Move to the next page
        params['page'] += 1

    print(f"  Total results collected: {len(all_items)} out of {total_count} possible.")
    return all_items

def get_readme_content(repo_full_name: str, token: str) -> str:
    """Fetches the README content for a given repository, trying different possible names and branches."""
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.raw" # Get raw content
    }

    # First, try the standard README endpoint which automatically finds the README
    standard_url = f"{GITHUB_API_URL}/repos/{repo_full_name}/readme"

    try:
        response = requests.get(standard_url, headers=headers)
        response.raise_for_status()
        return response.text
    except requests.exceptions.HTTPError:
        # If standard README endpoint fails, try specific file names with contents endpoint
        possible_readme_names = [
            "README.md", "readme.md", "README", "readme",
            "Readme.md", "ReadMe.md", "README.MD", "readme.MD",
            "Readme", "ReadMe", "README.txt", "readme.txt"
        ]

        # Try to get default branch first to use in requests
        try:
            repo_info_response = requests.get(f"{GITHUB_API_URL}/repos/{repo_full_name}", headers=headers)
            repo_info_response.raise_for_status()
            default_branch = repo_info_response.json().get('default_branch', 'main')
        except:
            # If we can't get the default branch, try main and master
            default_branch = 'main'

        possible_branches = [default_branch, 'master', 'main']

        for branch in possible_branches:
            for readme_name in possible_readme_names:
                url = f"{GITHUB_API_URL}/repos/{repo_full_name}/contents/{readme_name}?ref={branch}"

                try:
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()

                    # For the contents endpoint, we get JSON with base64 encoded content
                    content_json = response.json()
                    if 'content' in content_json:
                        import base64
                        content = base64.b64decode(content_json['content']).decode('utf-8')
                        return content
                except requests.exceptions.HTTPError as e:
                    if response.status_code == 404:
                        continue  # Try the next file
                    else:
                        print(f"Could not fetch README file {readme_name} from branch {branch} for {repo_full_name}: {e}")
                        continue
                except Exception as e:
                    print(f"Unexpected error while fetching README file {readme_name} from branch {branch} for {repo_full_name}: {e}")
                    continue

    print(f"Could not fetch README for {repo_full_name}: tried various file names and branches.")
    return ""

# Variable global para almacenar modelos disponibles (para evitar múltiples llamadas a la API)
AVAILABLE_GEMINI_MODELS = None

# Variable global para controlar la tasa de solicitudes a la API
GEMINI_REQUEST_COUNT = 0

def get_available_gemini_models(gemini_api_key: str):
    """Obtiene la lista de modelos Gemini disponibles, cacheándolos para reutilizar."""
    global AVAILABLE_GEMINI_MODELS

    if AVAILABLE_GEMINI_MODELS is not None:
        return AVAILABLE_GEMINI_MODELS

    if not GEMINI_AVAILABLE or not gemini_api_key:
        AVAILABLE_GEMINI_MODELS = []
        return AVAILABLE_GEMINI_MODELS

    try:
        genai.configure(api_key=gemini_api_key)

        available_models = []
        try:
            for m in genai.list_models():
                if "generateContent" in m.supported_generation_methods:
                    available_models.append(m.name.replace("models/", ""))
                    print(f"- {m.name} (supported)")
                else:
                    print(f"- {m.name} (not supported for generateContent)")
        except Exception as list_e:
            print(f"Could not list models: {list_e}")

        AVAILABLE_GEMINI_MODELS = available_models
        return available_models
    except Exception as e:
        print(f"Error configuring Gemini API to list models: {e}")
        AVAILABLE_GEMINI_MODELS = []
        return AVAILABLE_GEMINI_MODELS

# Variable global para indicar si se ha alcanzado la cuota diaria
GEMINI_DAILY_QUOTA_EXCEEDED = False

def classify_repo_with_gemini(repo: Dict[str, Any], readme: str, categories: List[str], gemini_api_key: str) -> str:
    """
    Classifies a repository into one of the given categories using the Gemini API.
    """
    global GEMINI_DAILY_QUOTA_EXCEEDED

    # Si ya hemos superado la cuota diaria, no intentar más clasificaciones
    if GEMINI_DAILY_QUOTA_EXCEEDED:
        print(f"Daily quota already exceeded. Skipping classification for {repo['full_name']}")
        return "Sin clasificar"

    if not GEMINI_AVAILABLE:
        print("Gemini API no está disponible. Skipping classification.")
        return "Sin clasificar"

    if not gemini_api_key:
        print("GEMINI_API_KEY not found. Skipping classification.")
        return "Sin clasificar"

    print(f"Attempting to use Gemini API for classification. API Key present: {bool(gemini_api_key)}")

    try:
        # Obtener modelos disponibles (una sola vez, usando cache)
        available_models = get_available_gemini_models(gemini_api_key)

        # Priorizar modelos flash de la versión 2.5, intentando gemini-2.5-flash-lite primero
        preferred_models = []
        for model_name in ['gemini-2.5-flash-lite', 'gemini-2.5-flash']:
            if model_name in available_models:
                preferred_models.append(model_name)

        # Si no hay modelos flash 2.5 disponibles, usar cualquier otro modelo Gemini flash 2.5 disponible
        if not preferred_models:
            for model_name in available_models:
                if 'gemini' in model_name.lower() and '2.5' in model_name and 'flash' in model_name.lower():
                    preferred_models.append(model_name)

        # Intentar usar modelos en orden de preferencia
        for model_name in preferred_models:
            try:
                model = genai.GenerativeModel(model_name)
                print(f"Using model: {model_name}")
                break
            except Exception as e:
                print(f"Model {model_name} not available for generation: {e}")
                continue
        else:
            print("No suitable Gemini models available for text generation, defaulting to 'Sin clasificar'")
            return "Sin clasificar"
    except Exception as e:
        print(f"Error configuring Gemini model or model not found: {e}")
        print("Please check your GEMINI_API_KEY and ensure Gemini 2.5 flash models are available in your region.")
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

    global GEMINI_REQUEST_COUNT

    try:
        print(f"Classifying repo: {repo['full_name']}")

        # Incrementar el contador de solicitudes
        GEMINI_REQUEST_COUNT += 1

        # Introducir un retraso para no exceder la cuota de la API
        # La API tiene un límite de 15 solicitudes por minuto por modelo
        # Para estar muy seguro de no exceder la cuota, vamos a usar un retraso más largo
        # Aproximadamente 1 solicitud cada 8-12 segundos
        import random
        delay = random.uniform(8.0, 12.0)  # Aproximadamente 5-7 solicitudes por minuto
        print(f"Waiting {delay:.2f} seconds before next request to respect API quota...")
        time.sleep(delay)

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
        # Si es un error de cuota, intentar obtener el tiempo de espera de la API
        error_str = str(e).lower()
        if "quota" in error_str or "rate" in error_str or "limit" in error_str or "429" in error_str:
            # Intentar extraer el tiempo de espera de la respuesta de error
            import re
            # Buscar el tiempo de espera en la respuesta: "Please retry in X.XXs"
            retry_match = re.search(r"retry in (\d+\.?\d*)s", str(e))
            if retry_match:
                retry_time = float(retry_match.group(1)) + 2  # Agregar 2 segundos adicionales como margen de seguridad
                print(f"Quota/rate limit error detected. Waiting for {retry_time:.2f} seconds (as indicated by API) before continuing...")
                time.sleep(retry_time)
            else:
                # Si no podemos extraer el tiempo, usar el valor por defecto
                print("Quota/rate limit error detected. Waiting for 60 seconds before continuing...")
                time.sleep(60)  # Esperar 60 segundos si se detecta un error de cuota

            # Marcar que hemos superado la cuota diaria
            GEMINI_DAILY_QUOTA_EXCEEDED = True
            print("Daily quota exceeded. Further classifications will be skipped until next restart.")
        print("This might be due to API rate limits, an invalid prompt, or temporary service issues.")
        return "Sin clasificar"


def save_projects(file_path: str, projects: List[Dict[str, Any]]):
    """Saves the list of projects to the YAML file."""
    # Sort projects by official status (official projects first), then by category, then by name for consistency
    projects.sort(key=lambda p: (not p.get('official', False), p.get('category', 'zzz'), p.get('name', 'zzz')))
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump({'projects': projects}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"Successfully saved {len(projects)} projects to {file_path}")


def update_projects_batch(file_path: str, all_current_projects: List[Dict[str, Any]]):
    """Updates the projects file with all current projects."""
    # Sort projects by official status (official projects first), then by category, then by name for consistency
    all_current_projects.sort(key=lambda p: (not p.get('official', False), p.get('category', 'zzz'), p.get('name', 'zzz')))

    # Save the updated projects
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.dump({'projects': all_current_projects}, f, allow_unicode=True, sort_keys=False, default_flow_style=False)
    print(f"Successfully updated {file_path} with batch. Total projects: {len(all_current_projects)}")


def update_readme_progressively():
    """Update the README.md file with current projects data."""
    import re

    # Get the absolute path of the script's directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Get the project root directory by going one level up
    project_root = os.path.dirname(script_dir)

    # Construct absolute paths for the files
    projects_file = os.path.join(project_root, 'projects.yaml')
    readme_file = os.path.join(project_root, 'README.md')

    # Read projects data
    with open(projects_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    # Separate official and third-party projects
    official_projects = []
    third_party_projects = []

    for project in data.get('projects', []):
        if project.get('official', False):
            official_projects.append(project)
        else:
            third_party_projects.append(project)

    # Generate markdown content with separate sections
    markdown_content = ""

    if official_projects:
        markdown_content += "### Proyectos Oficiales de LliureX\n\n"
        for project in official_projects:
            markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"
        markdown_content += "\n"

    if third_party_projects:
        markdown_content += "### Proyectos de Terceros\n\n"
        for project in third_party_projects:
            markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"
        markdown_content += "\n"

    # Remove the trailing newline
    markdown_content = markdown_content.rstrip()

    # Read README.md content
    with open(readme_file, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    # Replace the content between the markers
    # Using re.DOTALL to make '.' match newlines
    pattern = r"(<!-- PROJECTS_START -->)(.*)(<!-- PROJECTS_END -->)"
    new_readme_content = re.sub(
        pattern,
        f"\\1\n{markdown_content}\n\\3",
        readme_content,
        flags=re.DOTALL
    )

    # Write the updated content back to README.md
    with open(readme_file, 'w', encoding='utf-8') as f:
        f.write(new_readme_content)

    print("README.md has been successfully updated.")


# --- Main Execution ---

def main(github_token: str = None, gemini_api_key: str = None, batch_size: int = 10):
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

    # Load existing projects into a list for easy management
    all_projects: List[Dict[str, Any]] = []
    existing_projects_map: Dict[str, Dict[str, Any]] = {}

    if os.path.exists(yaml_path):
        with open(yaml_path, 'r', encoding='utf-8') as f:
            loaded_data = yaml.safe_load(f)
            if isinstance(loaded_data, dict) and 'projects' in loaded_data and isinstance(loaded_data['projects'], list):
                all_projects = loaded_data['projects']
                for p in loaded_data['projects']:
                    if 'url' in p:
                        # Initialize the 'official' property for backward compatibility if it doesn't exist
                        if 'official' not in p:
                            p['official'] = p['url'].startswith('https://github.com/lliurex/')
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

    # Use a set to track repo URLs that have been processed from found_repos
    processed_found_repo_urls: Set[str] = set()

    # Process repositories in batches to update the YAML file progressively
    for i in range(0, len(found_repos), batch_size):
        batch = found_repos[i:i + batch_size]
        print(f"\nProcessing batch {i//batch_size + 1}/{(len(found_repos) + batch_size - 1)//batch_size}...")

        batch_projects = []  # Keep track of projects updated in this batch

        for repo in batch:
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
                    # Detectar si es un proyecto oficial de LliureX (en el repositorio lliurex)
                    existing_project['official'] = repo_url.startswith('https://github.com/lliurex/')
                    projects_reclassified += 1
                else:
                    # Project exists and is already properly classified
                    # Make sure the official property is set correctly
                    existing_project['official'] = repo_url.startswith('https://github.com/lliurex/')

                # Add to batch projects so we can update the global all_projects list
                batch_projects.append(existing_project)
            else:
                # This is a completely new project
                print(f"\nProcessing new repository: {repo['full_name']}")
                readme_content = get_readme_content(repo['full_name'], github_token)

                if gemini_api_key and GEMINI_AVAILABLE:
                    category = classify_repo_with_gemini(repo, readme_content, categories, gemini_api_key)
                else:
                    category = "Sin clasificar"

                print(f"  -> Classified as: {category}")

                # Detectar si es un proyecto oficial de LliureX (en el repositorio lliurex)
                is_official = repo_url.startswith('https://github.com/lliurex/')
                new_project_entry = {
                    'name': repo['name'],
                    'url': repo_url,
                    'description': repo.get('description', 'Sin descripción.') or 'Sin descripción.',
                    'category': category,
                    'official': is_official
                }
                batch_projects.append(new_project_entry)
                new_projects_added += 1

        # Update the all_projects list with the batch results
        for project in batch_projects:
            # Remove if already in list to avoid duplicates
            all_projects = [p for p in all_projects if p['url'] != project['url']]
            # Add the updated/new version
            all_projects.append(project)

        # Update the projects file with all projects processed so far
        update_projects_batch(yaml_path, all_projects)

        # Also update the README.md file progresively
        update_readme_progressively()

    # After processing all found repositories, make sure to include any projects that
    # were in the original file but were not found in the GitHub search
    # These are projects that may have been deleted from GitHub or don't match search criteria anymore
    original_urls = set(existing_projects_map.keys())
    processed_urls = processed_found_repo_urls
    unprocessed_original_urls = original_urls - processed_urls

    if unprocessed_original_urls:
        for url in unprocessed_original_urls:
            project = existing_projects_map[url]
            # Add to all_projects if not already there
            if not any(p['url'] == url for p in all_projects):
                all_projects.append(project)

        # Initialize the 'official' property for any existing projects that don't have it yet (for backward compatibility)
        for project in all_projects:
            if 'official' not in project:
                project['official'] = project['url'].startswith('https://github.com/lliurex/')

        # Update the projects file one final time to include unprocessed original projects
        update_projects_batch(yaml_path, all_projects)

        # Also update the README.md file one final time
        update_readme_progressively()

    if new_projects_added > 0 or projects_reclassified > 0:
        print(f"\nAdded {new_projects_added} new projects and re-classified {projects_reclassified} projects. Final update completed...")
    else:
        print("\nNo new projects found or projects to re-classify.")


if __name__ == "__main__":
    main()