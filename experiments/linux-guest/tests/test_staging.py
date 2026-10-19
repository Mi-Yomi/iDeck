import hashlib
import io
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import stage_bundle
import stage_husk
import typecheck_source


class BundleGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.guest = self.root / "guest"
        self.guest.mkdir()
        self.profile = dict(stage_bundle.CONFIG)
        for key, name in (("kernel", "vmlinuz-virt"), ("initramfs", "initramfs-ideck.gz")):
            data = (key + " test fixture").encode()
            (self.guest / name).write_bytes(data)
            self.profile[key] = {"file": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
        self.save()

    def tearDown(self):
        self.temporary.cleanup()

    def save(self):
        (self.guest / "profile.json").write_text(json.dumps(self.profile))

    def test_only_validated_three_files_are_copied(self):
        (self.guest / "unrelated-secret").write_text("do not copy")
        out = self.root / "bundle"
        stage_bundle.stage(self.guest, out)
        self.assertEqual(set(p.name for p in out.iterdir()), {"profile.json", "vmlinuz-virt", "initramfs-ideck.gz"})
        self.assertEqual(stage_bundle.verify(self.guest), stage_bundle.verify(out))
        stage_bundle.stage(self.guest, out)  # incremental Xcode build

    def test_corruption_cannot_mutate_existing_bundle(self):
        out = self.root / "bundle"
        stage_bundle.stage(self.guest, out)
        before = stage_bundle.verify(out)
        (self.guest / "initramfs-ideck.gz").write_bytes(b"wrong")
        with self.assertRaises(ValueError):
            stage_bundle.stage(self.guest, out)
        self.assertEqual(stage_bundle.verify(out), before)

    def test_profile_filename_and_dimensions_cannot_override_scope(self):
        for key, value in (("width", 1024), ("vcpus", True)):
            good = self.profile[key]
            self.profile[key] = value
            self.save()
            with self.assertRaises(ValueError):
                stage_bundle.verify(self.guest)
            self.profile[key] = good
        self.profile["kernel"]["file"] = "../outside"
        self.save()
        with self.assertRaises(ValueError):
            stage_bundle.verify(self.guest)

    def test_oversized_profile_rejected_before_read(self):
        (self.guest / "profile.json").write_bytes(b" " * 65537)
        with self.assertRaises(ValueError):
            stage_bundle.verify(self.guest)

    def test_output_cannot_be_source_or_its_child(self):
        for out in (self.guest, self.guest / "bundle"):
            with self.assertRaises(ValueError):
                stage_bundle.stage(self.guest, out)

    def test_output_directory_cannot_replace_an_asset(self):
        out = self.root / "bundle"
        (out / "initramfs-ideck.gz").mkdir(parents=True)
        with self.assertRaises(ValueError):
            stage_bundle.stage(self.guest, out)
        self.assertFalse((out / "vmlinuz-virt").exists())

    def test_dirty_or_wrong_upstream_rejected_before_worktree(self):
        for head, status in (("0" * 40, b""), (stage_husk.PIN, b" M src/app/Husk/HuskApp.swift")):
            with patch.object(stage_husk, "load_overlay", return_value={}), \
                 patch.object(stage_husk, "git", side_effect=[head.encode(), status]) as git:
                with self.assertRaises(ValueError):
                    stage_husk.prepare(self.root / "upstream", self.guest, self.root / "output")
                self.assertFalse(any("worktree" in call.args for call in git.call_args_list))

    def test_overlay_paths_must_stay_under_root(self):
        for name in ("../bad", "/bad", "C:/bad", "folder\\bad"):
            with self.assertRaises(ValueError):
                stage_husk.local_path(self.root, name)

    def test_sparse_checkout_is_not_a_build_source(self):
        with patch.object(stage_husk, "load_overlay", return_value={}), \
             patch.object(stage_husk, "git", side_effect=[stage_husk.PIN.encode(), b"", b"S missing.swift\n"]):
            with self.assertRaisesRegex(ValueError, "complete Husk checkout"):
                stage_husk.prepare(self.root / "upstream", self.guest, self.root / "output")

    def test_exact_offline_source_slice_and_patch(self):
        out = self.root / "source-slice"
        lock = typecheck_source.restore(out)
        self.assertEqual(len(lock["files"]), 81)
        self.assertTrue((out / "src/translation-layer-next/husk-console-abi.h").is_file())
        before = typecheck_source.swift_sources(out)
        typecheck_source.overlay(out)
        after = typecheck_source.swift_sources(out)
        self.assertEqual(len(after), len(before) + 29)
        self.assertIn("LinuxProbeRoot()", (out / "src/app/Husk/HuskApp.swift").read_text())
        self.assertTrue((out / "src/translation-layer/husk-tl.h").is_file())
        with self.assertRaises(ValueError):
            typecheck_source.restore(out)

    def test_missing_transitive_header_rejected_even_with_valid_archive_hashes(self):
        lock = json.loads((stage_husk.ROOT / "husk/source-check.lock.json").read_text())
        original = stage_husk.ROOT / "husk" / lock["archive"]
        fake = self.root / "incomplete-source-package"
        (fake / "husk").mkdir(parents=True)
        archive = fake / "husk" / lock["archive"]
        missing = "src/translation-layer-next/husk-console-abi.h"
        del lock["files"][missing]
        with tarfile.open(original) as source, tarfile.open(archive, "w:gz") as target:
            for member in source:
                if member.name != missing:
                    target.addfile(member, io.BytesIO(source.extractfile(member).read()))
        raw = archive.read_bytes()
        lock.update(archive_size=len(raw), archive_sha256=hashlib.sha256(raw).hexdigest())
        (fake / "husk/source-check.lock.json").write_text(json.dumps(lock))
        out = self.root / "must-not-be-created"
        with patch.object(typecheck_source, "ROOT", fake):
            with self.assertRaisesRegex(ValueError, "husk-console-abi.h"):
                typecheck_source.restore(out)
        self.assertFalse(out.exists())

    def test_changed_overlay_input_rejected(self):
        original = json.loads((stage_husk.ROOT / "husk/overlay.lock.json").read_text())
        fake = self.root / "overlay"
        (fake / "husk").mkdir(parents=True)
        original["inputs"] = {"changed.swift": "0" * 64}
        (fake / "husk/overlay.lock.json").write_text(json.dumps(original))
        (fake / "changed.swift").write_text("changed")
        with patch.object(stage_husk, "ROOT", fake):
            with self.assertRaisesRegex(ValueError, "differs from its reviewed lock"):
                stage_husk.load_overlay()


if __name__ == "__main__":
    unittest.main()
