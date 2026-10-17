"""Offline original Steam installer tests; synthetic ELF/ZIPs are not client proof."""
import copy
import hashlib
import io
import json
from pathlib import Path
import stat
import sys
import tempfile
import unittest
import urllib.request
from unittest.mock import Mock, patch
import zipfile
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import steam_client as client


def elf(machine=183):
    header = bytearray(64)
    header[:7] = b'\x7fELF\x02\x01\x01'
    header[18:20] = machine.to_bytes(2, 'little')
    return bytes(header) + b'fixture, never executable Steam\n'


class SteamClient(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ideck-steam-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cache = self.root / 'cache'
        self.cache.mkdir()
        self.destination = self.root / 'home' / 'Steam'
        self.lock = {
            'schema': 1, 'kind': 'private-steam-arm64-experiment',
            'channel': 'steamdeck_publicbeta', 'version': '1792192922',
            'manifest_url': client.CDN + '/' + client.MANIFEST,
            'manifest_sha256': 'a' * 64, 'upstream_commit': client.UPSTREAM,
            'redistribution_approved': False, 'parts': [],
        }
        self.archive([('steamrtarm64/steam', elf())])

    def archive(self, entries, component='bins_linuxarm64_linuxarm64', suffix='0'):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as z:
            for name, contents in entries:
                z.writestr(name, contents)
        contents = data.getvalue()
        name = component + '.zip.' + suffix * 40
        path = self.cache / name
        path.write_bytes(contents)
        part = {'component': component, 'file': name, 'size': len(contents),
                'sha256': hashlib.sha256(contents).hexdigest()}
        self.lock['parts'].append(part)
        return path, part

    def replace_native_archive(self, entries):
        self.lock['parts'].clear()
        return self.archive(entries)

    def assert_unpublished(self):
        self.assertFalse(self.destination.exists())
        if self.destination.parent.exists():
            self.assertEqual(list(self.destination.parent.glob('.steam-install-*')), [])

    def test_real_zip_extracts_and_records_no_login_or_acceptance(self):
        self.archive([('resources/readme.txt', b'resource')], 'resources_all')
        result = client.install(self.lock, self.cache, self.destination)
        self.assertEqual((self.destination / 'steamrtarm64/steam').read_bytes(), elf())
        self.assertEqual((self.destination / 'resources/readme.txt').read_bytes(), b'resource')
        self.assertEqual((self.destination / 'package/beta').read_text(), 'steamdeck_publicbeta\n')
        receipt = json.loads((self.destination / 'package/ideck-install.json').read_text())
        self.assertFalse(receipt['agreement_accepted'])
        self.assertFalse(receipt['login_performed'])
        self.assertFalse(result['client_executed'])
        self.assertEqual(result['native_machine'], 'AArch64')
        self.assertEqual(list(self.destination.parent.glob('.steam-install-*')), [])

    def test_backslash_paths_normalize_into_real_directories(self):
        self.replace_native_archive([('steamrtarm64\\steam', elf()), ('resources\\nested\\item', b'yes')])
        client.install(self.lock, self.cache, self.destination)
        self.assertEqual((self.destination / 'resources/nested/item').read_bytes(), b'yes')

    def test_traversal_absolute_drive_and_ambiguous_segments_rejected(self):
        for name in ('../escape', 'a/../../escape', '/escape', 'C:/escape',
                     '\\escape', 'a\\..\\escape', 'a//b', './thing', 'a/./b'):
            with self.subTest(name=name):
                self.replace_native_archive([('steamrtarm64/steam', elf()), (name, b'bad')])
                with self.assertRaisesRegex(ValueError, 'unsafe'):
                    client.install(self.lock, self.cache, self.destination)
                self.assert_unpublished()
        self.assertFalse((self.root / 'escape').exists())

    def test_zip_symlink_and_special_file_rejected(self):
        for kind in (stat.S_IFLNK, stat.S_IFIFO, stat.S_IFCHR, stat.S_IFSOCK):
            with self.subTest(kind=kind):
                info = zipfile.ZipInfo('unsafe')
                info.create_system = 3
                info.external_attr = (kind | 0o777) << 16
                self.replace_native_archive([('steamrtarm64/steam', elf()), (info, b'target')])
                with self.assertRaises(ValueError):
                    client.install(self.lock, self.cache, self.destination)
                self.assert_unpublished()

    def test_encrypted_member_metadata_rejected(self):
        info = zipfile.ZipInfo('item')
        info.flag_bits |= 1
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            client.member_name(info)

    def link(self, name):
        info = zipfile.ZipInfo(name)
        info.create_system = 3
        info.external_attr = (stat.S_IFLNK | 0o777) << 16
        return info

    def test_verified_sibling_and_codec_parent_alias_inventory(self):
        self.replace_native_archive([
            ('steamrtarm64/steam', elf()), ('steamrtarm64/libs/liba.so.1', b'lib'),
            ('steamrtarm64/libcodec.so.1', b'codec'),
            (self.link('steamrtarm64/libs/liba.so'), b'liba.so.1'),
            (self.link('steamrtarm64/video/libcodec.so.1'), b'../libcodec.so.1'),
        ])
        total, links = client.archive_inventory(self.lock, self.cache)
        self.assertGreater(total, 0)
        self.assertEqual(links['steamrtarm64/libs/liba.so'], ('liba.so.1', 'steamrtarm64/libs/liba.so.1'))
        self.assertEqual(links['steamrtarm64/video/libcodec.so.1'], ('../libcodec.so.1', 'steamrtarm64/libcodec.so.1'))

    def test_alias_creation_follows_all_regular_extraction(self):
        self.replace_native_archive([(self.link('libalias'), b'libtarget'),
                                     ('steamrtarm64/steam', elf()), ('libtarget', b'library')])
        calls = []
        def inspect_alias(path, target, **kwargs):
            self.assertEqual((path.parent / target).read_bytes(), b'library')
            self.assertEqual((path.parent / 'steamrtarm64/steam').read_bytes(), elf())
            calls.append((path.name, target))
        with patch.object(Path, 'symlink_to', inspect_alias):
            client.install(self.lock, self.cache, self.destination)
        self.assertEqual(calls, [('libalias', 'libtarget')])

    def test_link_escape_absolute_backslash_and_long_target_rejected(self):
        for target in (b'/outside', b'../../outside', b'a/b', b'a\\b', b'..', b'.', b'C:bad', b'x' * 257):
            with self.subTest(target=target):
                self.replace_native_archive([('steamrtarm64/steam', elf()), (self.link('steamrtarm64/alias'), target)])
                with self.assertRaises(ValueError):
                    client.install(self.lock, self.cache, self.destination)
                self.assert_unpublished()

    def test_link_chain_and_missing_target_rejected(self):
        for entries in ([(self.link('alias'), b'missing')],
                        [(self.link('alias'), b'alias2'), (self.link('alias2'), b'target'), ('target', b'data')]):
            self.replace_native_archive([('steamrtarm64/steam', elf()), *entries])
            with self.assertRaisesRegex(ValueError, 'regular internal'):
                client.install(self.lock, self.cache, self.destination)
            self.assert_unpublished()

    def test_no_regular_entry_can_descend_through_link(self):
        self.replace_native_archive([('steamrtarm64/steam', elf()), ('target', b'file'),
                                     (self.link('alias'), b'target'), ('alias/escape', b'bad')])
        with self.assertRaisesRegex(ValueError, 'descends through'):
            client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_locked_size_and_sha256_required_before_extraction(self):
        for field, replacement in (('size', self.lock['parts'][0]['size'] + 1), ('sha256', 'f' * 64)):
            with self.subTest(field=field):
                bad = copy.deepcopy(self.lock)
                bad['parts'][0][field] = replacement
                with patch.object(client.zipfile, 'ZipFile', side_effect=AssertionError('must verify first')):
                    with self.assertRaisesRegex(ValueError, 'integrity'):
                        client.install(bad, self.cache, self.destination)
                self.assert_unpublished()

    def test_wrong_elf_architecture_class_or_magic_rejected(self):
        for contents in (elf(62), b'not ELF', b'\x7fELF\x01\x01' + bytes(30)):
            with self.subTest(contents=contents[:20]):
                self.replace_native_archive([('steamrtarm64/steam', contents)])
                with self.assertRaisesRegex(ValueError, 'ARM64'):
                    client.install(self.lock, self.cache, self.destination)
                self.assert_unpublished()

    def test_missing_native_executable_is_not_published(self):
        self.replace_native_archive([('other', b'not a native client')])
        with self.assertRaises((FileNotFoundError, ValueError)):
            client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_existing_install_never_repaired_or_overwritten(self):
        self.destination.mkdir(parents=True)
        sentinel = self.destination / 'user-data'
        sentinel.write_bytes(b'preserve this')
        with self.assertRaisesRegex(ValueError, 'exists'):
            client.install(self.lock, self.cache, self.destination)
        self.assertEqual(sentinel.read_bytes(), b'preserve this')
        self.assertEqual(list(self.destination.iterdir()), [sentinel])

    def test_low_disk_space_rejects_before_staging(self):
        with patch.object(client.shutil, 'disk_usage', return_value=Mock(free=0)):
            with self.assertRaisesRegex(ValueError, 'space'):
                client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_interrupted_extraction_cleans_staging(self):
        def interrupted(src, target, length):
            target.write(src.read(7))
            raise KeyboardInterrupt('simulated interruption')
        with patch.object(client.shutil, 'copyfileobj', side_effect=interrupted):
            with self.assertRaises(KeyboardInterrupt):
                client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_extraction_write_failure_cleans_staging(self):
        def no_space(src, target, length):
            target.write(src.read(3))
            raise OSError(28, 'simulated disk full')
        with patch.object(client.shutil, 'copyfileobj', side_effect=no_space):
            with self.assertRaises(OSError):
                client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_publish_error_cleans_staging(self):
        with patch.object(client, 'publish', side_effect=OSError('simulated publication failure')):
            with self.assertRaises(OSError):
                client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_conflicting_normalized_entries_rejected(self):
        self.archive([('steamrtarm64\\steam', b'different')], 'resources_all')
        with self.assertRaisesRegex(ValueError, 'conflict|overlap'):
            client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_atomic_publish_preserves_competing_empty_destination(self):
        stage = self.root / 'stage'
        stage.mkdir()
        (stage / 'private-data').write_bytes(b'do not replace')
        self.destination.mkdir(parents=True)
        with self.assertRaises(OSError):
            client.publish(stage, self.destination)
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual((stage / 'private-data').read_bytes(), b'do not replace')

    def test_destination_appearing_at_publication_is_retained_and_stage_removed(self):
        publish = client.publish
        def competing_destination(stage, destination):
            destination.mkdir()
            return publish(stage, destination)
        with patch.object(client, 'publish', side_effect=competing_destination):
            with self.assertRaises(OSError):
                client.install(self.lock, self.cache, self.destination)
        self.assertTrue(self.destination.is_dir())
        self.assertEqual(list(self.destination.iterdir()), [])
        self.assertEqual(list(self.destination.parent.glob('.steam-install-*')), [])

    def test_same_crc_and_size_do_not_prove_duplicate_byte_identity(self):
        # A genuine CRC32 collision, not mocked archive metadata.
        first, second = b'plumless', b'buckeroo'
        self.assertEqual(len(first), len(second))
        self.assertEqual(zlib.crc32(first), zlib.crc32(second))
        self.replace_native_archive([('steamrtarm64/steam', elf()), ('resources/collision', first)])
        self.archive([('resources/collision', second)], 'resources_all')
        with self.assertRaisesRegex(ValueError, 'conflict|duplicate|overlap'):
            client.install(self.lock, self.cache, self.destination)
        self.assert_unpublished()

    def test_lock_rejects_duplicate_component_even_with_different_filename(self):
        duplicate = copy.deepcopy(self.lock['parts'][0])
        duplicate['file'] = duplicate['component'] + '.zip.' + '1' * 40
        self.lock['parts'].append(duplicate)
        with self.assertRaises(ValueError):
            client.validate(self.lock)

    def manifest(self, extra='', version='1792192922'):
        part = self.lock['parts'][0]
        content = ('"linuxarm64" { "version" "' + version + '" '
                   '"' + part['component'] + '" { "file" "' + part['file'] + '" '
                   '"size" "' + str(part['size']) + '" "sha2" "' + part['sha256'] + '" } '
                   + extra + ' }')
        path = self.root / 'manifest.vdf'
        path.write_text(content, encoding='utf-8')
        return path

    def test_capture_pins_version_and_manifest_hash_and_selects_arm64_all_only(self):
        extra = ('"resources_all" { "file" "resources_all.zip.' + '2' * 40 + '" "size" "123" "sha2" "' + 'b' * 64 + '" } '
                 '"bins_linux64" { "file" "ignored" "size" "1" "sha2" "ignored" }')
        path = self.manifest(extra)
        lock = client.capture(path)
        self.assertEqual(lock['version'], '1792192922')
        self.assertEqual(lock['manifest_sha256'], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual([p['component'] for p in lock['parts']], ['bins_linuxarm64_linuxarm64', 'resources_all'])
        self.assertFalse(lock['redistribution_approved'])

    def test_manifest_duplicate_keys_and_invalid_version_fail(self):
        for path in (self.manifest('"version" "2"'),):
            with self.assertRaises(ValueError):
                client.capture(path)
        with self.assertRaises(ValueError):
            client.capture(self.manifest(version='latest'))

    def test_manifest_duplicate_root_and_broken_syntax_fail(self):
        for data in (b'"linuxarm64" {} "linuxarm64" {}', b'"root" {', b'"root" {} garbage'):
            with self.subTest(data=data), self.assertRaises(ValueError):
                client.parse_vdf(data)

    def test_download_verifies_mocked_https_bytes_and_reuses_cache_offline(self):
        path = self.cache / self.lock['parts'][0]['file']
        contents = path.read_bytes()
        path.unlink()
        opener = Mock()
        opener.open.return_value = io.BytesIO(contents)
        with patch.object(client.urllib.request, 'build_opener', return_value=opener):
            client.download(self.lock, self.cache)
        self.assertEqual(path.read_bytes(), contents)
        self.assertTrue(opener.open.call_args.args[0].startswith('https://'))
        with patch.object(client.urllib.request, 'build_opener', side_effect=AssertionError('cache must remain offline')):
            client.download(self.lock, self.cache)
        self.assertEqual(list(self.cache.glob('.steam-part-*')), [])

    def test_download_short_extra_wrong_hash_never_publish_and_remove_partial(self):
        path = self.cache / self.lock['parts'][0]['file']
        good = path.read_bytes()
        path.unlink()
        for content in (good[:-1], good + b'x', bytes(len(good))):
            with self.subTest(length=len(content)):
                opener = Mock()
                opener.open.return_value = io.BytesIO(content)
                with patch.object(client.urllib.request, 'build_opener', return_value=opener):
                    with self.assertRaises(ValueError):
                        client.download(self.lock, self.cache)
                self.assertFalse(path.exists())
                self.assertEqual(list(self.cache.iterdir()), [])

    def test_interrupted_download_cleans_partial(self):
        path = self.cache / self.lock['parts'][0]['file']
        path.unlink()
        src = Mock()
        src.__enter__ = Mock(return_value=src)
        src.__exit__ = Mock(return_value=False)
        src.read.side_effect = [b'some', KeyboardInterrupt()]
        opener = Mock()
        opener.open.return_value = src
        with patch.object(client.urllib.request, 'build_opener', return_value=opener):
            with self.assertRaises(KeyboardInterrupt):
                client.download(self.lock, self.cache)
        self.assertEqual(list(self.cache.iterdir()), [])

    def test_corrupt_cached_download_is_preserved_and_rejected_without_network(self):
        path = self.cache / self.lock['parts'][0]['file']
        original = path.read_bytes()
        corrupt = b'x' + original[1:]
        path.write_bytes(corrupt)
        with patch.object(client.urllib.request, 'build_opener', side_effect=AssertionError('no blind repair')):
            with self.assertRaisesRegex(ValueError, 'integrity'):
                client.download(self.lock, self.cache)
        self.assertEqual(path.read_bytes(), corrupt)

    def test_https_redirects_only_to_valve_cdn(self):
        request = urllib.request.Request(client.CDN + '/part.zip')
        handler = client.Redirect()
        for host in client.HOSTS:
            target = 'https://' + host + '/part.zip'
            redirected = handler.redirect_request(request, None, 302, 'Found', {}, target)
            self.assertEqual(redirected.full_url, target)
        for target in ('http://client-update.steamstatic.com/part', 'https://other.invalid/part',
                       'https://client-update.steamstatic.com.other.invalid/part',
                       'https://user:secret@client-update.steamstatic.com/part', 'file:///part'):
            with self.subTest(target=target), self.assertRaises(ValueError):
                handler.redirect_request(request, None, 302, 'Found', {}, target)


if __name__ == '__main__':
    unittest.main()
