import csv
import click
import enum


class ChangeReason(enum.Enum):
    NEW_FILE = 1
    CONTENT_CHANGED = 2
    ATTRIBUTES_CHANGED = 3
    DELETED = 4
    NO_CHANGE = 5


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

    def diff_list(self, remote_catalogue):
        """
        Return only paths that need changing, in a list with format:
        TODO
        """
        dd = self.diff_dict(remote_catalogue)
        dl = [(ChangeReason.NEW_FILE, p)
              for p in dd['upload']['new_files']]
        dl += [(ChangeReason.CONTENT_CHANGED, p)
               for p in dd['upload']['content_changed']]
        dl += [(ChangeReason.ATTRIBUTES_CHANGED, p)
               for p in dd['upload']['attributes_changed']]
        dl += [(ChangeReason.ATTRIBUTES_CHANGED, p)
               for p in dd['upload']['attributes_changed']]
        dl += [(ChangeReason.DELETED, p)
               for p in dd['upload']['delete']]
        return dl


def print_diff_dict(dd):
    for p in dd['upload']['new_files']:
        click.echo(click.style(' + [New]', fg='green') + '     {0}'.format(p))
    for p in dd['upload']['content_changed']:
        click.echo(
            click.style(' * [Changed]', fg='blue') + '     {0}'.format(p))
    for p in dd['upload']['attributes_changed']:
        click.echo(click.style(' ^ [Attrs]', fg='cyan') + '     {0}'.format(p))
    for p in dd['delete']:
        click.echo(click.style(' ^ [Delete]', fg='red') + '     {0}'.format(p))


def diff_as_list(diff):
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
