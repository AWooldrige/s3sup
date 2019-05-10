import os
import click
import csv
import tempfile
import unittest

from s3sup.catalogue import (
    Catalogue, load_gzipped_sqlite, write_gzipped_sqlite,
    MAX_DB_SCHEMA_VERSION, change_list, ChangeReason, _order_for_upload)


class TestCatalogueReadersAndWriters(unittest.TestCase):

    def setUp(self):
        self.simple_cat = Catalogue()
        self.simple_cat.add_file('test/blah.img', 'AABBCC', 'XXYYZZ')

        self.edgecase_cat = (
            Catalogue()
            .add_file('test/blah.img', 'AABBCC', 'XXYYZZ')
            .add_file('test/blah.img', 'AABBCC', '112233')  # Same file
            .add_file('fest_ЬℓσБ: &8>', 'FS FSFS', '7A9 ')  # Unicode
            .add_file('♬ /music.fav.mp3', 200010, '7A9 ')  # Integer hash
            .add_file('test/I think, "great.img', 'AABBCC', '11,2233')  # Comma
        )
        hndl, self.tmpf_path = tempfile.mkstemp()
        os.close(hndl)

    def old_to_csv_from_catalogue(self, cat, path):
        with open(path, 'wt', newline='') as f:
            writer = csv.writer(f, quoting=csv.QUOTE_ALL)
            writer.writerow(['path', 'content_hash', 'attributes_hash'])
            for path, (content_hsh, attributes_hsh) in cat.to_dict().items():
                writer.writerow([path, content_hsh, attributes_hsh])

    def tearDown(self):
        os.remove(self.tmpf_path)

    def test_simple_to_dict(self):
        self.assertEqual(
            self.simple_cat.to_dict(),
            {'test/blah.img': ('AABBCC', 'XXYYZZ')}
        )

    def test_simple_to_sqlite(self):
        self.simple_cat.to_sqlite(self.tmpf_path)
        with load_gzipped_sqlite(self.tmpf_path) as c:
            r = c.execute('PRAGMA user_version').fetchone()
            self.assertEqual(2, r[0])
            r = c.execute('SELECT * FROM files').fetchone()
            self.assertEqual('test/blah.img', r['path'])
            self.assertEqual('AABBCC', r['content_hash'])
            self.assertEqual('XXYYZZ', r['attributes_hash'])

    def test_simple_from_csv(self):
        self.old_to_csv_from_catalogue(self.simple_cat, self.tmpf_path)
        ncat = Catalogue()
        ncat.from_csv(self.tmpf_path)
        self.assertEqual(ncat.to_dict(), self.simple_cat.to_dict())

    def test_simple_from_sqlite(self):
        self.simple_cat.to_sqlite(self.tmpf_path)
        ncat = Catalogue()
        ncat.from_sqlite(self.tmpf_path)
        self.assertEqual(ncat.to_dict(), self.simple_cat.to_dict())

    def test_edge_cases_to_dict(self):
        self.assertEqual(
            self.edgecase_cat.to_dict(),
            {
                'test/blah.img': ('AABBCC', '112233'),
                'fest_ЬℓσБ: &8>': ('FS FSFS', '7A9 '),
                '♬ /music.fav.mp3': ('200010', '7A9 '),
                'test/I think, "great.img': ('AABBCC', '11,2233'),
            }
        )

    def test_edge_cases_to_sqlite(self):
        self.edgecase_cat.to_sqlite(self.tmpf_path)
        with load_gzipped_sqlite(self.tmpf_path) as c:
            rs = c.execute('SELECT * FROM files ORDER BY path').fetchall()
            self.assertEqual(4, len(rs))
            self.assertEqual("fest_ЬℓσБ: &8>", rs[0]['path'])
            self.assertEqual('test/I think, "great.img', rs[1]['path'])
            self.assertEqual("♬ /music.fav.mp3", rs[3]['path'])

    def test_edgecase_from_csv(self):
        self.old_to_csv_from_catalogue(self.edgecase_cat, self.tmpf_path)
        ncat = Catalogue()
        ncat.from_csv(self.tmpf_path)
        self.assertEqual(ncat.to_dict(), self.edgecase_cat.to_dict())

    def test_edgecase_from_sqlite(self):
        self.edgecase_cat.to_sqlite(self.tmpf_path)
        ncat = Catalogue()
        ncat.from_sqlite(self.tmpf_path)
        self.assertEqual(ncat.to_dict(), self.edgecase_cat.to_dict())

    def test_edgecase_from_sqlite_but_older_version(self):
        new_version = MAX_DB_SCHEMA_VERSION - 1
        with write_gzipped_sqlite(self.tmpf_path) as c:
            c.execute('PRAGMA user_version = {v:d}'.format(v=new_version))
            c.execute('''CREATE TABLE files (
                path TEXT,
                content_hash TEXT,
                attributes_hash TEXT)''')
        ncat = Catalogue()
        ncat.from_sqlite(self.tmpf_path)
        self.assertEqual({}, ncat.to_dict())

    def test_edgecase_from_sqlite_but_newer_version(self):
        new_version = MAX_DB_SCHEMA_VERSION + 1
        with write_gzipped_sqlite(self.tmpf_path) as c:
            c.execute('PRAGMA user_version = {v:d}'.format(v=new_version))
            c.execute('CREATE TABLE dummy ( path TEXT )')
        ncat = Catalogue()
        with self.assertRaisesRegex(
                click.ClickException, 'is version 3.*to version 2'):
            ncat.from_sqlite(self.tmpf_path)


