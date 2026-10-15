#!/bin/bash
# Source-only FreeType + complete current-Madeira win32u control.
# A reviewed outer wrapper supplies timeout, source fetch and header import.
# Usage: win32u-core-control.sh SOURCE preflight|freetype|win32u
set -euo pipefail
R=$(cd "${1:?source checkout required}" && pwd)
STAGE=${2:-preflight}
HERE=$(cd "$(dirname "$0")" && pwd)
EXPECTED=279fd0f83170425db002fe25d6bd62f6355f497d
WINE_EXPECTED=9129e9684daaeae70da9435e7c6060e59392634e
FT_EXPECTED=42608f77f20749dd6ddc9e0536788eaad70ea4b5
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo 'arm64 macOS required'; exit 2; }
# Capture the whole command before comparison. Early-exit grep/head consumers
# can SIGPIPE the producer under pipefail and misreport a matching tool version.
if XCODE_OUTPUT=$(xcodebuild -version); then :; else
    status=$?; printf 'xcodebuild -version failed (%s):\n%s\n' "$status" "$XCODE_OUTPUT"; exit "$status"
fi
[[ $'\n'"$XCODE_OUTPUT"$'\n' == *$'\nXcode 26.6\n'* ]] || {
    printf 'Unreviewed Xcode output:\n%s\n' "$XCODE_OUTPUT"; exit 2;
}
[ "$(xcrun --sdk iphoneos --show-sdk-version)" = 26.5 ] || { echo 'Unreviewed iPhoneOS SDK'; exit 2; }
[ "$(git -C "$R" rev-parse HEAD)" = "$EXPECTED" ] || { echo 'Wrong Madeira pin'; exit 2; }
git -C "$R" diff --exit-code HEAD -- .
E="$R/build/win32u-control-evidence"
mkdir -p "$E/tmp"
export TMPDIR="$E/tmp" LC_ALL=C
JOBS=${JOBS:-4}
[[ "$JOBS" =~ ^[1-4]$ ]] || { echo 'JOBS must be 1..4'; exit 2; }
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
MAKE=$(xcrun --find make)
LIBTOOL=$(xcrun --find libtool)
[ -x "$MAKE" ] || { echo 'Xcode make missing'; exit 2; }
[ -x "$LIBTOOL" ] || { echo 'Apple libtool missing'; exit 2; }
# The upstream recipe calls bare ar/libtool. Prefer the selected Xcode tools,
# never an unrelated GNU libtool or package-manager archiver earlier on PATH.
export PATH="$(dirname "$LIBTOOL"):$PATH"
for tool in cmake python3 git; do command -v "$tool" >/dev/null || { echo "Missing $tool"; exit 2; }; done
if CMAKE_OUTPUT=$(cmake --version); then :; else
    status=$?; printf 'cmake --version failed (%s):\n%s\n' "$status" "$CMAKE_OUTPUT"; exit "$status"
