"""Offline transport fixtures only; no Valve downloads, execution or owner-PC actions."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import ssl
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import steam_offline_download as tool


class Response(io.BytesIO):
    def __init__(self, body, url, status=200, headers=None):
        super().__init__(body)
        self.url = url; self.status = status
        self.headers = {'Content-Length': str(len(body))} if headers is None else headers

    def geturl(self):
        return self.url


class Download(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.body = b'only original synthetic fixture bytes'
        self.row = {'name': 'client/fixture.zip', 'size': len(self.body),
                    'sha256': hashlib.sha256(self.body).hexdigest()}
        self.url = tool.official_url(tool.steam_client.CDN + '/', 'fixture.zip')
        self.destination = self.root / 'fixture.zip'

    def source(self, body=None, **options):
        return Mock(open=Mock(side_effect=lambda url, **kw: Response(
            self.body if body is None else body, url, **options)))

    def test_real_lock_sources_counts_sizes_and_canonical_archive(self):
        rows, urls = tool.inputs()
        self.assertEqual(len(rows), 62)
        self.assertEqual(sum(r['size'] for r in rows), 379176939)
        self.assertEqual(tool.packer.cache.archive_size(rows), 379228160)
        self.assertEqual(rows, tool.packer.pins())
        self.assertEqual(sum(u.startswith(tool.DEBIAN_BASE + 'pool/') for u in urls.values()), 45)
        self.assertEqual(sum(u.startswith(tool.steam_client.CDN + '/') for u in urls.values()), 17)

    def test_unreviewed_origins_and_paths_refused(self):
        for base in ('http://deb.debian.org/debian/', 'https://evil.test/',
                     'https://deb.debian.org:443/debian/', 'https://user@deb.debian.org/debian/'):
            with self.subTest(base=base), self.assertRaises(ValueError):
                tool.official_url(base, 'pool/a.deb')
        for name in ('../x', 'pool/../x', '/x', 'a//x', 'a/./x', 'x?token=y', 'x#fragment',
                     'a%2fb', 'x\\y', 'x\x00', 'https://evil.test/x'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                tool.official_url(tool.DEBIAN_BASE, name)

    def test_source_provenance_bindings_and_missing_contract_refused(self):
        original = tool.read_lock
        for field in ('gui_inputs_sha256', 'release'):
            def changed(path):
                raw, obj = original(path)
                if path.name == 'steam-dependencies.lock.json':
                    obj = copy.deepcopy(obj); obj[field] = 'unreviewed' if field != 'release' else {}
                return raw, obj
            with self.subTest(field=field), patch.object(tool, 'read_lock', side_effect=changed):
                with self.assertRaises(ValueError): tool.inputs()

    def test_lock_read_is_bounded_and_rejects_links(self):
        path = self.root / 'lock.json'; path.write_bytes(b' ' * (256*1024+1))
        with self.assertRaises(ValueError): tool.read_lock(path)
        link = self.root / 'alias'; link.symlink_to(path)
        with self.assertRaises(ValueError): tool.read_lock(link)

    def test_tls_verification_and_all_redirects_refused(self):
        with patch.object(tool.urllib.request, 'build_opener') as build:
            tool.opener()
        handler = build.call_args.args[-1]
        self.assertEqual(handler._context.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(handler._context.check_hostname)
        for url in (self.url, 'https://deb.debian.org/debian/pool/x.deb', 'http://evil.test/x'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'redirect refused'):
                tool.NoRedirect().redirect_request(None, None, 302, '', {}, url)

    def test_verified_download_atomic_publication_and_offline_reuse(self):
        source = self.source()
        self.assertTrue(tool.download(self.row, self.url, self.destination, source))
        self.assertEqual(self.destination.read_bytes(), self.body)
        self.assertEqual(self.destination.stat().st_nlink, 1)
        self.assertFalse(tool.download(self.row, self.url, self.destination, Mock(open=Mock(side_effect=AssertionError))))
        source.open.assert_called_once_with(self.url, timeout=60)
        self.assertEqual(list(self.root.iterdir()), [self.destination])

    def test_corrupt_truncated_oversized_and_wrong_hash_never_published(self):
        for body in (self.body[:-1], self.body+b'x', b'x'*len(self.body)):
            with self.subTest(body=body), self.assertRaises(ValueError):
                tool.download(self.row, self.url, self.destination, self.source(body, headers={}))
            self.assertEqual(list(self.root.iterdir()), [])

    def test_response_status_url_length_encoding_refused(self):
        for options in ({'status': 206}, {'status': 302}, {'headers': {'Content-Length': '999'}},
                        {'headers': {'Content-Length': '-1'}}, {'headers': {'Content-Length': '9e1'}},
                        {'headers': {'Content-Encoding': 'gzip'}}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                tool.download(self.row, self.url, self.destination, self.source(**options))
            self.assertEqual(list(self.root.iterdir()), [])
        response = Response(self.body, 'https://evil.test/')
        with self.assertRaises(ValueError):
            tool.download(self.row, self.url, self.destination, Mock(open=Mock(return_value=response)))

    def test_interruption_cleanup_retry_and_time_bound(self):
        for error in (OSError('fixture interruption'), KeyboardInterrupt()):
            response = self.source().open(self.url)
            response.read = Mock(side_effect=[self.body[:3], error])
            with self.subTest(error=type(error)), self.assertRaises(type(error)):
                tool.download(self.row, self.url, self.destination, Mock(open=Mock(return_value=response)))
            self.assertEqual(list(self.root.iterdir()), [])
        with patch.object(tool.time, 'monotonic', side_effect=[0, 901]):
            with self.assertRaisesRegex(ValueError, 'time bound'):
                tool.download(self.row, self.url, self.destination, self.source())
        self.assertTrue(tool.download(self.row, self.url, self.destination, self.source()))

    def test_existing_bad_files_symlinks_hardlinks_and_reparse_ancestors_preserved(self):
        self.destination.write_bytes(b'preserve')
        with self.assertRaises(ValueError):
            tool.download(self.row, self.url, self.destination, self.source())
        self.assertEqual(self.destination.read_bytes(), b'preserve')
        self.destination.unlink(); real = self.root / 'real'; real.write_bytes(self.body)
        self.destination.symlink_to(real)
        with self.assertRaises(ValueError): tool.checked(self.destination, self.row)
        self.destination.unlink(); os.link(real, self.destination)
        with self.assertRaises(ValueError): tool.checked(self.destination, self.row)
        linked = self.root / 'linked'; linked.symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError): tool.safe_path(linked / 'new-file')
        with patch.object(Path, 'lstat', return_value=Mock(st_file_attributes=0x400, st_mode=0o40700)):
            with self.assertRaisesRegex(ValueError, 'reparse'): tool.safe_path(self.root)

    def test_concurrent_publication_reuses_only_exact_file(self):
        def concurrent(stage, destination):
            destination.write_bytes(self.body)
            raise FileExistsError()
        with patch.object(tool.steam_client, 'publish', side_effect=concurrent):
            tool.download(self.row, self.url, self.destination, self.source())
        self.assertEqual(self.destination.read_bytes(), self.body)
        self.destination.unlink()
        def corrupt(stage, destination):
            destination.write_bytes(b'preserve')
            raise FileExistsError()
        with patch.object(tool.steam_client, 'publish', side_effect=corrupt):
            with self.assertRaises(ValueError): tool.download(self.row, self.url, self.destination, self.source())
        self.assertEqual(self.destination.read_bytes(), b'preserve')

    def test_windows_publication_uses_no_replace_rename(self):
        with patch.object(tool.steam_client.os, 'name', 'nt'), patch.object(tool.steam_client.os, 'rename') as rename:
            tool.steam_client.publish('stage', 'final')
        rename.assert_called_once_with('stage', 'final')

    def test_full_62_part_download_pack_verify_and_repeat_without_http(self):
        original, urls = tool.inputs()
        rows = [dict(r, size=len(self.body), sha256=self.row['sha256']) for r in original]
        source = self.source()
        with patch.object(tool, 'inputs', return_value=(rows, urls)), patch.object(tool, 'opener', return_value=source), patch('builtins.print'):
            result = tool.prepare(self.root)
        self.assertEqual(source.open.call_count, 62)
        output = Path(result['path'])
        self.assertEqual(result['parts'], 62)
        self.assertFalse(result['client_executed']); self.assertFalse(result['agreement_accepted'])
        self.assertEqual(tool.packer.digest_file(output), result['sha256'])
        tool.packer.verify(output, rows)
        self.assertFalse(any(p.name.startswith('.ideck-') for p in self.root.iterdir()))
        with patch.object(tool, 'inputs', return_value=(rows, urls)), patch.object(tool, 'opener', side_effect=AssertionError):
            self.assertEqual(tool.prepare(self.root), result)
        output.write_bytes(b'preserve corrupt output')
        with patch.object(tool, 'inputs', return_value=(rows, urls)), self.assertRaises(ValueError):
            tool.prepare(self.root)
        self.assertEqual(output.read_bytes(), b'preserve corrupt output')

    def test_partial_run_retry_reuses_completed_part_without_http_range(self):
        rows = [dict(self.row, name='client/a.zip'), dict(self.row, name='debs/b.deb')]
        urls = {r['name']: self.url + r['name'].split('/')[-1] for r in rows}
        first = Mock(open=Mock(side_effect=[Response(self.body, urls[rows[0]['name']]), OSError('interrupted')]))
        with patch.object(tool, 'inputs', return_value=(rows, urls)), patch.object(tool, 'opener', return_value=first), patch('builtins.print'):
            with self.assertRaises(OSError): tool.prepare(self.root)
        self.assertEqual((self.root / rows[0]['name']).read_bytes(), self.body)
        self.assertFalse((self.root / 'owner-steam-cache.tar').exists())
        second = self.source()
        with patch.object(tool, 'inputs', return_value=(rows, urls)), patch.object(tool, 'opener', return_value=second), patch('builtins.print'):
            tool.prepare(self.root)
        second.open.assert_called_once_with(urls[rows[1]['name']], timeout=60)

    def test_space_failure_before_network(self):
        with patch.object(tool.shutil, 'disk_usage', return_value=Mock(free=0)), patch.object(tool, 'opener', side_effect=AssertionError):
            with self.assertRaisesRegex(ValueError, 'space'): tool.prepare(self.root)


if __name__ == '__main__': unittest.main()
