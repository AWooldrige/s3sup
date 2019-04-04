import csv
import enum
import collections
import copy
import click
import inflect


class ChangeReason(enum.Enum):
    NEW_FILE = 1
    CONTENT_CHANGED = 2
    ATTRIBUTES_CHANGED = 3
    DELETED = 4
    DELETED_PROTECTED = 5
    NO_CHANGE = 6


CR_STYLE = collections.namedtuple(
    'CR_STYLE', ['colour', 'symbol', 'shortreason', 'longreason'])

CR_STYLES = {
    ChangeReason['NEW_FILE']: CR_STYLE('yellow', '+', 'new', 'new'),
    ChangeReason['CONTENT_CHANGED']: CR_STYLE(
        'blue', '*', 'changed', 'content changed'),
    ChangeReason['ATTRIBUTES_CHANGED']: CR_STYLE(
        'cyan', '~', 'attrs', 'attributes changed'),
    ChangeReason['DELETED']: CR_STYLE('red', '-', 'delete', 'deleted'),
    ChangeReason['DELETED_PROTECTED']: CR_STYLE(
        'green', '^', 'deleteprotected', 'deleted but protected'),
    ChangeReason['NO_CHANGE']: CR_STYLE('green', '^', 'unchanged', 'unchanged')
}


class Catalogue:

    def __init__(self, preserve_deleted_files=False):
        self._c = {}
        self._preserve_deleted_files = preserve_deleted_files

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
        # TODO: Not a great use of memory, see if there's a better way.
        new_rmt = copy.deepcopy(self)

        changes = {
            'num_changes': 0,
            'upload': {
                'new_files': [],
                'content_changed': [],
                'attributes_changed': []
            },
            'delete': [],
            'delete_protected': [],
            'unchanged': []
        }

        for path, (content_hash, attributes_hash) in rmt.items():
            if path not in lcl:
                if self._preserve_deleted_files:
                    changes['delete_protected'].append(path)
                    # Deleted but protected files are the only ones that need
                    # to be maintained in remote
                    new_rmt.add_file(path, content_hash, attributes_hash)
                else:
                    changes['delete'].append(path)

        for path, (content_hash, attributes_hash) in lcl.items():
            try:
                r_content_hash, r_attributes_hash = rmt[path]
                if content_hash != r_content_hash:
                    changes['upload']['content_changed'].append(path)
                elif attributes_hash != r_attributes_hash:
                    changes['upload']['attributes_changed'].append(path)
                else:
                    changes['unchanged'].append(path)
            except KeyError:
                changes['upload']['new_files'].append(path)

        changes['num_changes'] = (
            len(changes['delete'])
            + len(changes['upload']['new_files'])
            + len(changes['upload']['content_changed'])
            + len(changes['upload']['attributes_changed'])
        )
        return changes, new_rmt


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
    _p(dd['delete_protected'], 'DELETED_PROTECTED')
    _p(dd['unchanged'], 'NO_CHANGE')


def change_list(diff):
    """
    Paths that need changes made on S3, along with the reason.

    Changes should be made in the order returned, in an attempt to prevent the
    temporary period where there may be incorrect links between HTML files and
    static assets that haven't been uploaded yet.
    """
    # Attribute changes first, less risk of content changes.
    dl = [(ChangeReason.ATTRIBUTES_CHANGED, p)
          for p in diff['upload']['attributes_changed']]
    # TODO: Upload in order: others, CSS, JS, HTML
    dl += [(ChangeReason.NEW_FILE, p)
           for p in diff['upload']['new_files']]
    # TODO: Upload in same order as above
    dl += [(ChangeReason.CONTENT_CHANGED, p)
           for p in diff['upload']['content_changed']]
    dl += [(ChangeReason.DELETED, p)
           for p in diff['delete']]
    return dl
