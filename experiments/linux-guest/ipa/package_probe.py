"""Validate the freshly linked iOS app and package it for owner sideloading."""
import hashlib
import json
import plistlib
import re
import shutil
import zipfile
from pathlib import Path


def check_plist(info):
    if info.get("CFBundleIdentifier") != "dev.ideck.linuxprobe":
        raise ValueError("Probe must have its own bundle identifier, separate from Husk")
    if info.get("CFBundleExecutable") != "Husk" or info.get("CFBundlePackageType") != "APPL":
        raise ValueError("Unexpected app executable/package")
    for key in ("CFBundleVersion", "CFBundleShortVersionString", "MinimumOSVersion", "UIDeviceFamily"):
        if not info.get(key):
            raise ValueError("Missing app plist key: " + key)


def check_ios_build_output(text):
    if not (re.search(r"platform\s+IOS\s", text) or "LC_VERSION_MIN_IPHONEOS" in text):
        raise ValueError("Linked Mach-O is not proven to target iOS devices")
    if "IOSSIMULATOR" in text or "MACOS" in text or "MACCATALYST" in text:
        raise ValueError("Non-device Mach-O platform present")


def configure_markdown_type(info):
    """Describe the existing Markdown file format for URL-based sharing."""
    identifier = "net.daringfireball.markdown"
    declarations = [item for item in info.get("UTImportedTypeDeclarations", [])
                    if item.get("UTTypeIdentifier") != identifier]
    declarations.append({
        "UTTypeIdentifier": identifier,
        "UTTypeDescription": "Markdown document",
        "UTTypeConformsTo": ["public.utf8-plain-text"],
        "UTTypeTagSpecification": {
            "public.filename-extension": ["md"],
            "public.mime-type": ["text/markdown"],
        },
    })
    info["UTImportedTypeDeclarations"] = declarations


def check_terminal_assets(app):
    lock = json.loads((Path(__file__).parent / "terminal.lock.json").read_text())
    expected_names = {"terminal-profile.json", "initramfs-terminal.gz", "userdata-seed.raw", "LICENSES-terminal.txt"}
    if set(lock["files"]) != expected_names:
        raise ValueError("Unexpected terminal resource manifest")
    directory = app / "iDeckLinuxTerminal"
    if directory.is_symlink() or not directory.is_dir() or {path.name for path in directory.iterdir()} != expected_names:
        raise ValueError("Required terminal resource directory missing or changed")
    for name, expected in lock["files"].items():
        path = directory / name
        if path.is_symlink() or not path.is_file() or path.stat().st_size != expected["size"]:
            raise ValueError("Required terminal resource missing or changed: " + name)
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        if digest.hexdigest() != expected["sha256"]:
            raise ValueError("Terminal resource integrity failure: " + name)


