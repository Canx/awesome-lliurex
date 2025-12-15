# scripts/generate_readme.py
import yaml
import re
import os
import argparse
from datetime import datetime

def sort_projects(projects, sort_by):
    """Sorts projects by official status first, then by the specified key."""
    if sort_by == 'name':
        return sorted(projects, key=lambda p: (not p.get('official', False), p['name'].lower()))
    
    if sort_by == 'update':
        return sorted(projects, key=lambda p: (not p.get('official', False), datetime.strptime(p.get('last_update', '1970-01-01T00:00:00Z'), '%Y-%m-%dT%H:%M:%SZ')), reverse=True)
    
    return projects

def main():
    parser = argparse.ArgumentParser(description="Generate project list files.")
    parser.add_argument('--sort-by', choices=['name', 'update'], default='name', help="Sort projects by 'name' or 'update'.")
    parser.add_argument('--output', required=True, help="Output file name.")
    args = parser.parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(script_dir)
    projects_file = os.path.join(project_root, 'projects.yaml')
    template_file = os.path.join(project_root, 'PROJECT_LIST.template.md')
    output_file = os.path.join(project_root, args.output)

    with open(projects_file, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    all_projects = data.get('projects', [])
    
    print(f"Sorting projects by: {args.sort_by}")
    sorted_projects = sort_projects(all_projects, args.sort_by)

    markdown_content = "### Proyectos Oficiales\n\n"
    has_official = False
    for project in sorted_projects:
        if project.get('official'):
            has_official = True
            if args.sort_by == 'update' and 'last_update' in project and project['last_update']:
                date_str = datetime.strptime(project['last_update'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']} (Actualizado: {date_str})\n"
            else:
                markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"

    if has_official:
        markdown_content += "\n"

    markdown_content += "### Proyectos de la Comunidad\n\n"
    for project in sorted_projects:
        if not project.get('official'):
            if args.sort_by == 'update' and 'last_update' in project and project['last_update']:
                date_str = datetime.strptime(project['last_update'], '%Y-%m-%dT%H:%M:%SZ').strftime('%Y-%m-%d')
                markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']} (Actualizado: {date_str})\n"
            else:
                markdown_content += f"- **[{project['name']}]({project['url']})**: {project['description']}\n"

    markdown_content = markdown_content.rstrip()

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
