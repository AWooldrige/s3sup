import functools
import pathlib
import pickle
import hashlib
import mimetypes
import collections

import click
import humanize

import s3sup.rules


TEXT_BASED_MIMETYPES = {
    'text/css',
    'text/csv',
    'text/html',
    'text/javascript',
    'text/ecmascript',
    'application/json',
    'application/javascript',
    'application/ecmascript',
    'application/rtf',
    'application/x-sh',
    'application/x-c',
    'application/x-latex',
    'image/svg+xml',
    'text/plain',
    'text/yaml',
    'application/yaml',
    'application/x-yaml',
    'application/xhtml+xml',
    'application/xml',
    'text/xml',
    'application/vnd.mozilla.xul+xml'
}
DEFAULT_CHARSET_MIMETYPES = TEXT_BASED_MIMETYPES
HASH_READ_BLOCK = 65536


class FilePrepper:

    def __init__(self, project_root, path, rules):
        self.project_root = project_root
        self.path = path

        self.path_proj = pathlib.Path(project_root)

        # Relative to project root. E.g. 'index.html'.
        self.path_local_rel = pathlib.Path(path)

        # Absolute path. E.g. '/home/jsmith/proj_1/index.html'
        self.path_local_abs = self.path_proj.joinpath(
            self.path_local_rel).resolve()

        self.rules = rules
        self.path_directives = s3sup.rules.directives_for_path(
            self.path, self.rules)

    @functools.lru_cache(maxsize=None)
    def attributes(self):
        # Defaults
        attrs = {
            'ACL': 'public-read',
            'Cache-Control': 'max-age=10'
        }
        fext = pathlib.Path(self.path).suffix
        mime_type, encoding = mimetypes.guess_type(self.path)
        try:
            mime_type = self.rules['mimetype_overrides'][fext]
        except KeyError:
            pass

        charset_mimetypes = DEFAULT_CHARSET_MIMETYPES
        try:
            charset_mimetypes = self.rules['charset_mimetypes']
        except KeyError:
            pass

        charset = None
        if mime_type in charset_mimetypes:
            charset = 'utf-8'
            try:
                charset = self.rules['charset']
            except KeyError:
                pass
        try:
            charset = self.path_directives['charset']
        except KeyError:
            pass

        content_type = 'application/octet-stream'
        if mime_type is not None:
            content_type = mime_type
            if charset is not None:
                content_type += '; charset={0}'.format(charset)
        try:
            content_type = self.path_directives['Content-Type']
        except KeyError:
            pass
        attrs['Content-Type'] = content_type

        if encoding:
            attrs['Content-Encoding'] = encoding

        # conf_name: boto_name
        directives_to_transfer = {
            'ACL',
            'Cache-Control',
            'Content-Disposition',
            'Content-Language',
            'Content-Encoding',
            'S3Metadata',
            'StorageClass',
            'WebsiteRedirectLocation'
        }
        for dctv in directives_to_transfer:
            try:
                attrs[dctv] = self.path_directives[dctv]
            except KeyError:
                continue
        # Set as a sorted dict
        # self.attributes() = {k: attrs[k] for k in sorted(attrs)}
        return collections.OrderedDict(
            sorted(attrs.items(), key=lambda t: t[0]))

    def attributes_as_boto_args(self):
        key_map = {
            'ACL': 'ACL',
            'StorageClass': 'StorageClass',
            'WebsiteRedirectLocation': 'WebsiteRedirectLocation',
            'Cache-Control': 'CacheControl',
            'Content-Disposition': 'ContentDisposition',
            'Content-Type': 'ContentType',
            'Content-Encoding': 'ContentEncoding',
            'Content-Language': 'ContentLanguage',
            'S3Metadata': 'Metadata'
        }
        return {key_map[k]: v for k, v in self.attributes().items()}

    def s3_path(self):
        try:
            root = self.rules['aws']['s3_project_root'].lstrip('/').rstrip('/')
            return '{0}/{1}'.format(root, self.path_local_rel.as_posix())
        except KeyError:
            return self.path_local_rel.as_posix()

    def content_fileobj(self):
        return self.path_local_abs.open('rb')

    def size(self):
        """Size of local file in bytes"""
        return self.path_local_abs.stat().st_size

    @functools.lru_cache(maxsize=None)
    def content_hash(self):
        sha = hashlib.sha256()
        with self.content_fileobj() as f_in:
            fbuf = f_in.read(HASH_READ_BLOCK)
            while len(fbuf) > 0:
                sha.update(fbuf)
                fbuf = f_in.read(HASH_READ_BLOCK)
            content_hash = sha.hexdigest()
        return content_hash

    @functools.lru_cache(maxsize=None)
    def attributes_hash(self):
        return hashlib.sha256(pickle.dumps(self.attributes())).hexdigest()

    def hashes(self):
        return (self.content_hash(), self.attributes_hash())

    def print_summary(self):
        to_print = {
            'Local path': click.format_filename(str(self.path_local_abs)),
            'S3 path': 's3://{0}/{1}'.format(
                self.rules['aws']['s3_bucket_name'], self.s3_path()),
            'Attributes': self.attributes(),
            'Content size': humanize.naturalsize(self.size()),
            'Content hash': self.content_hash(),
            'Attributes hash': self.attributes_hash()
        }
        title = 'File: {0}'.format(click.format_filename(
            str(self.path_local_rel)))
        s3sup.utils.pprint_h3(title)
        s3sup.utils.pprint_dict(to_print)
