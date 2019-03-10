import click


def pprint_h1(text):
    click.echo('*'*60)
    click.echo('* {0}'.format(text))
    click.echo('*'*60)


def pprint_h2(text):
    click.echo('* {0}'.format(text))
    click.echo('*'*60)


def pprint_h3(text):
    click.echo('{0}'.format(text))
    click.echo('*'*len(text))


def pprint_dict(d, level=0, level_name=None):
    try:
        iterator = d.items()
        if level_name is not None:
            click.echo('  '*level + '- {0}:'.format(level_name))
        for k, v in iterator:
            pprint_dict(v, level=level+1, level_name=k)
    except AttributeError:
        click.echo('  '*level + '- {0}: {1}'.format(
            level_name,
            click.style(str(d), fg='green')))
