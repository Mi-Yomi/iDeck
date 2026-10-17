"""GUI transport/acceptance guards. Small fixtures never claim a guest boot."""
import contextlib
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tarfile
import tempfile
import unittest
import urllib.error
from unittest.mock import patch,Mock

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'));sys.path.insert(0,str(ROOT.parents[1]/'ci'))
import gui_bundle as bundle
import seal_gui_payload
import build_linux_probe_ipa as build
import check_build_request
import gui_bootstrap


class GUITransport(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'source';self.source.mkdir()
        self.data={name:(name+' fixture\n').encode() for name in bundle.NAMES}
        for name,data in self.data.items():(self.source/name).write_bytes(data)
        self.addCleanup(patch.stopall)
        patch.object(bundle,'ROOTFS_SIZE',len(self.data[bundle.ROOTFS])).start()
        patch.object(bundle,'KERNEL_SHA256',hashlib.sha256(self.data['vmlinuz-virt']).hexdigest()).start()
        self.transport={name:data for name,data in self.data.items() if name!=bundle.ROOTFS}
        self.transport[bundle.ROOTFS+'.gz']=gzip.compress(self.data[bundle.ROOTFS],mtime=0)
        self.lock={'schema':1,'kind':'ideck-debian-gui','status':'ready',
                   'files':{name:bundle.metadata(self.source/name) for name in bundle.NAMES},
                   'acceptance':{'kind':'production-alpine-two-boots','matching_kernel_gui':True,'two_boots_clean':True,
                                 'kernel_sha256':bundle.KERNEL_SHA256,'report_sha256':'a'*64,
                                 'rootfs_sha256':hashlib.sha256(self.data[bundle.ROOTFS]).hexdigest(),
                                 'initramfs_sha256':hashlib.sha256(self.data['initramfs-desktop.gz']).hexdigest()}}
        self.archive=self.root/'ideck-debian-gui-v1.tar';self.lockpath=self.root/'lock.json';self.write_archive()

    def write_archive(self,special=None):
        with tarfile.open(self.archive,'w',format=tarfile.USTAR_FORMAT) as tar:
            for name,data in sorted(self.transport.items()):
                entry=tarfile.TarInfo(name);entry.size=len(data)
                if special and name=='vmlinuz-virt':special(entry)
                tar.addfile(entry,io.BytesIO(data) if entry.isfile() else None)
        self.lock['transport_files']={name:{'size':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in self.transport.items()}
        self.lock['payload']={'filename':self.archive.name,**bundle.metadata(self.archive)}
        self.lockpath.write_text(json.dumps(self.lock))

    def test_exact_restore_stage_and_incremental_rebuild(self):
        restored=self.root/'restored';bundle.restore(self.archive,restored,self.lockpath)
        target=self.root/'App.app/iDeckLinuxDesktop'
        for _ in range(2):bundle.stage(restored,target,self.lockpath)
        self.assertEqual({p.name:p.read_bytes() for p in target.iterdir()},self.data)
        with self.assertRaises(ValueError):bundle.restore(self.archive,restored,self.lockpath)

    def test_gate_cannot_accept_other_kernel_root_initrd_or_unverified_boots(self):
        for field in ('matching_kernel_gui','two_boots_clean','kernel_sha256','rootfs_sha256','initramfs_sha256','report_sha256'):
            good=self.lock['acceptance'][field];self.lock['acceptance'][field]=False
            self.lockpath.write_text(json.dumps(self.lock));destination=self.root/field
            with self.assertRaises(ValueError):bundle.restore(self.archive,destination,self.lockpath)
            self.assertFalse(destination.exists());self.lock['acceptance'][field]=good

    def test_missing_corrupt_extra_symlink_and_wrong_archive_bytes(self):
        root=self.source/bundle.ROOTFS;data=root.read_bytes();root.write_bytes(b'x'*len(data))
        with self.assertRaises(ValueError):bundle.verify(self.source,self.lock)
        root.unlink();root.symlink_to(self.source/'vmlinuz-virt')
        with self.assertRaises(ValueError):bundle.verify(self.source,self.lock)
        root.unlink();root.write_bytes(data);(self.source/'extra').write_bytes(b'x')
        with self.assertRaises(ValueError):bundle.verify(self.source,self.lock)
        self.archive.write_bytes(self.archive.read_bytes()+b'x')
        with self.assertRaises(ValueError):bundle.restore(self.archive,self.root/'bad',self.lockpath)
        self.assertFalse((self.root/'bad').exists())

    def test_gzip_bounds_and_raw_digest_required(self):
        for i,data in enumerate((b'x'*len(self.data[bundle.ROOTFS]),b'x'*10000)):
            self.transport[bundle.ROOTFS+'.gz']=gzip.compress(data);self.write_archive()
            with self.assertRaises(ValueError):bundle.restore(self.archive,self.root/str(i),self.lockpath)

    def test_no_links_traversal_symlink_ancestors_or_low_space(self):
        for i,special in enumerate((lambda x:setattr(x,'type',tarfile.SYMTYPE),lambda x:setattr(x,'name','../escape'))):
            self.write_archive(special)
            with self.assertRaises(ValueError):bundle.restore(self.archive,self.root/str(i),self.lockpath)
            self.assertFalse((self.root/str(i)).exists())
        self.write_archive()
        with patch.object(bundle.shutil,'disk_usage',return_value=Mock(free=0)):
            with self.assertRaisesRegex(ValueError,'space'):bundle.restore(self.archive,self.root/'full',self.lockpath)
        self.assertEqual(list((self.root/'full').iterdir()),[])
        alias=self.root/'alias';alias.symlink_to(self.source,target_is_directory=True)
        with self.assertRaises(ValueError):bundle.restore(self.archive,alias/'new',self.lockpath)
        self.assertFalse((self.source/'new').exists())

    def test_size_rejected_before_hash_reads(self):
        path=self.source/bundle.ROOTFS;path.write_bytes(b'wrong length')
        with patch.object(bundle,'metadata',side_effect=AssertionError('must not hash an oversized file')):
            with self.assertRaises(ValueError):bundle.checked(path,self.lock['files'][bundle.ROOTFS])

    def test_private_fetch_failure_redacts_url_token_and_body(self):
        secret='fixture-token-never-live';url='https://api.github.com/repos/Mi-Yomi/iDeck/releases/assets/123'
        error=urllib.error.HTTPError(url+'?'+secret,401,secret,{},io.BytesIO(secret.encode()))
        output=io.StringIO();diagnostic={}
        with patch.dict(os.environ,{'IDECK_GUI_PAYLOAD_URL':url,'IDECK_GUI_PAYLOAD_TOKEN':secret}),\
                patch.object(bundle.urllib.request,'build_opener') as network,contextlib.redirect_stdout(output):
            network.return_value.open.side_effect=error
            with self.assertRaises(bundle.FetchError):bundle.fetch(self.root/'download',self.lockpath,diagnostic=diagnostic)
        self.assertEqual(diagnostic['http_status'],401);self.assertEqual(diagnostic['received_bytes'],0)
        self.assertNotIn(secret,output.getvalue());self.assertNotIn(url,output.getvalue())
        self.assertFalse((self.root/'download').exists())


class ProductionGUIBlocking(unittest.TestCase):
    def test_ready_lock_is_bound_to_real_original_kernel_acceptance(self):
        lock=bundle.load_lock(ROOT/'ipa/gui.lock.json')
        receipt=ROOT/'evidence/gui-alpine-20261017/acceptance.json'
        self.assertEqual(lock['status'],'ready')
        self.assertEqual(hashlib.sha256(receipt.read_bytes()).hexdigest(),lock['acceptance']['report_sha256'])
        gate=json.loads(receipt.read_text())
        self.assertTrue(gate['matching_kernel_gui']);self.assertTrue(gate['two_boots_clean'])
        self.assertTrue(gate['machine_id_persisted'])
        self.assertEqual(gate['rootfs_sha256'],lock['files'][bundle.ROOTFS]['sha256'])
        self.assertEqual(gate['kernel_sha256'],bundle.KERNEL_SHA256)

    def test_pending_lock_fails_without_fetch_or_native_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);experiment=root/'experiment';(experiment/'ipa').mkdir(parents=True)
            lock=experiment/'ipa/gui.lock.json';lock.write_text('{"schema":1,"kind":"ideck-debian-gui","status":"blocked"}')
            with self.assertRaisesRegex(ValueError,'matching-kernel'):bundle.load_lock(lock)
            with patch.object(build,'ROOT',root),patch.object(build.platform,'system',return_value='Darwin'),\
                    patch.object(build,'EXPERIMENT',experiment),\
                    patch.object(build,'Worker') as worker,patch.object(check_build_request,'main'),\
                    patch.dict(os.environ,{'IDECK_WORKFLOW_ID':'ideck-linux-probe-ipa','NATIVE_BUILD_APPROVED':'true'}),\
                    patch.object(bundle.urllib.request,'build_opener') as network,contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError,'matching-kernel'):build.main()
            worker.assert_not_called();network.assert_not_called()
            result=json.loads((root/'.work/linux-ipa/result.json').read_text())
            self.assertFalse(result['ipa_created']);self.assertEqual(result['status'],'failed')

    def test_sealing_requires_real_receipt_before_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);seed=root/'seed';seed.mkdir();gate=root/'gate';gate.mkdir()
            (gate/'acceptance.json').write_text('{"status":"not-run"}')
            (seed/'gui-seed.json').write_text('{}')
            with self.assertRaisesRegex(ValueError,'matching-kernel'):
                seal_gui_payload.seal(seed,root/'bootstrap',gate,root/'modules',root/'sealed')
            self.assertFalse((root/'sealed').exists())

    def test_lock_read_is_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'lock';path.write_bytes(b' '*131073)
            with self.assertRaisesRegex(ValueError,'lock'):bundle.load_lock(path)

    def test_self_asserted_module_provenance_cannot_replace_original_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);modules=root/'modules';modules.mkdir()
            manifest=json.loads((ROOT/'evidence/local-debian-ext4-modules.json').read_text())
            manifest['modules'][0]['sha256']='0'*64
            (modules/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'pinned closure'):gui_bootstrap.prepare(root/'out',modules)
            self.assertFalse((root/'out').exists())
