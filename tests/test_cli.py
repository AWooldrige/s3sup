import os
import boto3
import shutil
import tempfile
import unittest
import moto
import pathlib
from click.testing import CliRunner

import s3sup.scripts.s3sup

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ['AWS_ACCESS_KEY_ID'] = 'FOO'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'BAR'


class TestInit(unittest.TestCase):

    def test_init_creates_new_skeleton_proj(self):
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(s3sup.scripts.s3sup.cli, ['init'])
            self.assertEqual(0, result.exit_code)
            self.assertIn('Skeleton configuration file created', result.stdout)
            with open('s3sup.toml', 'rt') as skel_file:
                self.assertIn('[[path_specific]]', skel_file.read())

    def test_init_does_not_override_existing(self):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            cf = pathlib.Path('s3sup.toml')
            cf.write_text('# Dummy file')
            result = runner.invoke(
                s3sup.scripts.s3sup.cli, ['init'], mix_stderr=False)
            self.assertEqual(1, result.exit_code)
            self.assertIn(
                's3sup configuration file already exists', result.stderr)
            self.assertEqual('# Dummy file', cf.read_text())


class TestStatus(unittest.TestCase):

    @moto.mock_s3
    def test_with_a_new_project(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['status', '-p', project_root, '-v'])

        self.assertEqual(0, result.exit_code)
        self.assertIn('new: 11 files', result.stdout)

        # Should be no objects uploaded after running status
        b = self.conn.Bucket('www.example.com')
        self.assertEqual([], [o for o in b.objects.all()])

    @moto.mock_s3
    def test_with_a_minimal_project(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['status', '-p', project_root])

        self.assertEqual(0, result.exit_code)
        self.assertIn('new: 1 file', result.stdout)

        # Should be no objects uploaded after running status
        b = self.conn.Bucket('www.example.com')
        self.assertEqual([], [o for o in b.objects.all()])


class TestUpload(unittest.TestCase):

    def assertInObj(self, text, obj):
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        obj.download_file(tmpp)
        with open(tmpp, 'rt') as tf:
            self.assertTrue(text in tf.read())
        os.remove(tmpp)

    @moto.mock_s3
    def test_not_an_s3sup_project_dir(self):
        runner = CliRunner()
        result = runner.invoke(s3sup.scripts.s3sup.cli, ['upload'])
        self.assertEqual(1, result.exit_code)
        self.assertIn('not an s3sup project directory', result.output)

    @moto.mock_s3
    def test_new_project(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertIn('new: 11 files', result.stdout)
        self.assertEqual(0, result.exit_code)

        # Check one object
        b = self.conn.Bucket('www.example.com')
        o = b.Object('staging/index.html')
        self.assertInObj('Hello world!', o)

    @moto.mock_s3
    def test_minimal_project(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertIn('new: 1 file', result.stdout)
        self.assertEqual(0, result.exit_code)

        # Check one object
        b = self.conn.Bucket('www.example.com')
        o = b.Object('index.html')
        self.assertInObj('I like it minimal.', o)

    @moto.mock_s3
    def test_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        b = self.conn.Bucket('www.example.com')
        o = b.Object('staging/robots.txt')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertIn('new: 11 files', result.stdout)
        self.assertEqual(0, result.exit_code)
        self.assertEqual('text/invalid', o.content_type)
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1.1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertEqual(0, result.exit_code)
        # Verify one of the changes.  No need to do the full whack as these are
        # tested in test_project.py.
        o = b.Object('staging/robots.txt')
        self.assertEqual('text/plain', o.content_type)

    @moto.mock_s3
    def test_works_with_current_directory_not_p(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        b = self.conn.Bucket('www.example.com')
        o = b.Object('staging/robots.txt')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        with runner.isolated_filesystem():
            new_projdir = os.path.join(os.getcwd(), 'proj')
            shutil.copytree(project_root, new_projdir)
            os.chdir(new_projdir)
            result = runner.invoke(s3sup.scripts.s3sup.cli, ['upload'])
            self.assertIn('new: 11 files', result.stdout)
            self.assertEqual(0, result.exit_code)
            self.assertEqual('text/invalid', o.content_type)

    @moto.mock_s3
    def test_dry_run(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        b = self.conn.Bucket('www.example.com')
        self.assertEqual([], [o for o in b.objects.all()])

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root, '-d'])
        self.assertEqual(0, result.exit_code)

        # Should be no objects uploaded
        self.assertEqual([], [o for o in b.objects.all()])


class TestInspect(unittest.TestCase):
    """Inspect commands should run fine without S3 connection"""

    @moto.mock_s3
    def test_normal_use_case_individual_file_in_current_dir(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        with runner.isolated_filesystem():
            new_projdir = os.path.join(os.getcwd(), 'proj')
            shutil.copytree(project_root, new_projdir)
            os.chdir(new_projdir)
            result = runner.invoke(
                s3sup.scripts.s3sup.cli,
                ['inspect', 'robots.txt'])
            self.assertEqual(0, result.exit_code)
            self.assertIn('robots.txt', result.stdout)
            self.assertIn('Cache-Control: private; max-age=400', result.stdout)

    def test_with_different_proj_dir_and_non_existing_file(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['inspect', '-p', project_root, 'robots.txt', 'non_existant.file',
             'white-paper.pdf'],
            mix_stderr=False)
        self.assertEqual(0, result.exit_code)
        self.assertIn('robots.txt', result.stdout)
        self.assertIn('Cache-Control: private; max-age=400', result.stdout)

        self.assertIn('non_existant.file', result.stderr)

        self.assertIn('white-paper.pdf', result.stdout)
        self.assertIn('StorageClass: REDUCED_REDUNDANCY', result.stdout)