class TestCatalogueDiff(unittest.TestCase):

    def setUp(self):
        self.simple_cat = Catalogue()
        self.simple_cat.add_file('test/blah.img', 'AABBCC', 'XXYYZZ')

        self.edgecase_cat = (
            Catalogue()
            .add_file('test/blah.img', 'AABBCC', 'XXYYZZ')
            .add_file('test/blah.img', 'AABBCC', '112233')  # Same file
            .add_file('fest_ЬℓσБ: &8>', 'FS FSFS', '7A9 ')  # Unicode
            .add_file('♬ /music.fav.mp3', 200010, '7A9 ')  # Integer hash
            .add_file('test/I think, "great.img', 'AABBCC', '11,2233')  # Comma
        )
        hndl, self.tmpf_path = tempfile.mkstemp()
        os.close(hndl)

    def test_diff_dict(self):
        local_cat = (
            Catalogue()
            .add_file('index.html', '9J9J9J', 'P2P2P2')
            .add_file('assets/blam/160-180.jpg', 'A1A1A1', 'B3B3B3')
            .add_file('♬ /music.fav.mp3', 200010, '7A9 ')
            .add_file('robots.txt', '4b4b4b', '929292')
            .add_file('consistent.html.html', '123', '123')
            .add_file('news_update.html', '4b4b4b', '929292')
        )
        remote_cat = (
            Catalogue()
            .add_file('assets/blam/160-180.jpg', 'A1A1A1', '9S9S95')
            .add_file('consistent.html.html', '123', '123')
            .add_file('index.html', '282828', 'P2P2P2')
            .add_file('♬ /music.fav.mp3', 200010, '7A9 ')
            .add_file('robots.txt', 'asdfhl', 'lkjfds')
            .add_file('tempfile.txt', 'fj8fj8', 'flwlfwl')
        )
        diff_dict, new_remote_catalogue = local_cat.diff_dict(remote_cat)
        expected = {
            'num_changes': 5,
            'upload': {
                'new_files': ['news_update.html'],
                'content_changed': ['index.html', 'robots.txt'],
                'attributes_changed': ['assets/blam/160-180.jpg']
            },
            'delete': ['tempfile.txt'],
            'delete_protected': [],
            'unchanged': ['consistent.html.html', '♬ /music.fav.mp3']
        }
        self.assertEqual(expected, diff_dict)

    def test_diff_dict_with_protected_deletion(self):
        local_cat = (
            Catalogue(preserve_deleted_files=True)
            .add_file('index.html', '9J9J9J', 'P2P2P2')
            .add_file('assets/blam/160-180.jpg', 'A1A1A1', 'B3B3B3')
            .add_file('robots.txt', '4b4b4b', '929292')
            .add_file('consistent.html.html', '123', '123')
            .add_file('news_update.html', '4b4b4b', '929292')
        )
        remote_cat = (
            Catalogue()
            .add_file('assets/blam/160-180.jpg', 'A1A1A1', '9S9S95')
            .add_file('consistent.html.html', '123', '123')
            .add_file('index.html', '282828', 'P2P2P2')
            .add_file('♬ /music.fav.mp3', 200010, '7A9 ')
            .add_file('robots.txt', 'asdfhl', 'lkjfds')
            .add_file('tempfile.txt', 'fj8fj8', 'flwlfwl')
        )
        diff_dict, new_remote_catalogue = local_cat.diff_dict(remote_cat)
        expected_diff = {
            'num_changes': 4,
            'upload': {
                'new_files': ['news_update.html'],
                'content_changed': ['index.html', 'robots.txt'],
                'attributes_changed': ['assets/blam/160-180.jpg']
            },
            'delete': [],
            'delete_protected': ['tempfile.txt', '♬ /music.fav.mp3'],
            'unchanged': ['consistent.html.html']
        }
        self.assertEqual(expected_diff, diff_dict)
        rmt_cat_d = new_remote_catalogue.to_dict()
        self.assertTrue('tempfile.txt' in rmt_cat_d)
        self.assertEqual(('fj8fj8', 'flwlfwl'), rmt_cat_d['tempfile.txt'])
        self.assertTrue('♬ /music.fav.mp3' in rmt_cat_d)
        self.assertEqual(('200010', '7A9 '), rmt_cat_d['♬ /music.fav.mp3'])


