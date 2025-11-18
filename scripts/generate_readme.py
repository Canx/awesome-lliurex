# scripts/generate_readme.py
import yaml
import re
import os

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

# Function to group projects by category
def group_by_category(projects):
    """Groups projects by category, with 'Sin clasificar' first."""
    categories = {}
    for project in projects:
        category = project.get('category', 'Sin clasificar')
        if category not in categories:
            categories[category] = []
        categories[category].append(project)

    # Sort categories: 'Sin clasificar' first, then alphabetically
    sorted_categories = []
    if 'Sin clasificar' in categories:
        sorted_categories.append(('Sin clasificar', categories['Sin clasificar']))

    # Add other categories alphabetically
    for cat in sorted(categories.keys()):
        if cat != 'Sin clasificar':
            sorted_categories.append((cat, categories[cat]))

    return sorted_categories

# Generate markdown content with separate sections
markdown_content = ""

# First: Community projects
if third_party_projects:
    markdown_content += "### Proyectos de la Comunidad\n\n"
    grouped = group_by_category(third_party_projects)
    for category, projects in grouped:
        markdown_content += f"#### {category}\n\n"
        for project in projects:
            markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"
        markdown_content += "\n"

# Second: Official projects
if official_projects:
    markdown_content += "### Proyectos Oficiales de LliureX\n\n"
    grouped = group_by_category(official_projects)
    for category, projects in grouped:
        markdown_content += f"#### {category}\n\n"
        for project in projects:
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
