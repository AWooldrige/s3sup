import csv
import enum
import collections
import click
import inflect


class ChangeReason(enum.Enum):
    NEW_FILE = 1
    CONTENT_CHANGED = 2
    ATTRIBUTES_CHANGED = 3
    DELETED = 4
    NO_CHANGE = 5


CR_STYLE = collections.namedtuple(
    'CR_STYLE', ['colour', 'symbol', 'shortreason', 'longreason'])

CR_STYLES = {
    ChangeReason['NEW_FILE']: CR_STYLE('yellow', '+', 'new', 'new'),
    ChangeReason['CONTENT_CHANGED']: CR_STYLE(
        'blue', '*', 'changed', 'content changed'),
    ChangeReason['ATTRIBUTES_CHANGED']: CR_STYLE(
        'cyan', '~', 'attrs', 'attributes changed'),
    ChangeReason['DELETED']: CR_STYLE('red', '-', 'delete', 'deleted'),
    ChangeReason['NO_CHANGE']: CR_STYLE('green', '^', 'unchanged', 'unchanged')
}


class Catalogue:

    def __init__(self):
        self._c = {}

    def add_file(self, path: str, content_hash: str, attributes_hash: str):
        self._c[path] = (str(content_hash), str(attributes_hash))
        return self

    def to_dict(self):
        return {k: self._c[k] for k in sorted(self._c.keys())}

    def from_csv(self, path: str):
        with open(path, 'rt', newline='') as f:
            reader = csv.reader(f)
            next(reader)  # Skip CSV header
            for path, content_hash, attributes_hash in csv.reader(f):
                self.add_file(path, content_hash, attributes_hash)

    def to_csv(self, path: str):
        with open(path, 'wt', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['path', 'content_hash', 'attributes_hash'])
            for path, (content_hsh, attributes_hsh) in self.to_dict().items():
                writer.writerow([path, content_hsh, attributes_hsh])

    def diff_dict(self, remote_catalogue):
        lcl = self.to_dict()
        rmt = remote_catalogue.to_dict()

        changes = {
            'num_changes': 0,
            'upload': {
                'new_files': [],
                'content_changed': [],
                'attributes_changed': []
            },
            'delete': [pth for pth in rmt if pth not in lcl],
            'unchanged': []
        }
        changes['num_changes'] += len(changes['delete'])

        for path, (content_hash, attributes_hash) in lcl.items():
            try:
                r_content_hash, r_attributes_hash = rmt[path]
                if content_hash != r_content_hash:
                    changes['upload']['content_changed'].append(path)
                    changes['num_changes'] += 1
                elif attributes_hash != r_attributes_hash:
                    changes['upload']['attributes_changed'].append(path)
                    changes['num_changes'] += 1
                else:
                    changes['unchanged'].append(path)
            except KeyError:
                changes['upload']['new_files'].append(path)
                changes['num_changes'] += 1

        return changes


def print_diff_summary(dd, verbose=False):
    ie = inflect.engine()
    nc = dd['num_changes']
    if nc <= 0:
        click.echo('No local changes to be synced.')
        return

    if verbose:
        click.echo('Local changes to be synced to S3:')
    else:
        click.echo('Summary of local changes to be synced to S3:')

    def _p(files, change_reason):
        num_files = len(files)
        if num_files <= 0:
            return
        crs = CR_STYLES[ChangeReason[change_reason]]
        cr_prefix = click.style(
            '{symbol} {changereason}'.format(
                symbol=getattr(crs, 'symbol'),
                changereason=getattr(crs, 'longreason')),
            fg=getattr(crs, 'colour'))
        files_txt = '{0} {1}'.format(num_files, ie.plural('file', num_files))
        click.echo(' {cr_prefix}: {files_txt}'.format(
            cr_prefix=cr_prefix,
            files_txt=files_txt))

        if not verbose or change_reason == 'NO_CHANGE':
            return

        change_symbol = click.style(
            '{symbol}'.format(symbol=getattr(crs, 'symbol')),
            fg=getattr(crs, 'colour'))

        for p in files:
            click.echo('   {0} {1}'.format(change_symbol, p))

    _p(dd['upload']['new_files'], 'NEW_FILE')
    _p(dd['upload']['content_changed'], 'CONTENT_CHANGED')
    _p(dd['upload']['attributes_changed'], 'ATTRIBUTES_CHANGED')
    _p(dd['delete'], 'DELETED')
    _p(dd['unchanged'], 'NO_CHANGE')


def change_list(diff):
    """
    Return only paths that need changing, in a list with format:
    TODO
    """
    dl = [(ChangeReason.NEW_FILE, p)
          for p in diff['upload']['new_files']]
    dl += [(ChangeReason.CONTENT_CHANGED, p)
           for p in diff['upload']['content_changed']]
    dl += [(ChangeReason.ATTRIBUTES_CHANGED, p)
           for p in diff['upload']['attributes_changed']]
    dl += [(ChangeReason.ATTRIBUTES_CHANGED, p)
           for p in diff['upload']['attributes_changed']]
    dl += [(ChangeReason.DELETED, p)
           for p in diff['delete']]
    return dl
