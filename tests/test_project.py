import os
import tempfile
import unittest

import boto3
import botocore
import moto

from s3sup.project import Project

MODULE_DIR = os.path.dirname(os.path.abspath(__file__))

os.environ['AWS_ACCESS_KEY_ID'] = 'FOO'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'BAR'


class TestProject(unittest.TestCase):

    @moto.mock_s3
    def test_fixture_proj_1(self):
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.build_catalogue()

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
        conn.create_bucket(Bucket='www.test.com')

        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.build_remote_catalogue()
        self.assertEqual({}, cat.to_dict())

    @moto.mock_s3
    def test_build_existing_catalogue(self):
        conn = boto3.resource('s3', region_name='eu-west-1')
        conn.create_bucket(Bucket='www.test.com')
        b = conn.Bucket('www.test.com')
        exp_csv_p = os.path.join(
            MODULE_DIR, 'expected_cat_fixture_proj_1.csv')
        with open(exp_csv_p, 'rb') as exp_csv_f:
            b.put_object(
                Key='staging/.s3sup.catalogue.csv',
                ACL='private',
                Body=exp_csv_f)
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        cat = p.build_remote_catalogue()
        self.assertTrue('assets/logo.svg' in cat.to_dict())


class TestProjectSyncNoChanges(unittest.TestCase):

    @moto.mock_s3
    def test_no_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.test.com')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        p.sync()

        project_root_n = os.path.join(MODULE_DIR, 'fixture_proj_1')
        pn = Project(project_root_n)
        pn.sync()

        b = self.conn.Bucket('www.test.com')
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
    def test_multiple_project_changes(self):
        self.conn = boto3.resource('s3', region_name='eu-west-1')
        self.conn.create_bucket(Bucket='www.test.com')
        project_root = os.path.join(MODULE_DIR, 'fixture_proj_1')
        p = Project(project_root)
        p.sync()

        project_root_n = os.path.join(MODULE_DIR, 'fixture_proj_1.1')
        pn = Project(project_root_n)
        pn.sync()

        b = self.conn.Bucket('www.test.com')
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


if __name__ == '__main__':
    unittest.main()
