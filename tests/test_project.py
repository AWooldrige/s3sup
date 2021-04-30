import os
import tempfile
import unittest
import pathlib
import shutil

import boto3
import botocore
import moto

from s3sup.project import Project

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ['AWS_ACCESS_KEY_ID'] = 'FOO'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'BAR'


def all_bucket_keys(bucket):
    return ([o.key for o in bucket.objects.all()])


class TestProject(unittest.TestCase):

    @moto.mock_s3
    def test_build_non_existant_remote_catalogue(self):
        conn = boto3.resource('s3', region_name='eu-west-1')
        conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.get_remote_catalogue()
        self.assertEqual({}, cat.to_dict())

    @moto.mock_s3
    def test_build_existing_old_csv_catalogue(self):
        conn = boto3.resource('s3', region_name='eu-west-1')
        conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        b = conn.Bucket('www.example.com')
        exp_csv_p = os.path.join(
            MODULE_DIR, 'expected_cat_fixture_proj_1.csv')
        with open(exp_csv_p, 'rb') as exp_csv_f:
            b.put_object(
                Key='staging/.s3sup.catalogue.csv',
                ACL='private',
                Body=exp_csv_f)
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.get_remote_catalogue()
        self.assertTrue('assets/logo.svg' in cat.to_dict())


class TestProjectSyncNoChanges(unittest.TestCase):

    @moto.mock_s3
    def test_no_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        p.sync()

        project_root_n = os.path.join(MODULE_DIR, 'fixture_proj_1')
        pn = Project(project_root_n)
        pn.sync()

        b = self.conn.Bucket('www.example.com')
        o = b.Object('staging/index.html')
        self.assertEqual('private; max-age=400', o.cache_control)


