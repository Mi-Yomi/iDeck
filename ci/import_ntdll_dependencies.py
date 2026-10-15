#!/usr/bin/env python3
"""Transport exact reviewed producer artifacts; never execute or rewrite inputs.

This is byte/provenance validation, not a fresh platform or link test. The consuming
control must revalidate target archives and rerun relocated crypto feature proof.
"""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import zipfile

MIB = 1024 * 1024
MAX_ARCHIVE = 32 * MIB
MAX_EXPANDED = 128 * MIB
MAX_MEMBERS = 1024
PROOF_HELPER_SHA256 = '6d3a662a0760a17d329675bea3d3445959f9e85ed7d0d37ff7e608f3a055af9f'
CONFIG_SHA256 = '22332cb47937d006792e911322c2978a953d25fb5c883837c952b05e7e4077e4'
CRYPTO_METADATA = frozenset(('lib/libgmp.la', 'lib/libgnutls.la',
                            'lib/pkgconfig/gmp.pc', 'lib/pkgconfig/gnutls.pc',
                            'lib/pkgconfig/hogweed.pc', 'lib/pkgconfig/nettle.pc'))


class ImportFailure(ValueError):
    pass


def require(value, message):
    if not value:
        raise ImportFailure(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(name):
    require(isinstance(name, str), "Artifact path must be text")
    p = PurePosixPath(name)
    require(name and name == p.as_posix() and not p.is_absolute()
            and ".." not in p.parts and "\\" not in name and ":" not in name
            and all(ord(c) >= 32 and ord(c) != 127 for c in name), "Unsafe artifact path")
    return name


def safe_path(path, fresh=False):
    path = Path(path).absolute()
    require(".." not in path.parts, "Parent traversal in filesystem path")
    require(not any(p.is_symlink() for p in (path, *path.parents)), "Symlink path rejected")
    if fresh:
        require(not path.exists(), "Import destination already exists")
    else:
        require(path.is_file(), "Missing regular input file")
    return path


def validate_spec(spec):
    require(spec.get("status") == "verified-original-producer", "Artifact not verified and frozen")
    require(re.fullmatch(r"[0-9a-f]{64}", spec.get("sha256", "")), "Bad archive hash")
    require(type(spec.get("bytes")) is int and 0 < spec["bytes"] <= MAX_ARCHIVE, "Bad archive bound")
    producer = spec.get("producer", {})
    require(isinstance(producer, dict) and re.fullmatch(r"[0-9a-f]{24}", producer.get("build_id", "")) and re.fullmatch(r"[0-9a-f]{40}", producer.get("madeira", "")), "Missing exact producer identity")
    members = spec.get("members", {})
    require(isinstance(members, dict) and 0 < len(members) <= MAX_MEMBERS, "Bad member inventory")
    folded = set()
    for name, record in members.items():
        canonical(name)
        require(name.casefold() not in folded, "Case-colliding member inventory")
        folded.add(name.casefold())
        require(type(record.get("bytes")) is int and 0 <= record["bytes"] <= MAX_EXPANDED, "Bad member size")
        require(re.fullmatch(r"[0-9a-f]{64}", record.get("sha256", "")), "Bad member hash")
        require(not any(parent.as_posix() in members for parent in PurePosixPath(name).parents if parent.as_posix() != "."), "Member is a file parent")
    require(sum(x["bytes"] for x in members.values()) <= MAX_EXPANDED, "Expanded inventory too large")
    mapping = spec.get("prefix_mapping", {})
    kind = spec.get('kind', 'prefix')
    require(kind in ('prefix', 'evidence-only'), 'Unknown artifact kind')
    require(isinstance(mapping, dict) and (bool(mapping) if kind == 'prefix' else not mapping), "Invalid explicit prefix mapping")
    folded = set()
    for target, original in mapping.items():
        canonical(target)
        require(target.startswith(("include/", "lib/")) and original in members, "Invalid prefix mapping")
        require(target.casefold() not in folded, "Case-colliding prefix mapping")
        folded.add(target.casefold())
        require(not any(parent.as_posix() in mapping for parent in PurePosixPath(target).parents if parent.as_posix() != "."), "Prefix file parent")
    return spec


def import_artifact(archive, spec, destination):
    """Validate all bytes before writes; retain entire original envelope + mapped prefix."""
    spec = validate_spec(spec)
    archive = safe_path(archive)
    destination = safe_path(destination, fresh=True)
    require(archive.stat().st_size == spec["bytes"], "Archive size mismatch")
    raw = archive.read_bytes()
    require(sha(raw) == spec["sha256"], "Archive hash mismatch")
    checked = {}
    with zipfile.ZipFile(archive) as z:
        infos = z.infolist()
        names = [i.filename for i in infos]
        require(len(names) == len(set(names)) == len(spec["members"]), "Duplicate/missing/extra ZIP member")
        require(set(names) == set(spec["members"]), "ZIP differs from frozen member inventory")
        require(sum(i.file_size for i in infos) <= MAX_EXPANDED, "ZIP expansion bound exceeded")
        for info in infos:
            name = canonical(info.filename)
            mode = info.external_attr >> 16
            require(not info.is_dir() and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                    and not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                    "Only unencrypted regular stored/deflated files allowed")
            item = spec["members"][name]
            require(info.file_size == item["bytes"], "ZIP member size mismatch")
            data = z.read(info)  # Includes the ZIP CRC check.
            require(len(data) == item["bytes"] and sha(data) == item["sha256"], "ZIP member hash mismatch")
            checked[name] = data
    destination.mkdir(parents=True)
    records = []
    for name, data in checked.items():
        path = destination / "original" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(0o644)
    for target, original in spec["prefix_mapping"].items():
        path = destination / "prefix" / target
        path.parent.mkdir(parents=True, exist_ok=True)
        data = checked[original]
        path.write_bytes(data)
        path.chmod(0o644)
        records.append({"path": target, "original_member": original, "bytes": len(data), "sha256": sha(data), "content_changed": False})
    result = {"status": "imported-exact-reviewed-bytes", "producer": spec["producer"],
              "original_archive_sha256": spec["sha256"], "original_archive_bytes": len(raw),
              "original_members": len(checked), "prefix_files": sorted(records, key=lambda x: x["path"]),
              "metadata_rewritten": False, "target_executed": False, "platform_revalidated": False,
              "qualification": "Byte transport only; consumer must perform target-object and link/proof checks."}
    (destination / "import-manifest.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def verified_import(root, spec):
    """Recheck all retained/mapped identities before a bounded metadata operation."""
    spec = validate_spec(spec)
    root = Path(root).absolute()
    require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), 'Unsafe import root')
    manifest_path = safe_path(root / 'import-manifest.json')
    record = json.loads(manifest_path.read_text())
    require(record.get('original_archive_sha256') == spec['sha256'] and
            record.get('original_archive_bytes') == spec['bytes'] and
            record.get('producer') == spec['producer'] and record.get('metadata_rewritten') is False,
            'Imported producer identity mismatch')
    expected = {('original/' + n): row for n, row in spec['members'].items()}
    expected.update({('prefix/' + target): spec['members'][original] for target, original in spec['prefix_mapping'].items()})
    actual = set()
    for path in root.rglob('*'):
        require(not path.is_symlink(), 'Symlink inside imported envelope')
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(expected) | {'import-manifest.json'}, 'Imported envelope member set changed')
    for name, row in expected.items():
        path = safe_path(root / name)
        require(path.stat().st_size == row['bytes'] and sha(path.read_bytes()) == row['sha256'], 'Imported bytes changed: ' + name)
    return record