fi
[[ "${CMAKE_OUTPUT%%$'\n'*}" = 'cmake version 4.3.4' ]] || {
    printf 'Unreviewed CMake output:\n%s\n' "$CMAKE_OUTPUT"; exit 2;
}
verify_sources() {
    [ "$(git -C "$R/wine" rev-parse HEAD)" = "$WINE_EXPECTED" ] || { echo 'Wrong Wine pin'; exit 2; }
    [ "$(git -C "$R/research/freetype" rev-parse HEAD)" = "$FT_EXPECTED" ] || { echo 'Wrong FreeType pin'; exit 2; }
    git -C "$R/wine" diff --exit-code HEAD -- .
    git -C "$R/research/freetype" diff --exit-code HEAD -- .
    python3 - "$R" "$HERE/source-lock.json" <<'PY'
import hashlib,json,pathlib,sys
r=pathlib.Path(sys.argv[1]); lock=json.loads(pathlib.Path(sys.argv[2]).read_text())
assert lock['madeira_commit']=='279fd0f83170425db002fe25d6bd62f6355f497d'
assert lock['wine_commit']=='9129e9684daaeae70da9435e7c6060e59392634e'
assert lock['freetype_commit']=='42608f77f20749dd6ddc9e0536788eaad70ea4b5'
for key,count in [('win32u',46),('freetype',42)]:
    rows=lock[key]; assert len(rows)==count and len({v['member'] for v in rows})==count
    for row in rows:
        p=r/row['path']; assert p.is_file() and not p.is_symlink(),p
        assert p.resolve().is_relative_to(r),p
        if row.get('sha256'): assert hashlib.sha256(p.read_bytes()).hexdigest()==row['sha256'],p
        if row.get('git_blob_sha1'):
            data=p.read_bytes()
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==row['git_blob_sha1'],p
for name in lock['required_generated_headers']:
    p=r/'wine/build-macos/include'/name; assert p.is_file() and not p.is_symlink() and p.stat().st_size,p
PY
}
archive_evidence() {
    local archive=$1 name=$2
    test -s "$archive"
    xcrun ar -t "$archive" > "$E/$name.members.txt"
    xcrun lipo -archs "$archive" > "$E/$name.arch.txt"
    xcrun otool -l "$archive" > "$E/$name.load-commands.txt"
    xcrun nm -g "$archive" > "$E/$name.symbols.txt"
    shasum -a 256 "$archive" > "$E/$name.sha256.txt"
}
# All compiler, SDK, library and CMake inputs for this control are specified
# below. Inherited search paths/toolchain files must not inject untracked code.
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH \
  CC CXX CFLAGS CXXFLAGS CPPFLAGS LDFLAGS LIBS SDKROOT \
  MACOSX_DEPLOYMENT_TARGET IPHONEOS_DEPLOYMENT_TARGET \
  CMAKE_TOOLCHAIN_FILE CMAKE_PREFIX_PATH CMAKE_GENERATOR CMAKE_GENERATOR_PLATFORM \
  CMAKE_GENERATOR_TOOLSET CMAKE_C_COMPILER_LAUNCHER CMAKE_CXX_COMPILER_LAUNCHER \
  CMAKE_PROJECT_TOP_LEVEL_INCLUDES PKG_CONFIG_PATH PKG_CONFIG_LIBDIR
printf 'SDK=%s\nCLANG=%s\nMAKE=%s\nLIBTOOL=%s\nJOBS=%s\nInherited compile/search/toolchain overrides cleared\n' \
  "$SDK" "$(xcrun --sdk iphoneos --find clang)" "$MAKE" "$LIBTOOL" "$JOBS" > "$E/toolchain.txt"
case "$STAGE" in
preflight)
    { date -u; uname -m; sw_vers; printf '%s\n' "$XCODE_OUTPUT";
      xcrun --sdk iphoneos --show-sdk-version; xcrun --sdk iphoneos clang --version;
      printf '%s\n' "$CMAKE_OUTPUT"; "$MAKE" --version; python3 --version; df -h "$R";
      printf 'make=%s\ncmake=%s\nlibtool=%s\nar=%s\n' "$MAKE" "$(command -v cmake)" "$LIBTOOL" "$(command -v ar)";
    } > "$E/preflight.txt"
    cat "$E/preflight.txt"
    ;;
