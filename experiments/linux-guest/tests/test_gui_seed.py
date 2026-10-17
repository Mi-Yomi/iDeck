"""Offline snapshot provenance guards; fixtures do not claim VM acceptance."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import gui_seed as seed
import debian_rootfs as base


class SnapshotProvenance(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);self.vm=self.root/'vm';self.vm.mkdir()
        self.source=self.vm/'scratch-gui.raw';self.source.write_bytes(b'fixture')
        self.digest=base.sha256(self.source);self.lock=ROOT/'ipa/gui-inputs.lock.json'
        self.acceptance=self.root/'lab-acceptance'
        paths=[Path(seed.gui_vm.__file__),Path(seed.gui.__file__),Path(base.__file__),Path(seed.gui_host_tools.__file__),
               *sorted((ROOT/'guest/gui').iterdir())]
        self.prep={'host_only':True,'lock_sha256':base.sha256(self.lock),
                   'sources':{str(p.relative_to(ROOT)):base.sha256(p) for p in paths}}
        (self.vm/'preparation.json').write_text(json.dumps(self.prep))
        self.reports={}
        for name in ('provision','boot1','boot2'):
            report={'status':'pass','preparation':copy.deepcopy(self.prep),
                    'runner_sha256':base.sha256(Path(seed.check_gui_vm.__file__)),
                    'host_tools_sha256':base.sha256(Path(seed.gui_host_tools.__file__)),
                    'clean_unmount':True,'read_only_fsck':True,'qemu_exit':0,
                    'provision':name=='provision','package_configuration_verified':True,
                    'persistence_boot':name=='boot2','gui_mapped':True,'keyboard_input_verified':True,
                    'emulated_pointer_move_resize':True,'wheel_evdev_verified':True,
                    'real_root_menu_launch':True,'editor_typed_saved':name=='boot1',
                    'persistence_read_before_write':name=='boot2',
                    'editor_reopened_after_boot':name=='boot2','disk_sha256':self.digest}
            self.reports[name]=report
            (self.acceptance/name).mkdir(parents=True)
            (self.acceptance/name/'runner-source.py').write_bytes(Path(seed.check_gui_vm.__file__).read_bytes())
        self.save()
        for change in (patch.object(seed,'SOURCE_SIZE',7),
                       patch.object(base,'ext4_header',return_value={'uuid':seed.gui.UUID})):
            change.start();self.addCleanup(change.stop)

    def save(self):
        for name,report in self.reports.items():
            (self.acceptance/name/'result.json').write_text(json.dumps(report))

    def check(self,source=None,digest=None):
        return seed.accepted_snapshot(source or self.source,self.vm,self.acceptance,
                                      self.lock,digest or self.digest)

    def test_new_snapshot_with_bound_reports(self):
        result=self.check()
        self.assertEqual(result['source_snapshot_sha256'],self.digest)
        self.assertEqual(set(result['boot_reports']),{'provision','boot1','boot2'})

    def test_changed_hash_geometry_or_unrelated_disk_rejected(self):
        for digest in ('a'*64,'not-a-digest'):
            with self.subTest(digest=digest),self.assertRaises(ValueError):self.check(digest=digest)
        unrelated=self.root/'userdata.raw';unrelated.write_bytes(b'fixture')
        with self.assertRaises(ValueError):self.check(source=unrelated)
        self.source.write_bytes(b'fixture-extra')
        with self.assertRaises(ValueError):self.check()
        self.assertEqual(unrelated.read_bytes(),b'fixture')

    def test_boot2_must_cover_exact_frozen_disk(self):
        self.reports['boot2']['disk_sha256']='a'*64;self.save()
        with self.assertRaisesRegex(ValueError,'different snapshot'):self.check()

    def test_failure_dirty_stop_stale_runner_or_missing_input_evidence(self):
        mutations=[('boot1','status','failed'),('boot2','clean_unmount',False),
                   ('boot2','read_only_fsck',False),('boot2','forced_termination',True),
                   ('boot2','qemu_exit',1),('boot1','runner_sha256','a'*64),
                   ('boot1','emulated_pointer_move_resize',False),
                   ('boot2','persistence_read_before_write',False),
                   ('boot2','editor_reopened_after_boot',False),
                   ('provision','package_configuration_verified',False)]
        original=copy.deepcopy(self.reports)
        for name,key,value in mutations:
            with self.subTest(name=name,key=key):
                self.reports=copy.deepcopy(original)
                self.reports[name][key]=value;self.save()
                with self.assertRaises(ValueError):self.check()

    def test_stale_package_lock_or_preparation_source_rejected(self):
        for key in ('sources','lock_sha256'):
            prep=copy.deepcopy(self.prep);prep[key]={} if key=='sources' else 'a'*64
            (self.vm/'preparation.json').write_text(json.dumps(prep))
            with self.subTest(key=key),self.assertRaises(ValueError):self.check()

    def test_missing_or_symlink_receipt_rejected(self):
        path=self.acceptance/'boot2/result.json';path.unlink()
        with self.assertRaises(ValueError):self.check()
        path.symlink_to(self.acceptance/'boot1/result.json')
        with self.assertRaises(ValueError):self.check()

    def test_provisioning_can_keep_reviewed_gui_only_runner_difference(self):
        archived=self.acceptance/'provision/runner-source.py'
        text=archived.read_text().replace("report['gui_mapped']=True", "report['gui_mapped']=False")
        archived.write_text(text)
        self.reports['provision']['runner_sha256']=base.sha256(archived);self.save()
        self.check()  # Provisioning never executes that GUI-only branch.
        text=archived.read_text().replace('seconds=1800','seconds=1801');archived.write_text(text)
        self.reports['provision']['runner_sha256']=base.sha256(archived);self.save()
        with self.assertRaisesRegex(ValueError,'provisioning code changed'):self.check()

    def test_common_shutdown_change_or_runner_tampering_is_rejected(self):
        archived=self.acceptance/'provision/runner-source.py'
        archived.write_text(archived.read_text().replace("'-fn'", "'-fy'"))
        with self.assertRaisesRegex(ValueError,'changed archived'):self.check()
        self.reports['provision']['runner_sha256']=base.sha256(archived);self.save()
        with self.assertRaisesRegex(ValueError,'provisioning code changed'):self.check()

    def test_extra_top_level_code_is_not_hidden_by_gui_projection(self):
        archived=self.acceptance/'provision/runner-source.py'
        archived.write_text(archived.read_text()+'\nbase.OFFLINE=False\n')
        self.reports['provision']['runner_sha256']=base.sha256(archived);self.save()
        with self.assertRaisesRegex(ValueError,'provisioning code changed'):self.check()
