import os
import tempfile
import boto3
import botocore
import click
import time

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

    def _boto_bucket(self):
        s = boto3.session.Session()
        res_args = {}
        try:
            res_args['region_name'] = self.rules['aws']['region_name']
        except KeyError:
            pass
        try:
            res_args['endpoint_url'] = self.rules['aws']['s3_endpoint_url']
        except KeyError:
            pass
        r = s.resource(service_name='s3', **res_args)
        b = r.Bucket(self.rules['aws']['s3_bucket_name'])
        return b

    def _obj_path(self, rel_path):
        return s3sup.fileprepper.s3_path(
            self.rules['aws']['s3_project_root'], rel_path)

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
        b = self._boto_bucket()
        rmt_cat_path = self._obj_path('.s3sup.catalogue.csv')
        f = b.Object(rmt_cat_path)
        c = s3sup.catalogue.Catalogue()

        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        try:
            f.download_file(tmpp)
            c.from_csv(tmpp)
        except botocore.exceptions.NoCredentialsError:
            raise click.UsageError(
                'Cannot find AWS credentials.\n -> Configure AWS credentials '
                ' using any mthod that the underlying boto3 library supports:'
                '\n -> https://boto3.amazonaws.com/v1/documentation/'
                'api/latest/guide/configuration.html')
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
        changes = s3sup.catalogue.change_list(self.calculate_diff())

        if len(changes) <= 0:
            return changes

        if self.dryrun:
            click.echo(click.style(
                'Not making any changes as this is a dryrun.', fg='blue'))
            return changes

        b = self._boto_bucket()

        def _prepped_file_and_obj(path):
            fp = s3sup.fileprepper.FilePrepper(
                self.local_project_root, path, self.rules)
            o = b.Object(fp.s3_path())
            return (fp, o)

        def display_current(item):
            if item is None:
                return ''
            cr, p = item
            s3_path = s3sup.fileprepper.s3_path(
                self.rules['aws']['s3_project_root'], p)

            crs = s3sup.catalogue.CR_STYLES[cr]
            change_symbol = click.style(
                '{symbol}'.format(symbol=getattr(crs, 'symbol')),
                fg=getattr(crs, 'colour'))

            return ' {0} {1}'.format(change_symbol, s3_path)

        with click.progressbar(changes, label='Syncing to S3',
                               item_show_func=display_current) as bar:
            for cr, p in bar:
                fp, o = _prepped_file_and_obj(p)
                if cr == s3sup.catalogue.ChangeReason['NEW_FILE']:
                    with fp.content_fileobj() as lf:
                        o.put(Body=lf, **fp.attributes_as_boto_args())

                if cr == s3sup.catalogue.ChangeReason['CONTENT_CHANGED']:
                    with fp.content_fileobj() as lf:
                        o.put(Body=lf, **fp.attributes_as_boto_args())

                if cr == s3sup.catalogue.ChangeReason['ATTRIBUTES_CHANGED']:
                    o.copy_from(
                        CopySource={
                            'Bucket': self.rules['aws']['s3_bucket_name'],
                            'Key': self._obj_path(p)},
                        MetadataDirective='REPLACE',
                        TaggingDirective='REPLACE',
                        **fp.attributes_as_boto_args())

                if cr == s3sup.catalogue.ChangeReason['DELETED']:
                    o.delete()

        c = self.build_catalogue()
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        c.to_csv(tmpp)
        o = b.Object(self._obj_path('.s3sup.catalogue.csv'))
        with open(tmpp, 'rb') as lf:
            o.put(Body=lf, ACL='private')
        os.remove(tmpp)
        return changes
