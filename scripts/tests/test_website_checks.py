import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.error import HTTPError, URLError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_links
import build_site


class Response:
    status = 200
    url = 'https://example.com/paper'
    headers = {'Content-Type': 'text/html'}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, size):
        return b'<!doctype html>'


class LinkChecks(unittest.TestCase):
    @patch.object(audit_links.time, 'sleep')
    def test_404_requires_two_get_confirmations(self, _):
        missing = HTTPError('https://example.com/paper', 404, 'Missing', {}, None)
        with patch.object(audit_links, 'urlopen', side_effect=[missing, missing, missing]) as fetch:
            self.assertEqual(audit_links.check_url(missing.url)['result'], 'broken')
            self.assertEqual([c.args[0].method for c in fetch.call_args_list], ['HEAD', 'GET', 'GET'])

    @patch.object(audit_links.time, 'sleep')
    def test_head_failure_and_temporary_failure_are_not_broken(self, _):
        missing = HTTPError('https://example.com/paper', 404, 'Missing', {}, None)
        with patch.object(audit_links, 'urlopen', side_effect=[missing, Response()]):
            self.assertEqual(audit_links.check_url(missing.url)['result'], 'ok')
        with patch.object(audit_links, 'urlopen', side_effect=URLError('timeout')):
            self.assertEqual(audit_links.check_url(missing.url)['result'], 'unverified')

    def test_paywall_is_not_broken(self):
        error = HTTPError('https://example.com/paper', 403, 'Blocked', {}, None)
        with patch.object(audit_links, 'urlopen', side_effect=error):
            self.assertEqual(audit_links.check_url(error.url)['result'], 'blocked')

    def test_google_sign_in_is_not_verified(self):
        response = Response()
        response.url = 'https://accounts.google.com/ServiceLogin'
        with patch.object(audit_links, 'urlopen', return_value=response):
            self.assertEqual(audit_links.check_url('https://drive.google.com/file/d/example/view')['result'], 'unverified')

    def test_local_absolute_relative_fragments_and_preview_images(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'research').mkdir()
            (root / 'image.png').write_bytes(b'image')
            (root / 'research/index.html').write_text('<h1 id="paper">Paper</h1>', encoding='utf-8')
            (root / 'index.html').write_text('''<a href="/research/#paper">Paper</a>
                <a href="https://adam-hale-shapiro.com/research/?v=1#paper">Paper</a>
                <meta property="og:image" content="https://adam-hale-shapiro.com/image.png?v=123">
                <a href="/research/#missing">Missing anchor</a>
                <img src="missing.png"><a href="https://example.com/paper">External</a>''', encoding='utf-8')
            errors, remote, _ = audit_links.collect_references(root)
            self.assertEqual(len(errors), 2)
            self.assertEqual(set(remote), {'https://example.com/paper'})


class SharingChecks(unittest.TestCase):
    def test_every_page_has_one_correct_social_card(self):
        from urllib.parse import urlsplit
        for path in build_site.DOCS.rglob('index.html'):
            with self.subTest(path=path):
                tree = build_site.Tree(path.read_text(encoding='utf-8')).root
                tags = {n.attrs.get('property') or n.attrs.get('name'): n.attrs.get('content')
                        for n in tree.walk() if n.tag == 'meta'}
                self.assertTrue(tags['og:title'])
                self.assertTrue(tags['og:description'])
                self.assertEqual(tags['og:image:width'], '1200')
                self.assertEqual(tags['og:image:height'], '630')
                self.assertEqual(tags['twitter:card'], 'summary_large_image')
                self.assertEqual(tags['twitter:image'], tags['og:image'])
                self.assertEqual(tags['og:url'], build_site.SITE_URL + '/' + path.parent.relative_to(build_site.DOCS).as_posix().strip('./') + ('/' if path.parent != build_site.DOCS else ''))
                self.assertTrue((build_site.DOCS / urlsplit(tags['og:image']).path.lstrip('/')).is_file())


if __name__ == '__main__':
    unittest.main()
