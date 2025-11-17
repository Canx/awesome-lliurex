# -*- coding: utf-8 -*-
import os
import unittest
import yaml
from unittest.mock import patch, MagicMock
from scripts.find_new_projects import get_existing_repos, get_project_categories, save_projects, main

class TestFindNewProjects(unittest.TestCase):

    def setUp(self):
        """Set up a dummy projects.yaml file for testing."""
        self.test_yaml_path = "test_projects.yaml"
        self.initial_data = {
            'projects': [
                {'name': 'Project 1', 'url': 'https://github.com/user/project1', 'description': 'Desc 1', 'category': 'Cat 1'},
                {'name': 'Project 2', 'url': 'https://github.com/user/project2', 'description': 'Desc 2', 'category': 'Cat 2'},
                {'name': 'Unclassified', 'url': 'https://github.com/user/unclassified', 'description': 'Desc 3', 'category': 'Sin clasificar'}
            ]
        }
        with open(self.test_yaml_path, 'w', encoding='utf-8') as f:
            yaml.dump(self.initial_data, f)

    def tearDown(self):
        """Remove the dummy YAML file after tests."""
        if os.path.exists(self.test_yaml_path):
            os.remove(self.test_yaml_path)

    def test_get_existing_repos(self):
        """Test that existing repository URLs are read correctly."""
        expected_repos = {
            'https://github.com/user/project1',
            'https://github.com/user/project2',
            'https://github.com/user/unclassified'
        }
        self.assertEqual(get_existing_repos(self.test_yaml_path), expected_repos)

    def test_get_project_categories(self):
        """Test that project categories are read and sorted correctly."""
        expected_categories = ['Cat 1', 'Cat 2', 'Sin clasificar']
        self.assertEqual(get_project_categories(self.test_yaml_path), expected_categories)

    def test_save_projects(self):
        """Test that projects are saved correctly to the YAML file."""
        new_projects = [
            {'name': 'Project A', 'url': 'https://github.com/user/projectA', 'description': 'Desc A', 'category': 'Cat A'},
            {'name': 'Project B', 'url': 'https://github.com/user/projectB', 'description': 'Desc B', 'category': 'Cat B'},
        ]
        save_projects(self.test_yaml_path, new_projects)
        
        with open(self.test_yaml_path, 'r', encoding='utf-8') as f:
            saved_data = yaml.safe_load(f)
        
        self.assertEqual(saved_data['projects'], new_projects)

    @patch('scripts.find_new_projects.search_github_repos')
    @patch('scripts.find_new_projects.get_readme_content')
    @patch('scripts.find_new_projects.classify_repo_with_gemini')
    @patch('scripts.find_new_projects.PROJECTS_YAML_PATH', "test_projects.yaml")
    def test_main_flow(self, mock_classify, mock_get_readme, mock_search):
        """Test the main function logic for adding and re-classifying projects."""
        # --- Mock GitHub Search Results ---
        mock_search.return_value = [
            # An existing, classified project (should not be changed)
            {'name': 'Project 1', 'html_url': 'https://github.com/user/project1', 'full_name': 'user/project1', 'description': 'Desc 1'},
            # An existing, unclassified project (should be re-classified)
            {'name': 'Unclassified', 'html_url': 'https://github.com/user/unclassified', 'full_name': 'user/unclassified', 'description': 'New Desc'},
            # A completely new project
            {'name': 'New Project', 'html_url': 'https://github.com/user/newproject', 'full_name': 'user/newproject', 'description': 'A new project.'}
        ]
        
        # --- Mock README Content ---
        mock_get_readme.return_value = "This is a README file."
        
        # --- Mock Gemini Classification ---
        # Simulate Gemini classifying the unclassified and new projects
        mock_classify.side_effect = ["Re-classified", "Newly-classified"]

        # --- Run the main function ---
        main(github_token='fake-token', gemini_api_key='fake-key')

        # --- Assertions ---
        with open(self.test_yaml_path, 'r', encoding='utf-8') as f:
            final_data = yaml.safe_load(f)
        
        projects = final_data['projects']
        
        # There should be 4 projects in total (2 old, 1 re-classified, 1 new)
        self.assertEqual(len(projects), 4)
        
        # Create a map for easy lookup
        projects_by_url = {p['url']: p for p in projects}
        
        # 1. Check the unchanged project
        self.assertIn('https://github.com/user/project1', projects_by_url)
        self.assertEqual(projects_by_url['https://github.com/user/project1']['category'], 'Cat 1')
        
        # 2. Check the re-classified project
        self.assertIn('https://github.com/user/unclassified', projects_by_url)
        reclassified_project = projects_by_url['https://github.com/user/unclassified']
        self.assertEqual(reclassified_project['category'], 'Re-classified')
        self.assertEqual(reclassified_project['description'], 'New Desc') # Description should be updated
        
        # 3. Check the new project
        self.assertIn('https://github.com/user/newproject', projects_by_url)
        new_project = projects_by_url['https://github.com/user/newproject']
        self.assertEqual(new_project['name'], 'New Project')
        self.assertEqual(new_project['category'], 'Newly-classified')
        
        # 4. Check the project that was in the original file but not in the search results
        self.assertIn('https://github.com/user/project2', projects_by_url)


if __name__ == '__main__':
    unittest.main()
