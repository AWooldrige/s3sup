import os
import boto3
import shutil
import tempfile
import traceback
import unittest
import moto
import pathlib
from click.testing import CliRunner

import s3sup.scripts.s3sup

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))
os.environ['AWS_ACCESS_KEY_ID'] = 'FOO'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'BAR'


def all_bucket_keys(bucket):
    return ([o.key for o in bucket.objects.all()])


class S3supCliTestCaseBase(unittest.TestCase):

    def assertSuccess(self, result):
        if result.exit_code != 0:
            print('\nCOMMAND FAILED')
            print('\nSTDOUT: \n{0}'.format(result.stdout))
            # Working around
            # https://github.com/pallets/click/issues/1193
            try:
                print('\nSTDERR: \n{0}'.format(result.stderr))
            except ValueError:
                print('\nSTDERR: -')
            if result.exception:
                print('\nUNCAUGHT EXCEPTION RAISED:')
                print(result.exc_info)
                print('\nTRACEBACK:')
                traceback.print_tb(result.exc_info[2])
        self.assertEqual(0, result.exit_code)

    def create_example_bucket(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
        b = self.conn.Bucket('www.example.com')
        return b

    def upload_fixture_proj_dir(self, fixture_proj_dir, invoke_cmd):
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            new_projdir = os.path.join(os.getcwd(), 'proj')
            shutil.copytree(fixture_proj_dir, new_projdir)
            os.chdir(new_projdir)
            result = runner.invoke(
                s3sup.scripts.s3sup.cli,
                invoke_cmd,
                mix_stderr=False)
            return result


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


class TestStatus(S3supCliTestCaseBase):

    @moto.mock_s3
    def test_with_a_new_project(self):
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['status', '-p', project_root, '-v'],
            mix_stderr=False)
        self.assertSuccess(result)
        self.assertIn('new: 11 files', result.stdout)

        # Should be no objects uploaded after running status
        self.assertEqual([], [o for o in b.objects.all()])

    @moto.mock_s3
    def test_with_a_minimal_project(self):
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['status', '-p', project_root],
            mix_stderr=False)
        self.assertSuccess(result)
        self.assertIn('new: 1 file', result.stdout)

        # Should be no objects uploaded after running status
        self.assertEqual([], [o for o in b.objects.all()])

    @moto.mock_s3
    def test_nodelete(self):
        # Get things uploaded first so we have something to delete
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload'])
        self.assertSuccess(cmd_result)
        self.assertIn(
            'staging/assets/landscape.62.png', all_bucket_keys(b))

        # First check that it would have been deleted without --nodelete
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1.1')
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['status'])
        self.assertSuccess(cmd_result)
        self.assertIn('deleted: 1 file', cmd_result.stdout)
        self.assertNotIn('deleted but protected: 1 file', cmd_result.stdout)

        # Now with --nodelete
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['status', '--nodelete'])
        self.assertSuccess(cmd_result)
        self.assertIn('deleted but protected: 1 file', cmd_result.stdout)
        self.assertNotIn('deleted: 1 file', cmd_result.stdout)


