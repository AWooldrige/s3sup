import os
import unittest
import s3sup.rules

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class TestPathRegexCompilation(unittest.TestCase):

    def test_path_regex_compiled(self):
        orig = {
            'path_specific': [
                {
                    'path': r"^recipe/.*",
                    "Cache-Control": "max-age=10"
                }
            ]
        }
        after = s3sup.rules._compile_path_regex(orig)
        path_re = after['path_specific'][0]['path_re']
        self.assertTrue(path_re.match('recipe/test.html') is not None)
        self.assertEqual(None, path_re.match('recipe.html'))


class TestDirectivesForPath(unittest.TestCase):

    def test_no_rules(self):
        rules = {}
        path = 'index.html'
        expected_directives = {}
        actual_directives = s3sup.rules.directives_for_path(path, rules)
        self.assertEqual(expected_directives, actual_directives)


class TestElaborateRules(unittest.TestCase):

    def setUp(self):
        self.rules = s3sup.rules.load_rules(os.path.join(
            MODULE_DIR, 'fixture_conf/elaborate.toml'))

    def assertDirectivesForPath(self, path, expected_directives):
        actual_directives = s3sup.rules.directives_for_path(
            path, self.rules)
        self.assertEqual(expected_directives, actual_directives)

    def test_deafult_paths_should_have_nothing_set(self):
        path = 'john_smith.txt'
        expected_directives = {}
        self.assertDirectivesForPath(path, expected_directives)

    def test_recipe_should_have_cache_control(self):
        path = 'recipe/pancakes.txt'
        expected_directives = {'Cache-Control': 'max-age=320'}
        self.assertDirectivesForPath(path, expected_directives)

    def test_lower_blocks_override_directives_set_higher(self):
        path = 'recipe/en-de/baking/♬ .cake.txt'
        expected_directives = {
            'Cache-Control': 'max-age=90',
            'Content-Language': 'de-DE, en-CA'
        }
        self.assertDirectivesForPath(path, expected_directives)

    def test_non_regex_and_values_inherit(self):
        path = 'recipe/in-dev/chef-card'
        expected_directives = {
            'Cache-Control': 'max-age=320',
            'Content-Type': 'text/chefcard3',
            'Content-Encoding': 'utf9.2'
        }
        self.assertDirectivesForPath(path, expected_directives)

    def test_website_redirects_work(self):
        path = '1999/history.shtml'
        expected_directives = {
            'WebsiteRedirectLocation': 'https://www.example.com/about-us/'
        }
        self.assertDirectivesForPath(path, expected_directives)

    def test_hidden_recipes(self):
        path = 'recipedownload/20190102.pdf'
        expected_directives = {
            'ACL': 'private',
            'Content-Disposition': 'attachment'
        }
        self.assertDirectivesForPath(path, expected_directives)