def package(worker, built, source, commit):
    if not built.is_dir():
        raise ValueError("No freshly built app; refusing to package")
    stage = worker.output / "package"
    app = stage / "Payload/Husk.app"
    app.parent.mkdir(parents=True)
    shutil.copytree(built, app, symlinks=True)
    plist_path = app / "Info.plist"
    info = plistlib.loads(plist_path.read_bytes())
    check_plist(info)
    info["CFBundleDisplayName"] = "iDeck Linux Probe"
    info["iDeckSourceCommit"] = commit
    # The probe does not import Android packages or handle the installed Husk's
    # URL scheme. Keeping those registrations would make iOS offer the wrong app.
    info.pop("CFBundleDocumentTypes", None)
    info["CFBundleURLTypes"] = [{"CFBundleURLName": "dev.ideck.linuxprobe",
                                 "CFBundleURLSchemes": ["ideck-linux-probe"]}]
    configure_markdown_type(info)
    plist_path.write_bytes(plistlib.dumps(info))
    required = ["Husk", "default.metallib", "husk-jit.js", "Frameworks/libqemu-aarch64-softmmu.dylib",
                "Frameworks/libANGLE-shared.dylib", "Frameworks/libFilePickerFix.dylib",
                "Frameworks/StikJIT.framework/StikJIT", "Frameworks/StikJIT.framework/Info.plist",
                "PlugIns/HuskJITHelper.appex/HuskJITHelper",
                "PlugIns/HuskDownloadsWidget.appex/HuskDownloadsWidget"]
    for name in required:
        file = app / name
        if not file.is_file() or file.stat().st_size == 0:
            raise ValueError("Required app component missing: " + name)
    # The software Linux guest is exact, including the original validated profile.
    guest_lock = json.loads((Path(__file__).parent / "guest.lock.json").read_text())
    for name, expected in guest_lock["files"].items():
        file = app / "iDeckLinuxProbe" / name
        if file.stat().st_size != expected["size"] or hashlib.sha256(file.read_bytes()).hexdigest() != expected["sha256"]:
            raise ValueError("Guest bytes changed or were not bundled: " + name)
    check_terminal_assets(app)
    # Fail packaging even when Xcode succeeded if Debian payload is omitted,
    # changed, or incomplete. Stream the large seed; never load it into RAM.
    from debian_bundle import verify as verify_debian, load_lock as load_debian_lock
    verify_debian(app / "iDeckDebian", load_debian_lock(Path(__file__).parent / "debian.lock.json"))
    for extension in (app / "PlugIns").glob("*.appex"):
        metadata = plistlib.loads((extension / "Info.plist").read_bytes())
        if not metadata.get("CFBundleIdentifier", "").startswith("dev.ideck.linuxprobe."):
            raise ValueError("Extension has an incompatible bundle identifier")
    binaries = [app / "Husk", *sorted((app / "Frameworks").rglob("*.dylib")),
                app / "Frameworks/StikJIT.framework/StikJIT",
                app / "PlugIns/HuskJITHelper.appex/HuskJITHelper",
                app / "PlugIns/HuskDownloadsWidget.appex/HuskDownloadsWidget"]
    for index, binary in enumerate(binaries):
        worker.run(f"arch-{index}", ["xcrun", "lipo", "-verify_arch", "arm64", binary])
        text = worker.run(f"platform-{index}", ["xcrun", "vtool", "-arch", "arm64", "-show-build", binary])
        check_ios_build_output(text + "\n")
        linked = worker.run(f"linked-{index}", ["xcrun", "otool", "-arch", "arm64", "-L", binary])
        for line in linked.splitlines():
            if " (compatibility version " not in line:
                continue
            dependency = line.strip().split(" (compatibility version ")[0]
            if dependency.startswith(("/System/Library/", "/usr/lib/")):
                continue
            if dependency.startswith("@rpath/"):
                resolved = app / "Frameworks" / dependency.removeprefix("@rpath/")
            elif dependency.startswith("@loader_path/"):
                resolved = binary.parent / dependency.removeprefix("@loader_path/")
            else:
                raise ValueError("Unpackaged/non-system dependency: " + dependency)
            if not resolved.resolve().is_relative_to(app.resolve()) or not resolved.is_file():
                raise ValueError("Missing embedded dependency: " + dependency)
    # Ad-hoc only, inside out. No certificate/account is read or created.
    for index, binary in enumerate(sorted((app / "Frameworks").rglob("*.dylib"))):
        worker.run(f"sign-dylib-{index}", ["codesign", "--force", "--sign", "-", "--timestamp=none", binary])
    for index, bundle in enumerate([*sorted((app / "Frameworks").glob("*.framework")), *sorted((app / "PlugIns").glob("*.appex"))]):
        worker.run(f"sign-bundle-{index}", ["codesign", "--force", "--sign", "-", "--timestamp=none", bundle])
    worker.run("sign-app", ["codesign", "--force", "--sign", "-", "--timestamp=none", "--entitlements",
                           source / "src/app/Husk/Husk.entitlements", app])
    worker.run("verify-signatures", ["codesign", "--verify", "--deep", "--strict", app])
    output = worker.output / "iDeck-Linux-Probe.ipa"
    worker.run("zip-ipa", ["ditto", "-c", "-k", "--keepParent", app.parent, output])
    with zipfile.ZipFile(output) as archive:
        if archive.testzip() is not None:
            raise ValueError("IPA ZIP integrity check failed")
        if "Payload/Husk.app/Husk" not in archive.namelist():
            raise ValueError("Wrong IPA payload layout")
    return {"ipa_created": True, "runtime_linked": True, "signing": "ad-hoc; owner sideload signing required",
            "ipa": output.name, "ipa_size": output.stat().st_size,
            "ipa_sha256": hashlib.sha256(output.read_bytes()).hexdigest()}
