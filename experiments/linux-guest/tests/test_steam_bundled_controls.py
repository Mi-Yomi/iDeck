"""Offline synthetic cache fixtures; real cache acceptance is a separate receipt."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import steam_bundled_cache as bundle
import steam_offline_cache as packer


class BundledCache(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.body = b'original synthetic package fixture'
        self.rows = [dict(r, size=len(self.body), sha256=hashlib.sha256(self.body).hexdigest()) for r in packer.pins()]
        for group in ('client', 'debs'): (self.root / group).mkdir()
        for row in self.rows: (self.root / row['name']).write_bytes(self.body)
        self.archive = self.root / 'fixture.tar'
        report = packer.pack(self.root / 'client', self.root / 'debs', self.archive, self.rows)
        self.lock = copy.deepcopy(bundle.load_lock(ROOT / 'ipa/steam-cache.lock.json'))
        self.lock.update(entries=self.rows, archive={key:report[key] for key in ('size','sha256')})
        self.lock['payload_url'] = 'https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123'
        self.lock_path = self.root / 'fixture.lock.json'; self.save()
        self.output = self.root / 'bundle'

    def save(self): self.lock_path.write_text(json.dumps(self.lock))

    def test_real_sealed_metadata_matches_current_pins_and_swift_digest(self):
        lock = bundle.load_lock(ROOT / 'ipa/steam-cache.lock.json')
        self.assertEqual(lock['entries'], packer.pins())
        self.assertEqual(lock['archive']['size'], 379228160)
        for name, pin in lock['source_inputs'].items():
            raw = (ROOT / name).read_bytes()
            self.assertEqual({'size':len(raw),'sha256':hashlib.sha256(raw).hexdigest()}, pin)
        self.assertIn(lock['archive']['sha256'], (ROOT/'ios/LinuxSteamOfflineCache.swift').read_text())

    def test_stage_verify_repeat_exact_resources_and_no_replacement(self):
        result = bundle.stage(self.archive, self.output, self.lock_path)
        inode = (self.output / bundle.FILENAME).stat().st_ino
        self.assertEqual(result['parts'],62)
        self.assertEqual(bundle.stage(self.archive,self.output,self.lock_path),result)
        self.assertEqual((self.output / bundle.FILENAME).stat().st_ino,inode)
        self.assertEqual((self.output / bundle.FILENAME).read_bytes(), self.archive.read_bytes())
        self.assertEqual(set(p.name for p in self.output.iterdir()),{bundle.FILENAME,bundle.MANIFEST})

    def test_corrupt_input_is_refused_before_destination_exists(self):
        raw = bytearray(self.archive.read_bytes()); raw[512] ^= 1; self.archive.write_bytes(raw)
        with self.assertRaisesRegex(ValueError,'SHA-256'): bundle.stage(self.archive,self.output,self.lock_path)
        self.assertFalse(self.output.exists())

    def test_new_outer_hash_cannot_hide_invalid_canonical_header_or_tail(self):
        original = self.archive.read_bytes()
        for offset in (0, 156, len(original)-1):
            raw = bytearray(original); raw[offset] ^= 1; self.archive.write_bytes(raw)
            self.lock['archive']['sha256'] = hashlib.sha256(raw).hexdigest(); self.save()
            with self.assertRaises(ValueError): bundle.stage(self.archive,self.output,self.lock_path)
        self.assertFalse(self.output.exists())

    def test_corrupt_existing_bundle_is_preserved_and_refused(self):
        bundle.stage(self.archive,self.output,self.lock_path)
        output = self.output / bundle.FILENAME; output.write_bytes(b'preserve bad existing resource')
        with self.assertRaises(ValueError): bundle.stage(self.archive,self.output,self.lock_path)
        self.assertEqual(output.read_bytes(), b'preserve bad existing resource')

    def test_links_extra_members_and_wrong_manifest_refused(self):
        link = self.root / 'alias.tar'; link.symlink_to(self.archive)
        with self.assertRaises(ValueError): bundle.stage(link,self.output,self.lock_path)
        link.unlink(); os.link(self.archive,link)
        with self.assertRaises(ValueError): bundle.stage(link,self.output,self.lock_path)
        link.unlink()
        bundle.stage(self.archive,self.output,self.lock_path)
        extra = self.output / 'extra'; extra.write_bytes(b'not allowed')
        with self.assertRaises(ValueError): bundle.verify(self.output,self.lock_path)
        extra.unlink(); (self.output/bundle.MANIFEST).write_bytes(b'{}')
        with self.assertRaises(ValueError): bundle.verify(self.output,self.lock_path)

    def test_unreviewed_asset_urls_and_scope_rejected(self):
        for url in ('https://example.test/cache.tar','https://api.github.com/repos/other/repo/releases/assets/123',
                    'http://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123',self.lock['payload_url']+'?token=no'):
            self.lock['payload_url']=url; self.save()
            with self.assertRaises(ValueError): bundle.load_lock(self.lock_path)
        self.lock.pop('payload_url'); self.lock['client_executed']=True; self.save()
        with self.assertRaises(ValueError): bundle.load_lock(self.lock_path)

    def test_missing_delivery_fails_before_fetch_and_local_verified_file_can_stage(self):
        self.lock.pop('payload_url'); self.save()
        with patch.dict(os.environ,{},clear=True),patch('steam_bundle.fetch',side_effect=AssertionError):
            with self.assertRaisesRegex(ValueError,'STEAM_BUNDLED_CACHE_ASSET_NOT_UPLOADED'):
                bundle.prepare_for_build(self.output,self.lock_path,self.root)
        with patch.dict(os.environ,{'IDECK_STEAM_CACHE_FILE':str(self.archive)},clear=True):
            self.assertEqual(bundle.prepare_for_build(self.output,self.lock_path,self.root)['parts'],62)

    def test_ci_fetch_uses_existing_payload_transport_and_exact_pin(self):
        def fetch(destination,lock):
            self.assertEqual(lock,self.lock)
            self.assertEqual(os.environ['IDECK_DEBIAN_PAYLOAD_TOKEN'],'synthetic-fixture-value')
            shutil.copyfile(self.archive,destination)
        with patch.dict(os.environ,{'IDECK_DEBIAN_PAYLOAD_TOKEN':'synthetic-fixture-value'},clear=True),patch('steam_bundle.fetch',side_effect=fetch) as call:
            bundle.prepare_for_build(self.output,self.lock_path,self.root)
        call.assert_called_once()

    def test_standalone_xcode_stage_uses_real_shared_format_without_file_digest(self):
        scripts=self.root/'scripts';scripts.mkdir()
        shutil.copyfile(ROOT/'tools/steam_bundled_cache.py',scripts/'ideck-stage-steam-cache.py')
        shutil.copyfile(ROOT/'guest/steam-offline-cache.py',scripts/'ideck-steam-cache-format.py')
        wrapper="import hashlib,runpy,sys;hashlib.__dict__.pop('file_digest',None);sys.argv=sys.argv[1:];runpy.run_path(sys.argv[0],run_name='__main__')"
        args=[sys.executable,'-I','-B','-c',wrapper,str(scripts/'ideck-stage-steam-cache.py'),'stage',str(self.archive),str(self.lock_path),'--destination',str(self.output)]
        for _ in range(2): subprocess.run(args,check=True,capture_output=True)
        self.assertEqual(bundle.verify(self.output,self.lock_path)['parts'],62)

    def test_mandatory_apple_fixtures_and_runtime_routes_are_connected(self):
        ci=(ROOT.parents[1]/'ci/check_linux_guest_profile.py').read_text()
        for marker in ('LINUX_STEAM_SCREEN_CONTROLS_PASS','LINUX_STEAM_BUNDLED_CACHE_PASS'):
            self.assertIn(marker,ci)
        for source in ('LinuxSteamControlsState.swift','LinuxSteamControlsView.swift','SteamControlsChecks.swift','SteamBundledChecks.swift'):
            self.assertIn(source,ci)
        worker=(ROOT/'ios/LinuxTerminalSession.swift').read_text()
        self.assertLess(worker.index('LinuxSteamOfflineCache.prepareBundled('),worker.index('self.disk = try steam.openExisting'))
        self.assertIn('checkpoint: { try self.preparation.advance(.assets) }',worker)
        desktop=(ROOT/'ios/LinuxDesktopView.swift').read_text()
        self.assertIn('input.releaseScreenControls(); showScreenControls.toggle()',desktop)
        self.assertIn('.onDisappear { keyboard = false; input.setFocused(false) }',desktop)
        source=(ROOT/'ios/LinuxDesktopInput.swift').read_text()
        self.assertIn('screen.releaseAll(); emit(state.releaseAll())',source)
        self.assertNotIn('husk_gamepad_',source)


if __name__=='__main__': unittest.main()