class TestOrderForUpload(unittest.TestCase):
    def testGeneral(self):
        """
        The rules are to upload:
          1) Other assets first
          2) CSS & JS next
          3) HTML last (in case they reference any of the above assets)
        """
        original = [
            'news/test.jpg.htm',    # .htm still probably in use
            'extra/assets.js',
            'assets.js',
            'archive/index.htm',
            'extra/1.2/assets.js',
            'index.html',
            'favicon.ico',
            'noextension',
            'archive/logo.png',
            'welcome.HTML',         # Uppercase should be fine
            'style.css',
            'style.huh?',
            '♬ /music.fav.mp3',
            '♬ /music.fav.html',
            'logo.jpg',
            'additional/style.css'
        ]
        expected = [
            # Unknown items first, deepest directories first
            'archive/logo.png',
            '♬ /music.fav.mp3',
            'favicon.ico',
            'logo.jpg',
            'noextension',
            'style.huh?',

            # CSS next, deepest directories first
            'additional/style.css',
            'style.css',

            # JS after, deepest directories first
            'extra/1.2/assets.js',
            'extra/assets.js',
            'assets.js',

            # HTML last, deepest directories first
            'archive/index.htm',
            'news/test.jpg.htm',
            '♬ /music.fav.html',
            'index.html',
            'welcome.HTML'
        ]
        self.assertEqual(expected, _order_for_upload(original))


class TestChangeList(unittest.TestCase):

    def testHtmlFilesListedLastForNewUploads(self):
        """
        This is a rather crude was of ensuring static assets are available
        before the HTML documents that reference them.
        """
        local_cat = (
            Catalogue()
            .add_file('news/test.jpg.htm', 'GGG', '777')
            .add_file('flex.js', 'HHH', '888')
            .add_file('assets/blah.jpg', 'FFF', '666')
            .add_file('assets/xtr/blam.css', 'III', '999')
            .add_file('index.html', 'AAA', '111')
            .add_file('words.txt', 'HHH', '888')
            .add_file('test/I think, "great.img', 'DDD', '444')
            .add_file('assets/blah.png', 'EEE', '555')
        )
        remote_cat = Catalogue()
        diff, new_remote_catalogue = local_cat.diff_dict(remote_cat)
        cl = change_list(diff)
        self.assertEqual([
            (ChangeReason.NEW_FILE, 'assets/blah.jpg'),
            (ChangeReason.NEW_FILE, 'assets/blah.png'),
            (ChangeReason.NEW_FILE, 'test/I think, "great.img'),
            (ChangeReason.NEW_FILE, 'words.txt'),
            (ChangeReason.NEW_FILE, 'assets/xtr/blam.css'),
            (ChangeReason.NEW_FILE, 'flex.js'),
            (ChangeReason.NEW_FILE, 'news/test.jpg.htm'),
            (ChangeReason.NEW_FILE, 'index.html')
        ], cl)

    def testHtmlFilesListedLastForChangedFiles(self):
        local_cat = (
            Catalogue()
            .add_file('news/test.jpg.htm', 'GGG', '777')
            .add_file('flex.js', 'HHH', '888')
            .add_file('assets/blah.jpg', 'FFF', '666')
            .add_file('assets/xtr/blam.css', 'III', '999')
            .add_file('index.html', 'AAA', '111')
            .add_file('words.txt', 'HHH', '888')
            .add_file('test/I think, "great.img', 'DDD', '444')
            .add_file('assets/blah.png', 'EEE', '555')
        )
        remote_cat = (
            Catalogue()
            .add_file('news/test.jpg.htm', 'GGGCHANGED', '777')
            .add_file('flex.js', 'HHH', '888')
            .add_file('assets/blah.jpg', 'FFFCHANGED', '666')
            .add_file('assets/xtr/blam.css', 'IIICHANGED', '999')
            .add_file('index.html', 'AAACHANGED', '111')
            .add_file('words.txt', 'HHHCHANGED', '888')
            .add_file('test/I think, "great.img', 'DDD', '444')
            .add_file('assets/blah.png', 'EEE', '555')
        )
        diff, new_remote_catalogue = local_cat.diff_dict(remote_cat)
        cl = change_list(diff)
        self.assertEqual([
            (ChangeReason.CONTENT_CHANGED, 'assets/blah.jpg'),
            (ChangeReason.CONTENT_CHANGED, 'words.txt'),
            (ChangeReason.CONTENT_CHANGED, 'assets/xtr/blam.css'),
            (ChangeReason.CONTENT_CHANGED, 'news/test.jpg.htm'),
            (ChangeReason.CONTENT_CHANGED, 'index.html')
        ], cl)


if __name__ == '__main__':
    unittest.main()
