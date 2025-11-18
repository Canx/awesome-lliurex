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
