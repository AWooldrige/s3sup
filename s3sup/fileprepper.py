import os
import pathlib
import pickle
import hashlib
import mimetypes
import s3sup.rules
import collections


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


def s3_path(s3_project_root, rel_path):
    pr = s3_project_root.lstrip('/').rstrip('/')
    if pr == '':
        return '{0}{1}'.format(pr, rel_path)
    else:
        return '{0}/{1}'.format(pr, rel_path)


class FilePrepper:

    def __init__(self, project_root, path, rules):
        self.project_root = project_root
        self.path = path
        self.abspath = os.path.abspath(os.path.join(project_root, path))
        self.rules = rules
        self.path_directives = s3sup.rules.directives_for_path(
            self.path, self.rules)

        attrs = {}
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
        # self.attrs = {k: attrs[k] for k in sorted(attrs)}
        self.attrs = collections.OrderedDict(
            sorted(attrs.items(), key=lambda t: t[0]))

    def attributes(self):
        return self.attrs

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
        boto_attrs = {key_map[k]: v for k, v in self.attrs.items()}

        # Defaults for if none set
        defaults = {
            'ACL': 'public-read',
            'CacheControl': 'max-age=120'
        }
        for k, v in defaults.items():
            if k not in boto_attrs:
                boto_attrs[k] = v
        return boto_attrs

    def s3_path(self):
        root = ''
        try:
            root = self.rules['aws']['s3_project_root']
        except KeyError:
            pass
        return s3_path(root, self.path)

    def content_fileobj(self):
        return open(self.abspath, 'rb')

    def content_hash(self):
        try:
            return self._content_hash
        except AttributeError:
            pass
        sha = hashlib.sha256()
        with self.content_fileobj() as f_in:
            fbuf = f_in.read(HASH_READ_BLOCK)
            while len(fbuf) > 0:
                sha.update(fbuf)
                fbuf = f_in.read(HASH_READ_BLOCK)
            self._content_hash = sha.hexdigest()
        return self._content_hash

    def attributes_hash(self):
        try:
            return self._attributes_hash
        except AttributeError:
            pass
        self._attributes_hash = hashlib.sha256(
            pickle.dumps(self.attrs)).hexdigest()
        return self._attributes_hash

    def hashes(self):
        return (self.content_hash(), self.attributes_hash())
