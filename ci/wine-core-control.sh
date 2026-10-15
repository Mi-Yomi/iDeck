#!/bin/bash
# Bounded current-Madeira Wine source control. No remote dispatch or installation.
# Usage: wine-core-control.sh SOURCE preflight|wine-headers|wineserver
set -euo pipefail
R=$(cd "${1:?source checkout required}" && pwd)
STAGE=${2:-preflight}
EXPECTED=279fd0f83170425db002fe25d6bd62f6355f497d
WINE_EXPECTED=9129e9684daaeae70da9435e7c6060e59392634e
[ "$(uname -s)" = Darwin ] || { echo 'macOS runner required'; exit 2; }
[ "$(uname -m)" = arm64 ] || { echo 'Apple silicon runner required'; exit 2; }
xcodebuild -version | grep -qx 'Xcode 26.6' || { echo 'Unreviewed Xcode'; exit 2; }
[ "$(git -C "$R" rev-parse HEAD)" = "$EXPECTED" ] || { echo 'Wrong Madeira pin'; exit 2; }
git -C "$R" diff --exit-code HEAD -- .
E="$R/build/control-evidence"
mkdir -p "$E/tmp"
export TMPDIR="$E/tmp" LC_ALL=C
JOBS=${JOBS:-4}
[[ "$JOBS" =~ ^[1-4]$ ]] || { echo 'JOBS must be 1..4'; exit 2; }
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
[ "$(xcrun --sdk iphoneos --show-sdk-version)" = 26.5 ] || { echo 'Unreviewed SDK'; exit 2; }
# Select only tools already installed on this image. Do not brew-install/update.
BISON_BIN=$(command -v bison || true)
if [ -x /opt/homebrew/opt/bison/bin/bison ]; then BISON_BIN=/opt/homebrew/opt/bison/bin/bison; fi
[ -n "$BISON_BIN" ] || { echo 'Prerequisite missing: Bison >=3'; exit 2; }
"$BISON_BIN" --version | head -1 | grep -Eq ' [3-9]\.' || { echo 'Prerequisite missing: Bison >=3'; exit 2; }
OBJCOPY_BIN=$(command -v llvm-objcopy || true)
if [ -z "$OBJCOPY_BIN" ]; then OBJCOPY_BIN=$(xcrun --find llvm-objcopy 2>/dev/null || true); fi
if [ -z "$OBJCOPY_BIN" ] && [ -x /opt/homebrew/opt/llvm/bin/llvm-objcopy ]; then
    OBJCOPY_BIN=/opt/homebrew/opt/llvm/bin/llvm-objcopy
fi
[ -n "$OBJCOPY_BIN" ] && [ -x "$OBJCOPY_BIN" ] || { echo 'Prerequisite missing: llvm-objcopy with Mach-O rename support'; exit 2; }
export PATH="$(dirname "$BISON_BIN"):$(dirname "$OBJCOPY_BIN"):$PATH"
for tool in flex make python3; do command -v "$tool" >/dev/null || { echo "Missing $tool"; exit 2; }; done
python3 - "$(flex --version)" <<'PY'
import re,sys
m=re.search(r"(\d+)\.(\d+)\.(\d+)",sys.argv[1])
assert m and tuple(map(int,m.groups())) >= (2,5,33), "Flex >=2.5.33 required"
PY
verify_wine() {
    [ "$(git -C "$R/wine" rev-parse HEAD)" = "$WINE_EXPECTED" ] || { echo 'Wrong Wine pin'; exit 2; }
    git -C "$R/wine" diff --exit-code HEAD -- .
}
case "$STAGE" in
preflight)
    { date -u; uname -m; sw_vers; xcodebuild -version;
      xcrun --sdk iphoneos --show-sdk-version; xcrun --sdk iphoneos clang --version;
      "$BISON_BIN" --version; flex --version; make --version;
      "$OBJCOPY_BIN" --version; python3 --version; df -h "$R";
      printf 'bison=%s\nobjcopy=%s\n' "$BISON_BIN" "$OBJCOPY_BIN";
      xcrun --sdk macosx --find clang; xcrun --sdk iphoneos --find clang;
    } > "$E/preflight.txt"
    cat "$E/preflight.txt"
    # Our own inert target object proves objcopy can rename Mach-O, not ELF only.
    printf 'int wine_control_probe = 1;\n' > "$E/objcopy-probe.c"
    xcrun --sdk iphoneos clang -arch arm64 -isysroot "$SDK" -miphoneos-version-min=17.0 \
      -c "$E/objcopy-probe.c" -o "$E/objcopy-probe.o"
    "$OBJCOPY_BIN" --redefine-sym _wine_control_probe=_wine_control_probe_renamed "$E/objcopy-probe.o"
    xcrun nm -g "$E/objcopy-probe.o" > "$E/objcopy-probe.nm.txt"
    grep -Eq '[[:space:]]_wine_control_probe_renamed$' "$E/objcopy-probe.nm.txt"
    ! grep -Eq '[[:space:]]_wine_control_probe$' "$E/objcopy-probe.nm.txt"
    xcrun otool -l "$E/objcopy-probe.o" > "$E/objcopy-probe.load-commands.txt"
    grep -Eq 'LC_BUILD_VERSION|LC_VERSION_MIN_IPHONEOS' "$E/objcopy-probe.load-commands.txt"
    ;;