class TestProjectSyncProjectChanges(unittest.TestCase):

    def assertInObj(self, text, obj):
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        obj.download_file(tmpp)
        with open(tmpp, 'rt') as tf:
            self.assertTrue(text in tf.read())
        os.remove(tmpp)

    @moto.mock_s3
    def test_fixture_proj_2_minimal(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        p = Project(project_root)
        p.sync()

        b = self.conn.Bucket('www.example.com')
        o = b.Object('index.html')
        self.assertInObj('I like it minimal.', o)

    @moto.mock_s3
    def test_multiple_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        p.sync()

        project_root_n = os.path.join(MODULE_DIR, 'fixture_proj_1.1')
        pn = Project(project_root_n)
        pn.sync()

        b = self.conn.Bucket('www.example.com')
        o = b.Object('staging/index.html')
        self.assertEqual('private; max-age=400', o.cache_control)

        # Check new uploaded file
        o = b.Object('staging/contact/index.html')
        self.assertEqual('private; max-age=400', o.cache_control)

        # Check file that had contents modified
        o = b.Object('staging/products.html')
        self.assertInObj('A new additional product!', o)

        # Check file that had content and attrs modified
        o = b.Object('staging/assets/stylesheet.css')
        self.assertInObj('padding: 1em;', o)
        self.assertEqual('max-age=1212', o.cache_control)

        # Check file that had attributes changed
        o = b.Object('staging/robots.txt')
        self.assertInObj('User-agent: *', o)
        self.assertEqual('text/plain', o.content_type)

        # Check file that had attributes removed
        o = b.Object('staging/white-paper.pdf')
        self.assertEqual(None, o.content_disposition)

        # Check file that had been deleted
        o = b.Object('staging/assets/landscape.62.png')
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        with self.assertRaises(botocore.exceptions.ClientError):
            o.download_file(tmpp)
        os.remove(tmpp)


class TestMultipleProjectConfigurations(unittest.TestCase):

    def create_example_bucket(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        b = self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        return b

    def create_projdir_with_conf(self, skeleton_dir_name, new_dir, config):
        original_dir = pathlib.Path(
            MODULE_DIR).joinpath(skeleton_dir_name).resolve()
        new_dir_path = pathlib.Path(new_dir).joinpath('proj')
        shutil.copytree(original_dir, new_dir_path)
        cf = pathlib.Path(new_dir_path).joinpath('s3sup.toml')
        cf.write_text(config)
        return new_dir_path

    @moto.mock_s3
    def test_basic_upload(self):
        b = self.create_example_bucket()
        conf = '''
[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.0', tmpd, conf)
            p = Project(project_root)
            p.sync()
        self.assertIn('assets/landscape.62.png', all_bucket_keys(b))
        # Check default headers
        o = b.Object('index.html')
        self.assertEqual('max-age=10', o.cache_control)

    @moto.mock_s3
    def test_nodelete(self):
        b = self.create_example_bucket()
        conf = '''
preserve_deleted_files = true

[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.0', tmpd, conf)
            p = Project(project_root)
            p.sync()

        # First time with nodelete
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.1', tmpd, conf)
            p = Project(project_root)
            p.sync()

        self.assertIn('index.html', all_bucket_keys(b))
        self.assertIn('assets/landscape.62.png', all_bucket_keys(b))

        # Second time without nodelete
        conf = '''
[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.1', tmpd, conf)
            p = Project(project_root)
            p.sync()

        self.assertIn('index.html', all_bucket_keys(b))
        self.assertNotIn('assets/landscape.62.png', all_bucket_keys(b))

    @moto.mock_s3
    def test_nodelete_supplied_at_runtime_overrides_conf(self):
        """
        The --nodelete functionality can be specified in both the configuration
        file and on the command line. The command line one should take priority
        """
        b = self.create_example_bucket()
        conf = '''
preserve_deleted_files = false

[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.0', tmpd, conf)
            p = Project(project_root)
            p.sync()

        # True in conf but False by runtime should == False
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.1', tmpd, conf)
            p = Project(project_root, preserve_deleted_files=True)
            p.sync()

        self.assertIn('index.html', all_bucket_keys(b))
        self.assertIn('assets/landscape.62.png', all_bucket_keys(b))

    @moto.mock_s3
    def test_s3_project_root_can_be_set_empty_string_or_default(self):
        b = self.create_example_bucket()
        conf = '''
[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.0', tmpd, conf)
            p = Project(project_root)
            diff, new_remote_cat = p.calculate_diff()
            p.sync()
        self.assertIn('index.html', diff['upload']['new_files'])
        self.assertIn('index.html', all_bucket_keys(b))

        conf = '''
[aws]
region_name = 'eu-west-1'
s3_bucket_name = 'www.example.com'
s3_project_root = ''
'''
        with tempfile.TemporaryDirectory() as tmpd:
            project_root = self.create_projdir_with_conf(
                'skeleton_proj_1.0', tmpd, conf)
            p = Project(project_root)
            diff, new_remote_cat = p.calculate_diff()
            p.sync()
        self.assertIn('index.html', diff['unchanged'])
        self.assertIn('index.html', all_bucket_keys(b))


class TestProjectMigrationFromCSVToSqlite(unittest.TestCase):

    @moto.mock_s3
    def test_normal_case_auto_migration(self):
        """
        If an on CSV type catalogue file exists, it should be replaced with the
        SQLite version on the next push
        """
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        project_root = os.path.join(MODULE_DIR, 'migration_fixture_proj_1')
        p = Project(project_root)
        p.sync()

        b = self.conn.Bucket('www.example.com')
        old_csv_p = os.path.join(
            MODULE_DIR, 'migration_fixture_proj_1.s3sup.catalogue.csv')
        with open(old_csv_p, 'rb') as old_csv_f:
            b.put_object(
                Key='.s3sup.catalogue.csv',
                ACL='private',
                Body=old_csv_f)
        b.Object('.s3sup.cat').delete()

        self.assertNotIn('.s3sup.cat', all_bucket_keys(b))
        self.assertIn('.s3sup.catalogue.csv', all_bucket_keys(b))

        project_root_n = os.path.join(MODULE_DIR, 'migration_fixture_proj_1.1')
        pn = Project(project_root_n)
        pn.sync()

        self.assertIn('.s3sup.cat', all_bucket_keys(b))
        self.assertIn('.s3sup.catalogue.csv', all_bucket_keys(b))
        self.assertIn('additional.txt', all_bucket_keys(b))

        o = b.Object('.s3sup.catalogue.csv')
        with tempfile.NamedTemporaryFile() as tf:
            o.download_fileobj(tf)
            tf.seek(0)
            with self.assertRaises(UnicodeDecodeError):
                print(tf.read().decode('utf-8'))

    @moto.mock_s3
    def test_migration_interrupted_both_formats_now_on_s3_old_ignored(self):
        """
        It's possible the migration was interrupted and now both the CSV and
        SQLite versions of the catalogue are now on S3. Need to make sure that
        the only the new one is used when building the remote catalogue and not
        the old one, which may be out of date.
        """
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(
            Bucket='www.example.com',
            CreateBucketConfiguration={'LocationConstraint': 'eu-west-1'})
        project_root = os.path.join(MODULE_DIR, 'migration_fixture_proj_1.1')
        p = Project(project_root)
        p.sync()

        b = self.conn.Bucket('www.example.com')
        old_csv_p = os.path.join(
            MODULE_DIR, 'migration_fixture_proj_1.s3sup.catalogue.csv')
        with open(old_csv_p, 'rb') as old_csv_f:
            b.put_object(
                Key='.s3sup.catalogue.csv',
                ACL='private',
                Body=old_csv_f)

        self.assertIn('.s3sup.cat', all_bucket_keys(b))
        self.assertIn('.s3sup.catalogue.csv', all_bucket_keys(b))

        project_root_n = os.path.join(MODULE_DIR, 'migration_fixture_proj_1.1')
        pn = Project(project_root_n)
        diff, new_remote_cat = pn.calculate_diff()
        self.assertEqual(0, diff['num_changes'])


if __name__ == '__main__':
    unittest.main()
