import csv
import contextlib
import gzip
import sqlite3
import shutil
import tempfile
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

MAX_DB_SCHEMA_VERSION = 2


@contextlib.contextmanager
def load_gzipped_sqlite(path):
    with tempfile.NamedTemporaryFile() as out_f:
        with gzip.open(path, 'rb') as in_f:
            shutil.copyfileobj(in_f, out_f)
        c = sqlite3.connect(out_f.name)
        c.row_factory = sqlite3.Row
        yield c
        c.close()


@contextlib.contextmanager
def write_gzipped_sqlite(path):
    with tempfile.NamedTemporaryFile() as in_f:
        c = sqlite3.connect(in_f.name)
        c.row_factory = sqlite3.Row
        yield c
        c.commit()
        c.close()
        with gzip.open(path, 'wb') as out_f:
            shutil.copyfileobj(in_f, out_f)


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

    def from_sqlite(self, path: str):
        with load_gzipped_sqlite(path) as c:
            schema_version = c.execute('PRAGMA user_version').fetchone()[0]
            if schema_version > MAX_DB_SCHEMA_VERSION:
                raise click.ClickException((
                    'Upgrade to latest s3sup to continue. The s3sup version'
                    'last used to push this project to S3 was newer than the '
                    'installed version. The newer remote catalogue format is '
                    'not readable by older s3sup version. Catalogue schema is '
                    'version {0}, this s3sup only supports catalogue schema '
                    'up to version {1}.').format(
                        schema_version, MAX_DB_SCHEMA_VERSION))
            # Handle migrations here
            for row in c.execute('SELECT * FROM files'):
                self.add_file(
                    row['path'], row['content_hash'], row['attributes_hash'])

    def to_sqlite(self, path: str):
        with write_gzipped_sqlite(path) as c:
            c.execute('PRAGMA user_version = {v:d}'.format(
                v=MAX_DB_SCHEMA_VERSION))
            c.execute('''CREATE TABLE files (
                path TEXT,
                content_hash TEXT,
                attributes_hash TEXT)''')
            c.executemany(
                'INSERT INTO files VALUES (?, ?, ?)',
                [(path, ch, ah) for path, (ch, ah) in self.to_dict().items()])

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


def _order_for_upload(path_names):
    """
    Prevent HTML files referencing static assets (stylesheets/scripts/images)
    before they exist on S3. Achieved by applying a crude but effective
    ordering to the upload sequence to ensure HTML files are uploaded after all
    other assets.
    """
    html, css, js, others = [], [], [], []
    for p in path_names:
        pl = p.lower()
        if pl.endswith(('.html', '.htm', '.xhtml')):
            html.append(p)
        elif pl.endswith(('.css')):
            css.append(p)
        elif pl.endswith(('.js')):
            js.append(p)
        else:
            others.append(p)

    def _srt(g):
        return sorted(sorted(g), key=lambda x: x.count('/'), reverse=True)

    ordered = _srt(others) + _srt(css) + _srt(js) + _srt(html)
    assert len(ordered) == len(path_names)
    return ordered


def change_list(diff):
    """
    Paths that need changes made on S3, along with the reason why.

    Changes should be made in the order returned, in an attempt to prevent the
    temporary period where there may be incorrect links between HTML files,
    referencing static assets that haven't been uploaded yet.
    """
    # Attribute changes first, less risk of content changes.
    dl = [(ChangeReason.ATTRIBUTES_CHANGED, p)
          for p in diff['upload']['attributes_changed']]
    dl += [(ChangeReason.NEW_FILE, p)
           for p in _order_for_upload(diff['upload']['new_files'])]
    dl += [(ChangeReason.CONTENT_CHANGED, p)
           for p in _order_for_upload(diff['upload']['content_changed'])]
    dl += [(ChangeReason.DELETED, p)
           for p in diff['delete']]
    return dl