class TestUpload(S3supCliTestCaseBase):

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
    def test_bucket_doesnt_exist(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload'])
        self.assertEqual(1, cmd_result.exit_code)
        self.assertIn('S3 bucket does not exist', cmd_result.stderr)

    @moto.mock_s3
    def test_new_project(self):
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertIn('new: 11 files', result.stdout)
        self.assertSuccess(result)

        # Check one object
        o = b.Object('staging/index.html')
        self.assertInObj('Hello world!', o)

    @moto.mock_s3
    def test_minimal_project(self):
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertIn('new: 1 file', result.stdout)
        self.assertSuccess(result)

        # Check one object
        o = b.Object('index.html')
        self.assertInObj('I like it minimal.', o)

    @moto.mock_s3
    def test_project_changes(self):
        b = self.create_example_bucket()
        o = b.Object('staging/robots.txt')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertSuccess(result)
        self.assertIn('new: 11 files', result.stdout)
        self.assertEqual('text/invalid', o.content_type)
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1.1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root])
        self.assertSuccess(result)
        # Verify one of the changes.  No need to do the full whack as these are
        # tested in test_project.py.
        o = b.Object('staging/robots.txt')
        self.assertEqual('text/plain', o.content_type)

    @moto.mock_s3
    def test_works_with_current_directory_not_p(self):
        b = self.create_example_bucket()
        o = b.Object('staging/robots.txt')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        with runner.isolated_filesystem():
            new_projdir = os.path.join(os.getcwd(), 'proj')
            shutil.copytree(project_root, new_projdir)
            os.chdir(new_projdir)
            result = runner.invoke(s3sup.scripts.s3sup.cli, ['upload'])
            self.assertSuccess(result)
            self.assertIn('new: 11 files', result.stdout)
            self.assertEqual('text/invalid', o.content_type)

    @moto.mock_s3
    def test_dry_run(self):
        b = self.create_example_bucket()
        self.assertEqual([], [o for o in b.objects.all()])

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner()
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['upload', '-p', project_root, '-d'])
        self.assertSuccess(result)

        # Should be no objects uploaded
        self.assertEqual([], [o for o in b.objects.all()])

    @moto.mock_s3
    def test_nodelete(self):
        b = self.create_example_bucket()
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload'])
        self.assertSuccess(cmd_result)
        self.assertIn(
            'staging/assets/landscape.62.png', all_bucket_keys(b))

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1.1')

        # Double check that --dryrun definitely still works with --nodelete
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload', '--dryrun', '--nodelete'])
        self.assertSuccess(cmd_result)
        self.assertIn(
            'staging/assets/landscape.62.png', all_bucket_keys(b))
        self.assertNotIn(
            'staging/contact/index.html', all_bucket_keys(b))

        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload', '--nodelete'])
        self.assertSuccess(cmd_result)
        # This would have been deleted without --nodelete
        self.assertIn(
            'staging/assets/landscape.62.png', all_bucket_keys(b))
        # This should still be uploaded
        self.assertIn(
            'staging/contact/index.html', all_bucket_keys(b))

        # Now do the full upload and make sure things get deleted after
        cmd_result = self.upload_fixture_proj_dir(
           project_root, ['upload'])
        self.assertSuccess(cmd_result)
        self.assertNotIn(
            'staging/assets/landscape.62.png', all_bucket_keys(b))


class TestInspect(S3supCliTestCaseBase):
    """Inspect commands should run fine without S3 connection"""

    @moto.mock_s3
    def test_minimal_project(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        runner = CliRunner(mix_stderr=False)
        result = runner.invoke(
            s3sup.scripts.s3sup.cli,
            ['inspect', '-p', project_root, 'index.html'],
            mix_stderr=False)
        self.assertSuccess(result)
        self.assertIn('ACL: public-read', result.stdout)

    @moto.mock_s3
    def test_normal_use_case_individual_file_in_current_dir(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        runner = CliRunner(mix_stderr=False)
        with runner.isolated_filesystem():
            new_projdir = os.path.join(os.getcwd(), 'proj')
            shutil.copytree(project_root, new_projdir)
            os.chdir(new_projdir)
            result = runner.invoke(
                s3sup.scripts.s3sup.cli,
                ['inspect', 'robots.txt'],
                mix_stderr=False)
            self.assertSuccess(result)
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
        self.assertSuccess(result)
        self.assertIn('robots.txt', result.stdout)
        self.assertIn('Cache-Control: private; max-age=400', result.stdout)

        self.assertIn('non_existant.file', result.stderr)

        self.assertIn('white-paper.pdf', result.stdout)
        self.assertIn('StorageClass: REDUCED_REDUNDANCY', result.stdout)
