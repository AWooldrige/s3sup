import os
import functools
import tempfile
import pkgutil

import boto3
import botocore
import click
import humanize

import s3sup.catalogue
import s3sup.fileprepper
import s3sup.rules
import s3sup.utils


def load_skeleton_s3sup_toml():
    return pkgutil.get_data(__package__, 'skeleton.s3sup.toml')


class Project:

    def __init__(self, local_project_root, dryrun=False,
                 preserve_deleted_files=False, verbose=True):
        self.dryrun = dryrun
        self.verbose = verbose
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

        self._preserve_deleted_files = preserve_deleted_files
        try:
            self._preserve_deleted_files = (
                preserve_deleted_files or self.rules['preserve_deleted_files'])
        except KeyError:
            pass

        self._fp_cache = {}
        self.local_preflight_checks()

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
        return r, b

    def file_prepper_wrapped(self, path):
        try:
            return self._fp_cache[path]
        except KeyError:
            self._fp_cache[path] = s3sup.fileprepper.FilePrepper(
                self.local_project_root, path, self.rules)
        return self._fp_cache[path]

    def _local_fs_path(self, rel_path):
        return os.path.join(self.local_project_root, rel_path)

    def local_preflight_checks(self):
        """
        Can't stop things going wrong during the upload, but having a good poke
        round catches most problems.
        """
        return True

    def remote_preflight_checks(self):
        """
        Can't stop things going wrong during the upload, but having a good poke
        round catches most problems.
        """
        rmt_cat_fp = self.file_prepper_wrapped('.s3sup.write_test')
        rsrc, b = self._boto_bucket()
        o = b.Object(rmt_cat_fp.s3_path())
        try:
            o.put(Body='Can s3sup write to bucket?', ACL='private')
        except rsrc.meta.client.exceptions.NoSuchBucket:
            raise click.ClickException('S3 bucket does not exist: {0}'.format(
                self.rules['aws']['s3_bucket_name']))
        o.delete()

    @functools.lru_cache(maxsize=8)
    def local_catalogue(self):
        local_cat = s3sup.catalogue.Catalogue(
            preserve_deleted_files=self._preserve_deleted_files)
        for root, dirs, files in os.walk(self.local_project_root):
            for f in files:
                if f == 's3sup.toml':
                    continue
                abs_path = os.path.join(root, f)
                rel_path = os.path.relpath(
                    abs_path, start=self.local_project_root)
                fp = self.file_prepper_wrapped(rel_path)
                local_cat.add_file(
                    rel_path, fp.content_hash(), fp.attributes_hash())
        return local_cat

    @functools.lru_cache(maxsize=8)
    def get_remote_catalogue(self):
        remote_cat = s3sup.catalogue.Catalogue(
            preserve_deleted_files=self._preserve_deleted_files)

        _, b = self._boto_bucket()
        old_cat_fp = self.file_prepper_wrapped('.s3sup.catalogue.csv')
        old_f = b.Object(old_cat_fp.s3_path())

        new_cat_fp = self.file_prepper_wrapped('.s3sup.cat')
        new_f = b.Object(new_cat_fp.s3_path())

        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        try:
            new_f.download_file(tmpp)
            remote_cat.from_sqlite(tmpp)
        except botocore.exceptions.NoCredentialsError:
            raise click.UsageError(
                'Cannot find AWS credentials.\n -> Configure AWS credentials '
                ' using any method that the underlying boto3 library supports:'
                '\n -> https://boto3.amazonaws.com/v1/documentation/'
                'api/latest/guide/configuration.html')
        except botocore.exceptions.ClientError:
            if self.verbose:
                click.echo(
                    ('Could not find SQLite based remote catalogue on S3 '
                     '(expected at {0}).').format(new_cat_fp.s3_path()))
            try:
                old_f.download_file(tmpp)
                remote_cat.from_csv(tmpp)
                click.echo(click.style((
                    'WARNING: After the next s3sup push, do not attempt to '
                    'use older versions of s3sup (0.3.0 or below) with this '
                    'project, as they will no longer be able to read the '
                    'remote catalogue.'), fg='blue'))
            except botocore.exceptions.ClientError:
                if self.verbose:
                    click.echo(
                        ('Could not find older CSV based remote catalogue on '
                         'S3 either (expected at {0}). This indicates the '
                         'project has never been pushed to S3 before.').format(
                            old_cat_fp.s3_path()))
                pass
            pass
        os.remove(tmpp)
        return remote_cat

    def write_remote_catalogue(self, catalogue):
        hndl, tmpp = tempfile.mkstemp()
        os.close(hndl)
        catalogue.to_sqlite(tmpp)
        rmt_cat_fp = self.file_prepper_wrapped('.s3sup.cat')
        _, b = self._boto_bucket()
        o = b.Object(rmt_cat_fp.s3_path())
        with open(tmpp, 'rb') as lf:
            o.put(Body=lf, ACL='private')
        os.remove(tmpp)

        # Deliberately break older s3sup clients <= 0.3.0.
        # This file even needs uploading even for projects that have never used
        # the old format, just in-case an old version of s3sup is used on it
        # in the future (perhaps if part of a CI/CD system is used).
        old_rmt_cat_fp = self.file_prepper_wrapped('.s3sup.catalogue.csv')
        the_breaker = (
            b'\xF9\xF9This is a deliberately corrupt old version of the s3sup '
            b'catalogue format It is not used any more and this file is only '
            b'here to cause s3sup clients <= 0.3.0 to fail, rather than have '
            b'them try to upload everything again.')
        b.Object(old_rmt_cat_fp.s3_path()).put(Body=the_breaker, ACL='private')

    def calculate_diff(self):
        local_cat = self.local_catalogue()
        remote_cat = self.get_remote_catalogue()
        diff, new_remote_cat = local_cat.diff_dict(remote_cat)
        return (diff, new_remote_cat)

    def sync(self):
        self.remote_preflight_checks()
        diff, new_remote_cat = self.calculate_diff()
        changes = s3sup.catalogue.change_list(diff)
        changes_with_prep = [
            (cr, p, self.file_prepper_wrapped(p)) for cr, p in changes]

        if len(changes) <= 0:
            return changes

        if self.dryrun:
            click.echo(click.style(
                'Not making any changes as this is a dry run.', fg='blue'))
            return changes

        _, b = self._boto_bucket()

        def display_current(item):
            if item is None:
                return ''
            cr, p, fp = item
            crs = s3sup.catalogue.CR_STYLES[cr]
            change_symbol = click.style(
                '{symbol}'.format(symbol=getattr(crs, 'symbol')),
                fg=getattr(crs, 'colour'))

            cur = ' {0} {1}'.format(change_symbol, fp.s3_path())
            if (cr == s3sup.catalogue.ChangeReason['NEW_FILE'] or
                    cr == s3sup.catalogue.ChangeReason['CONTENT_CHANGED']):
                cur += ' ({0})'.format(humanize.naturalsize(fp.size()))
            return cur

        with click.progressbar(changes_with_prep, label='Syncing to S3',
                               item_show_func=display_current) as bar:
            for cr, p, fp in bar:
                o = b.Object(fp.s3_path())
                if cr == s3sup.catalogue.ChangeReason['NEW_FILE']:
                    with fp.content_fileobj() as lf:
                        o.put(Body=lf, **fp.attributes_as_boto_args())
                elif cr == s3sup.catalogue.ChangeReason['CONTENT_CHANGED']:
                    with fp.content_fileobj() as lf:
                        o.put(Body=lf, **fp.attributes_as_boto_args())
                elif cr == s3sup.catalogue.ChangeReason['ATTRIBUTES_CHANGED']:
                    o.copy_from(
                        CopySource={
                            'Bucket': self.rules['aws']['s3_bucket_name'],
                            'Key': fp.s3_path()},
                        MetadataDirective='REPLACE',
                        TaggingDirective='REPLACE',
                        **fp.attributes_as_boto_args())
                elif cr == s3sup.catalogue.ChangeReason['DELETED']:
                    o.delete()
                else:
                    raise Exception('Unknown ChangeReason: {0}'.format(cr))

        self.write_remote_catalogue(new_remote_cat)
        return changes

    def print_summary(self):
        lcl_dir = click.format_filename(self.local_project_root)
        if lcl_dir == '.':
            lcl_dir += ' (current dir)'

        s3p = 's3://{0}/'.format(self.rules['aws']['s3_bucket_name'])
        try:
            s3p += self.rules['aws']['s3_project_root'].lstrip('/').rstrip('/')
        except KeyError:
            pass

        to_print = {
            'Local project dir': lcl_dir,
            'AWS region': self.rules['aws']['region_name'],
            'S3 bucket': s3p
        }
        s3sup.utils.pprint_h1('PROJECT INFORMATION')
        s3sup.utils.pprint_dict(to_print)