freetype)
    verify_sources
    B="$R/build/freetype-ios/build"
    [ ! -e "$B" ] || { echo 'Fresh FreeType build directory required'; exit 2; }
    # Same source/version/features as the pinned Madeira recipe. Explicit make,
    # compiler, compile database, parallel limit and LTO-off are control guards.
    cmake -S "$R/research/freetype" -B "$B" -G 'Unix Makefiles' \
      -DCMAKE_MAKE_PROGRAM="$MAKE" \
      -DCMAKE_C_COMPILER="$(xcrun --sdk iphoneos --find clang)" \
      -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_OSX_ARCHITECTURES=arm64 \
      -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 -DCMAKE_OSX_SYSROOT="$SDK" \
      -DCMAKE_BUILD_TYPE=Release -DBUILD_SHARED_LIBS=OFF \
      -DFT_DISABLE_ZLIB=ON -DFT_DISABLE_BZIP2=ON -DFT_DISABLE_PNG=ON \
      -DFT_DISABLE_HARFBUZZ=ON -DFT_DISABLE_BROTLI=ON \
      -DCMAKE_C_FLAGS=-fno-stack-protector \
      -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
    cmake --build "$B" --parallel "$JOBS"
    cp "$B/CMakeCache.txt" "$E/CMakeCache.txt"
    cp "$B/compile_commands.json" "$E/compile_commands.json"
    python3 - "$R" "$HERE/source-lock.json" <<'PY'
import json,pathlib,sys
r=pathlib.Path(sys.argv[1]); lock=json.loads(pathlib.Path(sys.argv[2]).read_text())
cmds=json.loads((r/'build/freetype-ios/build/compile_commands.json').read_text())
assert len(cmds)==42, 'Unexpected FreeType compilation count'
actual=[pathlib.Path(c['file']).resolve().relative_to(r).as_posix() for c in cmds]
assert sorted(actual)==sorted(i['path'] for i in lock['freetype']), 'FreeType source closure drift'
for c in cmds:
    text=c.get('command',' '.join(c.get('arguments',[])))
    assert '-arch arm64' in text and '-miphoneos-version-min=17.0' in text, text
PY
    archive_evidence "$B/libfreetype.a" libfreetype.a
    ;;
win32u)
    verify_sources
    B="$R/build/win32u-unix"
    A="$R/app/Madeira/libwin32u_unix.a"
    [ ! -e "$B/obj" ] && [ ! -e "$B/control-unmerged.a" ] && [ ! -e "$A" ] || {
        echo 'Fresh win32u object/archive outputs required'; exit 2;
    }
    test -s "$R/build/freetype-ios/build/libfreetype.a"
    test -s "$R/build/freetype-ios/build/include/freetype/config/ftconfig.h"
    mkdir -p "$R/app/Madeira"
    # No missing-font warning branch: the real FreeType archive is mandatory.
    # This executes the exact pinned source recipe without generated stub code.
    bash -x "$B/build.sh"
    python3 - "$R" "$HERE/source-lock.json" <<'PY'
import hashlib,json,pathlib,subprocess,sys
r=pathlib.Path(sys.argv[1]); lock=json.loads(pathlib.Path(sys.argv[2]).read_text())
obj=r/'build/win32u-unix/obj'; expected=sorted(v['member'] for v in lock['win32u'])
assert sorted(p.name for p in obj.glob('*.o'))==expected, 'Unexpected win32u object closure'
archive=r/'build/win32u-unix/control-unmerged.a'
subprocess.run(['xcrun','ar','rcs',str(archive),*[str(obj/n) for n in expected]],check=True)
paths=sorted({v['path'] for v in lock['win32u']+lock['freetype']}|set(lock['additional_source_files']))
files=[]
for name in paths:
    p=r/name
    assert p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(r),p
    files.append({'path':name,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'size':p.stat().st_size})
manifest={k:lock[k] for k in ['madeira_commit','wine_commit','freetype_commit']}
manifest.update(archive_only=True,runtime_linked=False,device_tested=False,
    win32u_members=expected,freetype_members=sorted(v['member'] for v in lock['freetype']),source_files=files,
    upstream_feature_limits=['CoreText font enumeration uses upstream null-collection wrapper',
        'Fontconfig/EGL/Vulkan backends remain disabled by upstream config',
        'Application Winios and ntdll references remain unresolved at archive stage'])
(r/'build/win32u-control-evidence/source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
PY
    archive_evidence "$B/control-unmerged.a" libwin32u-core.a
    archive_evidence "$A" libwin32u_unix.a
    ;;
*) echo "Unknown stage: $STAGE"; exit 2 ;;
esac
