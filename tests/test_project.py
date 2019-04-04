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
    def test_fixture_proj_1(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.local_catalogue()

        hndl, tmp_path = tempfile.mkstemp()
        cat.to_csv(tmp_path)

        exp_csv_p = os.path.join(
            MODULE_DIR, 'expected_cat_fixture_proj_1.csv')
        with open(tmp_path, 'rt') as cat_csv_f:
            cat_csv = cat_csv_f.read()
        with open(exp_csv_p, 'rt') as exp_csv_f:
            exp_csv = exp_csv_f.read()
        self.maxDiff = None
        self.assertEqual(exp_csv, cat_csv)

    @moto.mock_s3
    def test_build_non_existant_remote_catalogue(self):
        conn = boto3.resource('s3', region_name='eu-west-1')
        conn.create_bucket(Bucket='www.example.com')

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.get_remote_catalogue()
        self.assertEqual({}, cat.to_dict())

    @moto.mock_s3
    def test_build_existing_catalogue(self):
        conn = boto3.resource('s3', region_name='eu-west-1')
        conn.create_bucket(Bucket='www.example.com')
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
        self.conn.create_bucket(Bucket='www.example.com')
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
        self.conn.create_bucket(Bucket='www.example.com')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_2_minimal')
        p = Project(project_root)
        p.sync()

        b = self.conn.Bucket('www.example.com')
        o = b.Object('index.html')
        self.assertInObj('I like it minimal.', o)

    @moto.mock_s3
    def test_multiple_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.example.com')
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
        b = self.conn.create_bucket(Bucket='www.example.com')
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


if __name__ == '__main__':
    unittest.main()
