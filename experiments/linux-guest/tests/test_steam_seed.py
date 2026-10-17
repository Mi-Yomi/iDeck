"""Synthetic provenance fault fixtures; no disk/VM acceptance is claimed here."""
from contextlib import ExitStack
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
import steam_seed
import steam_vm


def digest(data): return hashlib.sha256(data).hexdigest()


class SeedContractFixtures(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.ev=self.root/'evidence/fixture'
        self.ev.mkdir(parents=True);(self.root/'profiles').mkdir();(self.root/'ipa').mkdir()
        self.seed=self.root/'seed.raw';self.seed.write_bytes(b'private experimental fixture')
        self.kernel=self.root/'kernel';self.kernel.write_bytes(b'kernel fixture')
        self.bootstrap=self.root/'bootstrap';self.bootstrap.mkdir()
        (self.bootstrap/'initramfs-steam.gz').write_bytes(b'steam bootstrap fixture')
        def pin(path):return {'size':path.stat().st_size,'sha256':digest(path.read_bytes())}
        self.seed_pin=pin(self.seed);self.kernel_pin=pin(self.kernel)
        self.gui_pin={'size':8,'sha256':digest(b'GUI base')}
        self.steam_pin=pin(self.bootstrap/'initramfs-steam.gz')
        self.profile=json.loads((ROOT/'profiles/steam-host-experiment.json').read_text())
        self.write(self.root/'profiles/steam-host-experiment.json',self.profile)
        self.write(self.root/'ipa/gui.lock.json',{'files':{
            'gui-rootfs-v1.raw':{'size':10,'sha256':digest(b'production')},
            'vmlinuz-virt':self.kernel_pin,'initramfs-desktop.gz':self.gui_pin}})
        for name in ['gui-inputs','steam-client','steam-dependencies']:
            self.write(self.root/('ipa/'+name+'.lock.json'),{'unit_fixture':name})
        bindings={n:digest((self.root/n).read_bytes()) for n in steam_seed.BINDINGS}
        self.write(self.bootstrap/'bootstrap.json',{'base_initramfs':self.gui_pin,
            'initramfs':self.steam_pin,'required_kernel_sha256':self.kernel_pin['sha256'],
            'original_shutdown_function_preserved':True,'gui_payload_changed':False,'valve_client_bundled':False})
        base=self.ev/'gui-bootstrap.json';self.write(base,{'kernel':self.kernel_pin,'initramfs':self.gui_pin})
        self.artifacts={'gui-bootstrap.json':base}
        boots={};strict={}
        for name in ['boot1','boot2']:
            folder=self.ev/name;folder.mkdir();runner=folder/'runner-source.py'
            runner.write_bytes(b'# fixture runner; never executed\n')
            report={'host_only':True,'production_bootstrap':True,'gui_mapped':True,
                'keyboard_input_verified':True,'emulated_pointer_move_resize':True,
                'wheel_evdev_verified':True,'real_root_menu_launch':True,'clean_unmount':True,
                'read_only_fsck':True,'qemu_exit':0,'persistence_boot':name=='boot2',
                'preparation':{'kernel_sha256':self.kernel_pin['sha256'],'initramfs_sha256':self.gui_pin['sha256']},
                'runner_sha256':digest(runner.read_bytes()),'machine_id_sha256':'a'*64,
                'persistence_read_before_write':name=='boot2','editor_reopened_after_boot':name=='boot2'}
            self.write(folder/'result.json',report)
            for f in [runner,folder/'result.json']:self.artifacts[f.relative_to(self.ev).as_posix()]=f
            boots[name]={'report':name+'/result.json','runner':name+'/runner-source.py'}
        for name in ['boot1','boot2','seed']:
            folder=self.ev/name;folder.mkdir(exist_ok=True);target='/fixture/'+name+'.raw'
            stdout=('Pass 1: Checking inodes, blocks, and sizes\nPass 2: Checking directory structure\n'
                'Pass 3: Checking directory connectivity\nPass 4: Checking reference counts\n'
                'Pass 5: Checking group summary information\n'+target+': 12/100 files (0.4% non-contiguous), 30/200 blocks\n')
            stderr='e2fsck 1.47.2 (1-Jan-2025)\n'
            (folder/'stdout.log').write_text(stdout);(folder/'stderr.log').write_text(stderr)
            checksum=self.seed_pin['sha256'] if name=='seed' else digest(name.encode())
            self.write(folder/'fsck.json',{'command':['e2fsck','-f','-n',target],'exit_code':0,
                'read_only':True,'writer_running':False,'host_fsync':True,
                'raw_sha256_before':checksum,'raw_sha256_after':checksum,
                'evaluation':steam_vm.evaluate_offline_fsck(0,stdout,stderr,target)})
            strict[name]={'report':name+'/fsck.json','stdout':name+'/stdout.log','stderr':name+'/stderr.log'}
            for f in strict[name].values():self.artifacts[f]=self.ev/f
        identity={'file':'gui-rootfs-v1.raw',**self.seed_pin}
        self.write(self.ev/'seed.json',{'schema':1,'mode':'gui-seed','rootfs':identity,
            'read_only_fsck':True,'app_payload_ready':False,'gui_package_lock_sha256':bindings['ipa/gui-inputs.lock.json']})
        self.accepted={'schema':1,'kind':'production-alpine-two-boots','status':'pass','matching_kernel_gui':True,
            'two_boots_clean':True,'machine_id_persisted':True,'rootfs_sha256':self.seed_pin['sha256'],
            'kernel_sha256':self.kernel_pin['sha256'],'initramfs_sha256':self.gui_pin['sha256'],
            'gui_package_lock_sha256':bindings['ipa/gui-inputs.lock.json'],
            'bootstrap_receipt_sha256':digest(base.read_bytes()),'boot_reports':{},'ios_compiled':False,'device_verified':False}
        self.completed={'schema':1,'status':'pass','scope':'separate experimental seed only','seed':identity,
            'production_gui_lock_unchanged':True,'production_seed_replaced':False,'seed_published':False,
            'task_qemu_remaining':False,'security_or_network_settings_changed':False}
        self.c={'schema':1,'kind':'private-steam-experimental-seed','id':steam_seed.CONTRACT_ID,
            'host_only':True,'app_route_enabled':False,'production_gui_override':False,'seed':self.seed_pin,
            'kernel':self.kernel_pin,'gui_initramfs':self.gui_pin,'steam_bootstrap':self.steam_pin,
            'steam_bootstrap_receipt':pin(self.bootstrap/'bootstrap.json'),'repository_bindings':bindings,
            'provenance':{'manifest':{},'seed_receipt':'seed.json','acceptance':'acceptance.json','completion':'completion.json',
                'gui_bootstrap_receipt':{'path':'evidence/fixture/gui-bootstrap.json',**pin(base)},
                'boot_reports':boots,'strict_checks':strict}}
        self.contract=self.root/steam_seed.CONTRACT
        for name in ['seed.json','acceptance.json','completion.json']:self.artifacts[name]=self.ev/name
        self.rebind()
        self.addCleanup(patch.stopall)
        patch.object(steam_seed,'ROOT',self.root).start();patch.object(steam_vm,'ROOT',self.root).start()

    def write(self,path,value):path.write_text(json.dumps(value,indent=2)+'\n')

    def rebind(self):
        for name in ['boot1','boot2']:
            self.accepted['boot_reports'][name]=digest((self.ev/name/'result.json').read_bytes())
        self.write(self.ev/'acceptance.json',self.accepted)
        self.completed['alpine_acceptance']=copy.deepcopy(self.accepted)
        self.write(self.ev/'completion.json',self.completed)
        entries=[{'path':n,'size':p.stat().st_size,'sha256':digest(p.read_bytes())} for n,p in sorted(self.artifacts.items())]
        mp=self.ev/'manifest.json';self.write(mp,{'schema':1,'files':entries})
        self.c['provenance']['manifest']={'path':'evidence/fixture/manifest.json','size':mp.stat().st_size,'sha256':digest(mp.read_bytes())}
        self.write(self.contract,self.c)

    def validate(self):
        return steam_seed.validate(self.contract,self.seed,self.kernel,self.bootstrap,steam_vm.evaluate_offline_fsck,
                                   runner_source=steam_vm.RUNNER_SOURCE)

    def test_configuration_is_deterministic_and_does_not_override_production(self):
        first=self.validate();second=self.validate()
        self.assertEqual(first,second);self.assertEqual(first['configuration_sha256'],second['configuration_sha256'])
        self.assertFalse(first['production_gui_override']);self.assertEqual(first['seed'],self.seed_pin)

    def test_contract_scope_and_schema_cannot_be_promoted_or_coerced(self):
        for key,value in [('schema',True),('host_only',False),('app_route_enabled',True),
                          ('production_gui_override',True),('id','unreviewed')]:
            with self.subTest(key=key):
                changed={**self.c,key:value};self.write(self.contract,changed)
                with self.assertRaisesRegex(ValueError,'contract scope'):self.validate()
        self.write(self.contract,self.c)

    def test_explicit_continuation_requires_same_contract_and_preserves_source(self):
        source=self.root/'old-run';source.mkdir()
        (source/'owner.lock').touch();(source/'steam-experiment.qcow2').write_bytes(b'unchanged private progress')
        r={'host_only':True,'clean_shutdown':True,'qemu_exit_code':0,'seed_sha256':self.seed_pin['sha256']}
        for old_contract in [None,{},'wrong',{'contract_sha256':'wrong'}]:
            self.write(source/'result.json',{**r,'seed_contract':old_contract})
            with self.assertRaisesRegex(ValueError,'contract differs'):
                steam_vm.validate_continuation(source,self.seed_pin['sha256'],'required-hash')
        self.write(source/'result.json',{**r,'seed_contract':{'contract_sha256':'required-hash'}})
        self.assertEqual(steam_vm.validate_continuation(source,self.seed_pin['sha256'],'required-hash'),source/'steam-experiment.qcow2')
        self.assertEqual((source/'steam-experiment.qcow2').read_bytes(),b'unchanged private progress')

    def test_same_size_wrong_seed_is_refused(self):
        before=self.seed.read_bytes();self.seed.write_bytes(b'X'+before[1:])
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):self.validate()

    def test_symlinked_seed_or_contract_is_refused(self):
        for path in [self.seed,self.contract]:
            with self.subTest(path=path):
                original=path.with_suffix('.actual');path.rename(original);path.symlink_to(original)
                with self.assertRaisesRegex(ValueError,'symlink'):self.validate()
                path.unlink();original.rename(path)

    def test_external_self_asserted_contract_is_refused(self):
        external=self.root/'unreviewed.json';external.write_bytes(self.contract.read_bytes())
        with self.assertRaisesRegex(ValueError,'unreviewed'):
            steam_seed.validate(external,self.seed,self.kernel,self.bootstrap,steam_vm.evaluate_offline_fsck,
                                runner_source=steam_vm.RUNNER_SOURCE)

    def test_kernel_and_bootstrap_tampering_is_refused(self):
        for path in [self.kernel,self.bootstrap/'initramfs-steam.gz',self.bootstrap/'bootstrap.json']:
            with self.subTest(path=path):
                original=path.read_bytes();path.write_bytes(original+b'x')
                with self.assertRaisesRegex(ValueError,'integrity mismatch'):self.validate()
                path.write_bytes(original)

    def test_profile_or_gui_lock_change_is_refused(self):
        for name in ['profiles/steam-host-experiment.json','ipa/gui.lock.json']:
            path=self.root/name;original=path.read_bytes();path.write_bytes(original+b' ')
            with self.assertRaisesRegex(ValueError,'repository binding'):self.validate()
            path.write_bytes(original)

    def test_evidence_corruption_missing_and_symlink_are_refused(self):
        path=self.ev/'boot1/stdout.log';original=path.read_bytes()
        path.write_bytes(original+b'unknown output')
        with self.assertRaisesRegex(ValueError,'integrity mismatch'):self.validate()
        path.unlink()
        with self.assertRaises(ValueError):self.validate()
        target=self.ev/'outside';target.write_bytes(original);path.symlink_to(target)
        with self.assertRaisesRegex(ValueError,'symlink'):self.validate()

    def test_manifest_traversal_and_duplicate_entries_are_refused(self):
        mp=self.ev/'manifest.json';original=json.loads(mp.read_text())
        for name in ['../escape','/outside','a//b']:
            m=copy.deepcopy(original);m['files'][0]['path']=name;self.write(mp,m)
            self.c['provenance']['manifest'].update(size=mp.stat().st_size,sha256=digest(mp.read_bytes()));self.write(self.contract,self.c)
            with self.assertRaises(ValueError):self.validate()
        m=copy.deepcopy(original);m['files'].append(m['files'][0]);self.write(mp,m)
        self.c['provenance']['manifest'].update(size=mp.stat().st_size,sha256=digest(mp.read_bytes()));self.write(self.contract,self.c)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.validate()

    def test_self_asserted_failed_acceptance_is_refused_even_when_rehashed(self):
        self.accepted['status']='failed';self.rebind()
        with self.assertRaisesRegex(ValueError,'Alpine acceptance'):self.validate()

    def test_wrong_builder_seed_identity_is_refused_even_when_rehashed(self):
        p=self.ev/'seed.json';r=json.loads(p.read_text());r['rootfs']['sha256']='0'*64;self.write(p,r);self.rebind()
        with self.assertRaisesRegex(ValueError,'builder receipt'):self.validate()

    def test_forced_or_unclean_boot_is_refused_even_when_rehashed(self):
        p=self.ev/'boot2/result.json';r=json.loads(p.read_text());r['forced_termination']=True;self.write(p,r);self.rebind()
        with self.assertRaisesRegex(ValueError,'real boot acceptance'):self.validate()

    def test_machine_id_must_really_match(self):
        p=self.ev/'boot2/result.json';r=json.loads(p.read_text());r['machine_id_sha256']='b'*64;self.write(p,r);self.rebind()
        with self.assertRaisesRegex(ValueError,'machine ID'):self.validate()

    def test_full_fsck_output_rechecked_instead_of_trusting_pass_boolean(self):
        p=self.ev/'seed/stdout.log';p.write_text(p.read_text()+'Optimize? no\n');self.rebind()
        with self.assertRaisesRegex(ValueError,'full-output fsck'):self.validate()

    def test_default_runner_rejects_experimental_seed_without_explicit_contract(self):
        args=SimpleNamespace(seed=self.seed,kernel=self.kernel,bootstrap=self.bootstrap)
        with ExitStack() as cleanup,patch.object(steam_vm.subprocess,'run',side_effect=AssertionError('no image writes')):
            with self.assertRaisesRegex(ValueError,'accepted GUI input differs'):
                steam_vm._boot(args,self.root/'profiles/steam-host-experiment.json',self.profile,self.root/'output',{},cleanup)

    def test_insufficient_space_stops_runner_before_image_tools_or_disk_write(self):
        args=SimpleNamespace(seed=self.seed,kernel=self.kernel,bootstrap=self.bootstrap,experimental_seed_contract=self.contract)
        out=self.root/'no-disk-output';report={}
        with ExitStack() as cleanup,patch.object(steam_vm.shutil,'disk_usage',return_value=SimpleNamespace(free=15*1024**3)), \
                patch.object(steam_vm.subprocess,'run',side_effect=AssertionError('no image tools')) as image, \
                patch.object(steam_vm.subprocess,'Popen',side_effect=AssertionError('no VM')) as vm:
            with self.assertRaisesRegex(ValueError,'insufficient space for Steam image'):
                steam_vm._boot(args,self.root/'profiles/steam-host-experiment.json',self.profile,out,report,cleanup)
            image.assert_not_called();vm.assert_not_called()
        self.assertFalse(out.exists());self.assertFalse(report['storage_preflight']['allowed'])
        self.assertEqual(report['seed_sha256'],self.seed_pin['sha256'])

    def test_existing_storage_threshold_is_not_discounted_for_sparse_overlay(self):
        for free,allowed in [(16*1024**3-1,False),(16*1024**3,True)]:
            with patch.object(steam_vm.shutil,'disk_usage',return_value=SimpleNamespace(free=free)):
                result=steam_vm.storage_preflight(self.root,self.profile)
            self.assertEqual(result['allowed'],allowed)
            self.assertEqual(result['required_before_image_write_bytes'],16*1024**3)
            self.assertFalse(result['sparse_allocation_discount'])
