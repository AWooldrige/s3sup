import os
import sys
import functools
import click
import pathlib

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import s3sup.project  # noqa: E402
import s3sup.catalogue  # noqa: E402

SKELETON_TOML = """
###############################################################################
# GLOBAL SETTINGS
###############################################################################
# preserve_deleted_files = false   # Prevent S3 files being deleted
# charset = 'utf-8'   # Specify default character encoding for text files

###############################################################################
# AWS SETTINGS
###############################################################################

[aws]
region_name = ''  # E.g. 'eu-west-1'
s3_bucket_name = '' # E.g. 'mys3websitebucketname'
s3_project_root = ''  # Root location for project within S3, e.g. 'staging/'


###############################################################################
# PATH SPECIFIC SETTINGS
#
# If multiple [[path_specific]] entries match a path:
#  * Directives are combined from all matching [[path_specific]] entries.
#  * The last matching [[path_specific]] wins for equivalent directive keys.
###############################################################################

# Catch-all matcher for all files. Set a sensible default cache lifetime.
[[path_specific]]
path = '^.*$'
Cache-Control = 'max-age=60'

# Example: extend cache lifetime for certain PDFs and set additional headers
# [[path_specific]]
# path = '^recipedownload/[0-9]+.pdf'
# Content-Disposition = 'attachment'
# Cache-Control = 'max-age=120'


###############################################################################
# MIMETYPE OVERRIDES
###############################################################################

# Override file extension -> mimetype mappings
# [mimetype_overrides]
# '.woff2' = 'font/woff2'
"""


def common_options(f):
    """
    Common command line options used by ALL s3sup commands
    """
    options = [
        click.option(
            '-p', '--projectdir', default='.',
            help='Local s3sup project directory, containing s3sup.toml.'),
        click.option(
            '-v', '--verbose', is_flag=True,
            help='Output running commentary.')
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)


def options_for_remotes(f):
    """
    Command line options only used by s3sup commands that compare with the
    remote S3 catalogue. E.g. upload and status.
    """
    options = [
        click.option(
            '-d', '--dryrun', is_flag=True,
            help='Simulate changes to be made. Do not modify files on S3.'),
        click.option(
            '-n', '--nodelete', is_flag=True,
            help='Do not delete any files on S3, add/modify operations only.')
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)


# Would rather add options to click.group(), but this doesn't work as intended:
# https://stackoverflow.com/questions/52144383/
@click.group()
def cli():
    """
    s3sup - Amazon S3 static site uploader
    """
    pass


@cli.command()
@common_options
def init(projectdir, verbose):
    """
    Create a skeleton s3sup.toml configuration file.
    """
    # Check file doesn't already exist
    cf = pathlib.Path(os.path.join(projectdir, 's3sup.toml'))
    if cf.exists():
        raise click.FileError(
            's3sup.toml', hint='s3sup configuration file already exists')
    cf.write_text(SKELETON_TOML)
    click.echo('Skeleton configuration file created: {0}'.format(
        cf.absolute()))


@cli.command()
@common_options
@options_for_remotes
def status(projectdir, verbose, dryrun, nodelete):
    """
    Show S3 changes required. Read-only.
    """
    click.echo('S3 site uploader. Using:')
    p = s3sup.project.Project(
        projectdir, dryrun=dryrun, preserve_deleted_files=nodelete,
        verbose=verbose)
    if verbose or projectdir != '.':
        click.echo(' * Local project directory: {0}'.format(projectdir))

    try:
        s3_root = p.rules['aws']['s3_project_root'].strip()
    except KeyError:
        s3_root = '/'
    s3_root = '/' if s3_root == '' else s3_root

    if s3_root != '/':
        s3_root = '/{0}/'.format(s3_root.lstrip('/').rstrip('/'))

    if verbose:
        click.echo(' * AWS region: {0}'.format(p.rules['aws']['region_name']))

    click.echo(' * S3 bucket: {0}{1}'.format(
        p.rules['aws']['s3_bucket_name'], s3_root))

    click.echo('')
    diff, _ = p.calculate_diff()
    s3sup.catalogue.print_diff_summary(diff, verbose=True)


@cli.command()
@click.argument('local_file', nargs=-1)
@common_options
def inspect(local_file, projectdir, verbose):
    """
    Show calculated attributes (e.g. headers) before upload.
    """
    p = s3sup.project.Project(projectdir, dryrun=True, verbose=verbose)
    p.print_summary()
    for f in local_file:
        click.echo()
        try:
            fp = p.file_prepper_wrapped(f)
            fp.print_summary()
        except FileNotFoundError:
            msg = 'Could not open: {0}'.format(click.format_filename(f))
            click.echo(click.style(msg, fg='red'), err=True)


@cli.command()
@common_options
@options_for_remotes
def upload(projectdir, verbose, dryrun, nodelete):
    """
    Synchronise local static site to S3.

    Use --dryrun to test behaviour without changes actually being made to S3.
    Or use "s3sup status".
    """
    click.echo('See mee?', err=True)
    p = s3sup.project.Project(
        projectdir, dryrun=dryrun, preserve_deleted_files=nodelete,
        verbose=verbose)
    diff, _ = p.calculate_diff()
    s3sup.catalogue.print_diff_summary(diff, verbose=verbose)
    p.sync()
    click.echo(click.style('Done!', fg='green'))


if __name__ == '__main__':
    cli()