wine-headers)
    verify_wine
    [ ! -e "$R/wine/build-macos" ] || { echo 'Fresh Wine build-macos required'; exit 2; }
    mkdir -p "$R/wine/build-macos"
    # Native host WIDL/makedep only. No PE compiler, host Wine install or SDK export.
    MAC_SDK=$(xcrun --sdk macosx --show-sdk-path)
    MAC_CC=$(xcrun --sdk macosx --find clang)
    MAC_CXX=$(xcrun --sdk macosx --find clang++)
    printf 'SDKROOT=%s\nCC=%s\nCXX=%s\nCFLAGS=\nCXXFLAGS=\nCPPFLAGS=\nLDFLAGS=\nLIBS=\n' \
      "$MAC_SDK" "$MAC_CC" "$MAC_CXX" > "$E/toolchain.txt"
    (cd "$R/wine/build-macos"
     export SDKROOT="$MAC_SDK" CC="$MAC_CC" CXX="$MAC_CXX" BISON="$BISON_BIN"
     export CFLAGS= CXXFLAGS= CPPFLAGS= LDFLAGS= LIBS=
     ../configure --enable-archs=none --without-x --without-freetype \
       --without-gnutls --without-gstreamer --disable-tests \
       2>&1 | tee "$E/wine-configure.log"
     make -j"$JOBS" include/all 2>&1 | tee "$E/wine-headers.log")
    for f in config.h dwrite.h dwrite_3.h mfobjects.h mftransform.h; do
        test -s "$R/wine/build-macos/include/$f"
    done
    # The generated native config remains unmodified. TLS integration is later.
    cp "$R/wine/build-macos/include/config.h" "$E/wine-config.h"
    shasum -a 256 "$E/wine-config.h" > "$E/wine-config-sha256.txt"
    ;;
wineserver)
    verify_wine
    test -s "$R/wine/build-macos/include/config.h"
    B="$R/build/wineserver"; W="$R/wine"; A="$R/app/Madeira/libwineserver.a"
    [ ! -e "$B/obj" ] && [ ! -e "$B/control-base" ] && [ ! -e "$A" ] || {
        echo 'Fresh server output directories/archive required'; exit 2;
    }
    mkdir -p "$B/control-base" "$R/app/Madeira"
    # Derive and verify closure against source, never inherit a prebuilt base.
    python3 - "$R" "$E/server-source-manifest.json" <<'PY'
import hashlib,json,re,sys
from pathlib import Path
r=Path(sys.argv[1]); script=(r/'build/wineserver/build.sh').read_text()
def entries(name):
 b=re.search(r'^'+name+r'=\((.*?)^\)',script,re.M|re.S)
 assert b, name
 return re.findall(r'^\s*"([^"\n]+)"',b[1],re.M)
