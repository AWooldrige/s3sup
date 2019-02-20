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
# AWS SETTINGS
###############################################################################

[aws]
region_name = ''  # E.g. 'eu-west-1'
s3_bucket_name = '' # E.g. 'mys3websitebucketname'
s3_project_root = '/'  # Root location for project within S3, e.g. '/staging/'


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
# path= '^recipedownload/[0-9]+.pdf'
# Content-Disposition = 'attachment'
# Cache-Control = 'max-age=120'


###############################################################################
# OTHER SETTINGS
###############################################################################

# Override file extension -> mimetype mappings
# [mimetype_overrides]
# '.woff2' = 'font/woff2'
"""


def common_options(f):
    options = [
        click.option(
            '-p', '--projectdir', default='.',
            help='Local s3sup project directory, containing s3sup.toml.'),
        click.option(
            '-v', '--verbose', is_flag=True,
            help='Output running commentary.')
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
def status(projectdir, verbose):
    """
    Check what changes need to be made to get local static site in sync with
    the S3 copy.

    This command is read-only and will not make any changes to S3.
    """
    # Shouldn't be calling anything that needs dryrun, but just to be safe!
    p = s3sup.project.Project(projectdir, dryrun=True)
    diff = p.calculate_diff()
    click.echo('{0} changes from S3 catalogue:'.format(diff['num_changes']))
    s3sup.catalogue.print_diff_dict(diff)


@cli.command()
@common_options
@click.option(
    '-d', '--dryrun', is_flag=True,
    help='Simulate changes to be made. Don\'t modify files on S3.')
def upload(projectdir, verbose, dryrun):
    """
    Synchronise local static site to S3.

    Use --dryrun to test behaviour without changes actually being made to S3.
    Or use "s3sup status".
    """
    p = s3sup.project.Project(projectdir, dryrun=dryrun)
    diff = p.calculate_diff()
    click.echo('{0} changes required:'.format(diff['num_changes']))
    s3sup.catalogue.print_diff_dict(diff)
    p.sync()


if __name__ == '__main__':
    cli()
