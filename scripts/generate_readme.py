# scripts/generate_readme.py
import yaml
import re
import os
import argparse
from datetime import datetime

# --- Functions for fetching and sorting ---

def sort_projects(projects, sort_by):
    """Sorts projects by name or last update."""
    if sort_by == 'name':
        return sorted(projects, key=lambda p: p['name'].lower())
    
    if sort_by == 'update':
        return sorted(projects, key=lambda p: datetime.strptime(p.get('last_update', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ'), reverse=True)
    
    return projects

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
        # Sort projects within 'Sin clasificar' before adding
        sorted_projects = sorted(categories['Sin clasificar'], key=lambda p: p['name'].lower())
        sorted_categories.append(('Sin clasificar', sorted_projects))

    # Add other categories alphabetically
    for cat in sorted(categories.keys()):
        if cat != 'Sin clasificar':
            # Sort projects within each category
            sorted_projects = sorted(categories[cat], key=lambda p: p['name'].lower())
            sorted_categories.append((cat, sorted_projects))

    return sorted_categories

# --- Main script execution ---

def main():
    # --- Argument parsing ---
    parser = argparse.ArgumentParser(description="Generate README with sorted project lists.")
    parser.add_argument(
        '--sort-by',
        choices=['name', 'update'],
        default='name',
        help="Sort projects by 'name' (alphabetical) or 'update' (last commit date)."
    )
    parser.add_argument(
        '--output',
        default='README.md',
        help="Output file name (e.g., README.md, README_by_date.md)."
    )
    args = parser.parse_args()

    # --- File paths ---
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    projects_file = os.path.join(project_root, 'projects.yaml')
    template_file = os.path.join(project_root, 'README.template.md')
    output_file = os.path.join(project_root, args.output)

    # --- Read and process projects ---
    with open(projects_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    official_projects = []
    third_party_projects = []
    for project in data.get('projects', []):
        if project.get('official', False):
            official_projects.append(project)
        else:
            third_party_projects.append(project)

    # --- Sort project lists ---
    print(f"Sorting projects by: {args.sort_by}")
    official_projects = sort_projects(official_projects, args.sort_by)
    third_party_projects = sort_projects(third_party_projects, args.sort_by)

    # --- Generate Markdown content ---
    markdown_content = ""

    # Community projects
    if third_party_projects:
        markdown_content += "### Proyectos de la Comunidad\n\n"
        # When sorting by update, we still group by category, but projects within are sorted by the primary key
        grouped = group_by_category(third_party_projects)
        for category, projects_in_cat in grouped:
            markdown_content += f"#### {category}\n\n"
            # Here we re-sort if the main sort was 'update'
            sorted_list = sort_projects(projects_in_cat, args.sort_by)
            for project in sorted_list:
                 if args.sort_by == 'update' and 'last_update' in project:
                    date_str = datetime.strptime(project['last_update'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                    markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']} (Actualizado: {date_str})\n"
                 else:
                    markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"
            markdown_content += "\n"

    # Official projects
    if official_projects:
        markdown_content += "### Proyectos Oficiales de LliureX\n\n"
        grouped = group_by_category(official_projects)
        for category, projects_in_cat in grouped:
            markdown_content += f"#### {category}\n\n"
            sorted_list = sort_projects(projects_in_cat, args.sort_by)
            for project in sorted_list:
                if args.sort_by == 'update' and 'last_update' in project:
                    date_str = datetime.strptime(project['last_update'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                    markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']} (Actualizado: {date_str})\n"
                else:
                    markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"
            markdown_content += "\n"


    markdown_content = markdown_content.rstrip()

    # --- Update README ---
    with open(template_file, 'r', encoding='utf-8') as f:
        readme_content = f.read()

    pattern = r"(<!-- PROJECTS_START -->)(.*)(<!-- PROJECTS_END -->)"
    new_readme_content = re.sub(
        pattern,
        f"\\1\n{markdown_content}\n\\3",
        readme_content,
        flags=re.DOTALL
    )

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(new_readme_content)

    print(f"{output_file} has been successfully updated.")

if __name__ == "__main__":
    main()
