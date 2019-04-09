import os
import sys
import functools
import click
import pathlib

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
import s3sup.project  # noqa: E402
import s3sup.catalogue  # noqa: E402


def common_options(f):
    """
    Common command line options used by ALL s3sup commands
    """
    options = [
        click.option(
            '-p', '--projectdir', default='.',
            help=('Specify local s3sup static site directory (containing '
                  's3sup.toml). By default the current directory is used.')),
        click.option(
            '-v', '--verbose', is_flag=True,
            help='Output more informational messages than normal.')
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)


def options_for_remotes(f):
    """
    Command line options only used by s3sup commands that interact with S3.
    E.g. push and status.
    """
    options = [
        click.option(
            '-d', '--dryrun', is_flag=True,
            help='Simulate changes to be made. Do not modify files on S3.'),
        click.option(
            '-n', '--nodelete', is_flag=True,
            help=('Do not delete any files on S3, add/modify operations only. '
                  'Alternatively set "preserve_deleted_files" '
                  'in s3sup.toml.')),
    ]
    return functools.reduce(lambda x, opt: opt(x), options, f)


class AliasedGroup(click.Group):
    """
    Provides shortcut commands, allowing 'st' to be typed for 'status'.
    Skeleton class taken straight from the click documentation.
    """

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        commands = self.list_commands(ctx)
        aliases = {
            'upload': 'push',
            'sync': 'push'
        }
        all_commands = commands + [alias for alias in aliases]
        matches = [x for x in all_commands if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            try:
                match = aliases[matches[0]]
            except KeyError:
                match = matches[0]
            return click.Group.get_command(self, ctx, match)
        ctx.fail('Multiple commands matched "{0}": {1}'.format(
            cmd_name, ', '.join(sorted(matches))))


# Would rather add options to click.group(), but this doesn't work as intended:
# https://stackoverflow.com/questions/52144383/
@click.command(cls=AliasedGroup)
def cli():
    """
    s3sup - Amazon S3 static site uploader
    """
    pass


@cli.command()
@common_options
def init(projectdir, verbose):
    """
    Create a skeleton s3sup.toml in the current directory.
    """
    # Check file doesn't already exist
    cf = pathlib.Path(os.path.join(projectdir, 's3sup.toml'))
    if cf.exists():
        raise click.FileError(
            's3sup.toml', hint='s3sup configuration file already exists')
    cf.write_bytes(s3sup.project.load_skeleton_s3sup_toml())
    click.echo('Skeleton configuration file created: {0}'.format(
        cf.absolute()))


@cli.command()
@common_options
@options_for_remotes
def status(projectdir, verbose, dryrun, nodelete):
    """
    Show S3 changes that will be made on next push.
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
    Show calculated metadata for individual files.
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
def push(projectdir, verbose, dryrun, nodelete):
    """
    Synchronise local static site to S3.

    Use --dryrun to test behaviour without changes actually being made to S3.
    Or use "s3sup status".

    This command has two other aliases: upload or sync.
    """
    p = s3sup.project.Project(
        projectdir, dryrun=dryrun, preserve_deleted_files=nodelete,
        verbose=verbose)
    diff, _ = p.calculate_diff()
    s3sup.catalogue.print_diff_summary(diff, verbose=verbose)
    p.sync()
    click.echo(click.style('Done!', fg='green'))


if __name__ == '__main__':
    cli()
