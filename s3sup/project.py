import os
import tempfile
import boto3
import botocore
import click

import s3sup.catalogue
import s3sup.fileprepper
import s3sup.rules


class Project:

    def __init__(self, local_project_root, dryrun=False):
        self.dryrun = dryrun
        self.local_project_root = local_project_root
        try:
            self.rules = s3sup.rules.load_rules(os.path.join(
                local_project_root, 's3sup.toml'))
        except FileNotFoundError:
            error_text = (
                '\n{0} not an s3sup project directory (no s3sup.toml found). '
                'Either:\n'
                ' * Change to an s3sup project directory before running.\n'
                ' * Supply project directory using -p/--projectdir.\n'
                ' * Create a new s3sup project direction using "s3sup init".'
            ).format(os.path.abspath(local_project_root))
            raise click.FileError(
                os.path.join(local_project_root, 's3sup.toml'),
                hint=error_text)

    def _boto_session(self):
        args = {}
        try:
            args['region_name'] = self.rules['aws']['region_name']
        except KeyError:
            pass
        return boto3.session.Session(**args)

    def _obj_path(self, rel_path):
        pr = self.rules['aws']['s3_project_root']
        if pr.endswith('/'):
            return '{0}{1}'.format(pr, rel_path)
        return '{0}/{1}'.format(pr, rel_path)

    def _local_fs_path(self, rel_path):
        return os.path.join(self.local_project_root, rel_path)

    def build_catalogue(self):
        c = s3sup.catalogue.Catalogue()
        for root, dirs, files in os.walk(self.local_project_root):
            for f in files:
                if f == 's3sup.toml':
                    continue
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(
                    abs_path, start=self.local_project_root)
                fp = s3sup.fileprepper.FilePrepper(
                    self.local_project_root, rel_path, self.rules)
                c.add_file(rel_path, fp.content_hash(), fp.attributes_hash())
        return c

    def build_remote_catalogue(self):
        s = self._boto_session()
        r = s.resource('s3')
        b = r.Bucket(self.rules['aws']['s3_bucket_name'])
        rmt_cat_path = self._obj_path('.s3sup.catalogue.csv')
        f = b.Object(rmt_cat_path)

        c = s3sup.catalogue.Catalogue()

        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        try:
            f.download_file(tmpp)
            c.from_csv(tmpp)
        except botocore.exceptions.ClientError:
            click.echo('Project not uploaded before (no {0} on S3).'.format(
                rmt_cat_path))
            pass
        os.remove(tmpp)
        return c

    def calculate_diff(self):
        try:
            return self._diff
        except AttributeError:
            pass
        local_cat = self.build_catalogue()
        remote_cat = self.build_remote_catalogue()
        self._diff = local_cat.diff_dict(remote_cat)
        return self._diff

    def sync(self):
        changes = self.calculate_diff()

        if changes['num_changes'] <= 0:
            click.echo('Local and remote project up-to-date')
            return changes

        if self.dryrun:
            click.echo(click.style(
                'Not making any changes as this is a dryrun.', fg='blue'))
            return changes

        s = self._boto_session()
        r = s.resource('s3')
        b = r.Bucket(self.rules['aws']['s3_bucket_name'])

        def _prepped_file_and_obj(path):
            fp = s3sup.fileprepper.FilePrepper(
                self.local_project_root, p, self.rules)
            o = b.Object(self._obj_path(p))
            return (fp, o)

        for p in changes['upload']['new_files']:
            click.echo('Uploading new file: {0}'.format(p))
            fp, o = _prepped_file_and_obj(p)
            with fp.content_fileobj() as lf:
                o.put(Body=lf, **fp.attributes_as_boto_args())

        for p in changes['upload']['content_changed']:
            click.echo('Uploading as content changed: {0}'.format(p))
            fp, o = _prepped_file_and_obj(p)
            with fp.content_fileobj() as lf:
                o.put(Body=lf, **fp.attributes_as_boto_args())

        for p in changes['upload']['attributes_changed']:
            click.echo('Changing attributes: {0}'.format(p))
            fp, o = _prepped_file_and_obj(p)
            o.copy_from(
                CopySource={
                    'Bucket': self.rules['aws']['s3_bucket_name'],
                    'Key': self._obj_path(p)},
                MetadataDirective='REPLACE',
                TaggingDirective='REPLACE',
                **fp.attributes_as_boto_args())

        for p in changes['delete']:
            click.echo('Deleting: {0}'.format(p))
            fp, o = _prepped_file_and_obj(p)
            o.delete()

        click.echo('Updating remote catalogue')
        c = self.build_catalogue()
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        c.to_csv(tmpp)
        o = b.Object(self._obj_path('.s3sup.catalogue.csv'))
        with open(tmpp, 'rb') as lf:
            o.put(Body=lf, ACL='private')
        os.remove(tmpp)
        return changes