patched=[x.split(':') for x in entries('PATCHED_FILES')]
replacements=[x.split(':') for x in entries('REPLACEMENTS')]
units=set(re.findall(r'\b([A-Za-z0-9_]+)\.c\b',(r/'wine/server/Makefile.in').read_text()))
base=sorted(units-{Path(x[2]).stem for x in patched})
expected='atom change clipboard completion console d3dkmt debugger device directory file hook mailslot mutex named_pipe procfs ptrace registry serial signal symlink timer token trace'.split()
assert base==expected,(base,expected)
assert len(units)==44 and len(patched)==25 and len(replacements)==26
assert {x[0]+'.o' for x in patched}|{'wineserver_ios_kill.o'}=={x[0] for x in replacements}
assert len({x[0] for x in replacements})==26
files=[r/'wine/server'/f'{x}.c' for x in base]+[r/'build/wineserver/wineserver_ios_kill.c']
for name,src,old in patched:
 for var,value in [('$WINE_SRC',str(r/'wine')),('$BUILD_DIR',str(r/'build/wineserver')),('$REPO_ROOT',str(r))]:
  src=src.replace(var,value)
 p=Path(src)
 if not p.is_absolute(): p=r/'build/wineserver'/p
 assert p.is_file(),p
 files.append(p)
# The HID parser is textually compiled into hidparse_ios.c.
files.append(r/'wine/dlls/hidparse.sys/main.c')
files.append(r/'wine/server/main.c')
manifest={'base_units':base,'patched_units':patched,'replacements':replacements,
 'expected_members':sorted([x+'.o' for x in base]+[x[0] for x in replacements]),
 'source_files':[{'path':str(p.relative_to(r)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in files],
 'collisions':'alloc_user_handle free_user_handle get_virtual_screen_rect destroy_thread_windows get_window_thread is_desktop_class is_message_class is_window_visible mirror_region send_notify_message shared_session user_shared_data'.split(),
 'madeira_commit':'279fd0f83170425db002fe25d6bd62f6355f497d','wine_commit':'9129e9684daaeae70da9435e7c6060e59392634e',
 'archive_only':True,'runtime_linked':False}
assert len(manifest['expected_members'])==49
Path(sys.argv[2]).write_text(json.dumps(manifest,indent=2)+'\n')
PY
    (
      set -x
      for u in atom change clipboard completion console d3dkmt debugger device directory file hook mailslot mutex named_pipe procfs ptrace registry serial signal symlink timer token trace; do
        xcrun --sdk iphoneos clang -arch arm64 -isysroot "$SDK" \
          -miphoneos-version-min=17.0 -O2 \
          -I"$W/include" -I"$W/include/wine" -I"$W/build-macos/include" \
          -I"$B" -I"$W/server" -I"$R/build/ntdll-unix/shims" \
          -I"$R/build/madsync" -DHAVE_LINUX_NTSYNC_H=1 \
          -include "$B/config_ios.h" -include stdarg.h -include "$B/unicode_fix.h" \
          -include "$B/wineserver_ios_kill.h" \
          -DBINDIR=\"/usr/local/bin\" -DDATADIR=\"/usr/local/share\" \
          -D__WINESRC__ -DWINE_IOS=1 -Dmain=wineserver_main \
          -Wno-implicit-function-declaration -c "$W/server/$u.c" -o "$B/control-base/$u.o"
      done
      xcrun ar rcs "$A" "$B/control-base/"*.o
      bash -x "$B/build.sh"
    ) 2>&1 | tee "$E/server-build.log"
    test -s "$A"
    xcrun lipo -info "$A" > "$E/libwineserver.a.arch.txt"
    xcrun ar -t "$A" > "$E/libwineserver.a.members.txt"
    xcrun otool -l "$A" > "$E/libwineserver.a.load-commands.txt"
    xcrun nm -g "$A" > "$E/libwineserver.a.symbols.txt"
    shasum -a 256 "$A" > "$E/archive-sha256.txt"
    ;;
*) echo 'Unknown stage'; exit 2 ;;
esac