def relocate_crypto_metadata(import_root, spec, original_proof_root, proof_spec):
    """Literal relocation of six generated text files only; retain producer bytes."""
    imported = verified_import(import_root, spec)
    verified_import(original_proof_root, proof_spec)
    root = Path(import_root).absolute()
    prefix = root / 'prefix'
    require('.work' in prefix.parts and not any(c.isspace() or c in "'\";$`\\" for c in str(prefix)), 'Unsafe relocated prefix token')
    relocation = spec.get('metadata_relocation', {})
    old = relocation.get('old_prefix', '')
    rows = relocation.get('files', {})
    require(isinstance(old, str) and old.startswith('/Users/builder/') and
            len(old) < 1024 and set(rows) == CRYPTO_METADATA, 'Unreviewed relocation scope')
    original_proof = json.loads(safe_path(Path(original_proof_root) / 'original/TargetProof/proof.json').read_text())
    require(original_proof.get('prefix') == old and original_proof.get('result') == 'passed-target-link-proof' and
            original_proof.get('proof_helper_sha256') == PROOF_HELPER_SHA256 and
            original_proof.get('target_binaries_run') is False and original_proof.get('signed') is False,
            'Original crypto proof identity mismatch')
    require(spec['producer'] == proof_spec['producer'], 'Crypto prefix/proof producer mismatch')
    for name, row in original_proof.get('archives', {}).items():
        member = 'Prefix/lib/' + name
        require(member in spec['members'] and row['sha256'] == spec['members'][member]['sha256'], 'Original proof archive mismatch')
    require(set(original_proof.get('archives', {})) == {'libgmp.a', 'libnettle.a', 'libhogweed.a', 'libgnutls.a'}, 'Original proof archive closure mismatch')
    changes = []
    for name, row in sorted(rows.items()):
        canonical(name)
        require(spec['prefix_mapping'].get(name) == row.get('original_member'), 'Relocation mapping drift')
        source = safe_path(root / 'original' / row['original_member'])
        data = source.read_bytes()
        require(row.get('original_sha256') == sha(data) and type(row.get('occurrences')) is int and
                0 < row['occurrences'] <= 8 and data.count(old.encode()) == row['occurrences'], 'Relocation source/count drift')
        text = data.decode('utf-8', errors='strict')
        changed = text.replace(old, str(prefix)).encode()
        require(old.encode() not in changed, 'Producer path remains in relocated metadata')
        changes.append((name, changed, {'path': name, 'original_member': row['original_member'],
                        'before_sha256': sha(data), 'after_sha256': sha(changed),
                        'occurrences': row['occurrences'], 'bytes_before': len(data), 'bytes_after': len(changed)}))
    # All identities and transformations are validated before the first write.
    for name, changed, _ in changes:
        (prefix / name).write_bytes(changed)
    result = {'status': 'relocated-generated-metadata-only', 'original_archive_sha256': spec['sha256'],
              'original_proof_archive_sha256': proof_spec['sha256'], 'old_prefix': old, 'new_prefix': str(prefix),
              'files': [row for _, _, row in changes], 'binary_or_header_bytes_changed': False,
              'original_envelopes_changed': False, 'fresh_target_link_proof_required': True,
              'target_executed': False, 'flags_added_or_removed': False}
    (root / 'relocation-manifest.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


def emit_validated_overlay(proof_helper, prefix, proof_output, config):
    """Enable the two scoped feature facts only through the exact target revalidator."""
    helper = safe_path(proof_helper)
    require(sha(helper.read_bytes()) == PROOF_HELPER_SHA256, 'Unreviewed crypto proof helper')
    original = safe_path(config)
    require(sha(original.read_bytes()) == CONFIG_SHA256, 'Original Wine config drift')
    location = importlib.util.spec_from_file_location('reviewed_ntdll_crypto_proof', helper)
    module = importlib.util.module_from_spec(location)
    old = sys.dont_write_bytecode
    try:
        sys.dont_write_bytecode = True
        location.loader.exec_module(module)
        result = module.generate_feature_overlay(Path(prefix), Path(proof_output), original,
                                                Path(proof_output) / 'validated-gnutls-features.h')
    finally:
        sys.dont_write_bytecode = old
    require(sha(original.read_bytes()) == CONFIG_SHA256, 'Original Wine config changed')
    return result
