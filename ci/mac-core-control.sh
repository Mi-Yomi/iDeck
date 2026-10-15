#!/bin/bash
# iDeck research control. Reviewed source build recipe, NOT yet run on macOS.
# No signing, service dispatch, proprietary payload download, or SDK copying.
# Usage: bash mac-core-control.sh SOURCE preflight|fex-ios|wine-headers|wineserver
set -euo pipefail
R=$(cd "${1:?source checkout required}" && pwd)
STAGE=${2:-preflight}
EXPECTED=279fd0f83170425db002fe25d6bd62f6355f497d
[ "$(git -C "$R" rev-parse HEAD)" = "$EXPECTED" ] || { echo 'Wrong Madeira revision'; exit 2; }
[ "$(uname -s)" = Darwin ] || { echo 'This stage requires the approved macOS executor'; exit 2; }
E="$R/build/control-evidence"
mkdir -p "$E"
export TMPDIR="$E/tmp"; mkdir -p "$TMPDIR"
export LC_ALL=C
JOBS=${JOBS:-4}
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
verify_pin() {
    [ "$(git -C "$R/$1" rev-parse HEAD)" = "$2" ] || { echo "Wrong $1 revision"; exit 2; }
    git -C "$R/$1" diff --exit-code HEAD -- . || { echo "Tracked $1 source drift"; exit 2; }
}
archive_evidence() {
    local f=$1 n
    test -s "$f"
    n=$(basename "$f")
    shasum -a 256 "$f" >> "$E/archive-sha256.txt"
    xcrun lipo -info "$f" > "$E/$n.arch.txt"
    xcrun ar -t "$f" > "$E/$n.members.txt"
    # arm64 alone could also be macOS; preserve every object's platform/minos.
    xcrun otool -l "$f" > "$E/$n.load-commands.txt"
    grep -Eq 'LC_BUILD_VERSION|LC_VERSION_MIN_IPHONEOS' "$E/$n.load-commands.txt" || {
      echo "No target platform metadata found in $f"; exit 2;
    }
    test -s "$E/$n.members.txt"
}
case "$STAGE" in
preflight)
    git -C "$R" diff --exit-code HEAD -- .
    { date -u; git -C "$R" rev-parse HEAD; git -C "$R" submodule status;
      uname -m; sw_vers; xcodebuild -version; xcrun --sdk iphoneos --show-sdk-version;
      xcrun --sdk iphoneos clang --version; df -h "$R";
      for tool in cmake ninja bison flex python3 cargo rustc llvm-objcopy; do
        command -v "$tool" || true
      done
      cmake --version; bison --version | head -1; python3 --version;
      xcrun --find metal || true; xcrun --find metallib || true;
    } | tee "$E/preflight.txt"
    ;;
fex-ios)
    git -C "$R" diff --exit-code HEAD -- .
    [ ! -e "$R/FEX/build-ios/CMakeCache.txt" ] || {
      echo 'First control requires a fresh build-ios; refusing stale CMake cache'; exit 2;
    }
    verify_pin FEX f59cab95659e8add0c88f0c76ec1cf483c536dbf
    for p in External/fmt External/range-v3 External/xxhash External/unordered_dense; do
        cmake_file="$R/FEX/$p/CMakeLists.txt"
        if [ "$p" = External/xxhash ]; then
            cmake_file="$R/FEX/$p/cmake_unofficial/CMakeLists.txt"
        fi
        test -f "$cmake_file" || { echo "Missing pinned CMake input $cmake_file"; exit 2; }
        expected_sub=$(git -C "$R/FEX" ls-tree HEAD "$p" | awk '{print $3}')
        [ "$(git -C "$R/FEX/$p" rev-parse HEAD)" = "$expected_sub" ] || {
          echo "Wrong pinned FEX/$p revision"; exit 2;
        }
        git -C "$R/FEX/$p" diff --exit-code HEAD -- .
    done
    # Explicit tuning avoids the source's /proc/cpuinfo probe on Apple hosts.
    # Explicit archive targets close omissions in upstream's build.sh.
    # LTO off is a recorded control-build deviation, not a claim of byte identity.
    # The observed Apple image has no Ninja; use its Xcode-provided make.
    MAKE_PROGRAM=$(xcrun --find make)
    test -x "$MAKE_PROGRAM"
    "$MAKE_PROGRAM" --version | head -1
    cmake -S "$R/FEX" -B "$R/FEX/build-ios" -G "Unix Makefiles" \
      -DCMAKE_MAKE_PROGRAM="$MAKE_PROGRAM" \
      -DCMAKE_SYSTEM_NAME=iOS -DCMAKE_SYSTEM_PROCESSOR=arm64 \
      -DCMAKE_OSX_ARCHITECTURES=arm64 -DCMAKE_OSX_SYSROOT="$SDK" \
      -DCMAKE_OSX_DEPLOYMENT_TARGET=17.0 -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTING=OFF -DBUILD_THUNKS=OFF -DBUILD_FEXCONFIG=OFF \
      -DBUILD_FEX_LINUX_TESTS=OFF -DENABLE_FEX_ALLOCATOR=OFF \
      -DENABLE_ASSERTIONS=OFF -DENABLE_CLANG_THUNKS=ON \
      -DENABLE_CCACHE=OFF -DENABLE_LTO=OFF -DTUNE_CPU=cortex-a78 \
      -DCMAKE_DISABLE_FIND_PACKAGE_fmt=TRUE \
      -DCMAKE_DISABLE_FIND_PACKAGE_range-v3=TRUE \
      -DCMAKE_DISABLE_FIND_PACKAGE_unordered_dense=TRUE \
      2>&1 | tee "$E/fex-configure.log"
    cmake --build "$R/FEX/build-ios" --parallel "$JOBS" \
      --target FEXCore FEXCore_Base JemallocLibs fmt cephes_128bit xxhash softfloat_3e \
      2>&1 | tee "$E/fex-build.log"
    for f in FEXCore/Source/libFEXCore.a FEXCore/Source/libFEXCore_Base.a \
      FEXCore/Source/libJemallocLibs.a External/fmt/libfmt.a \
      External/cephes/libcephes_128bit.a External/xxhash/cmake_unofficial/libxxhash.a \
      External/SoftFloat-3e/libsoftfloat_3e.a; do
        archive_evidence "$R/FEX/build-ios/$f"
    done
    cp "$R/FEX/build-ios/CMakeCache.txt" "$E/fex-CMakeCache.txt"
    ;;
wine-headers)
    git -C "$R" diff --exit-code HEAD -- .
    [ ! -e "$R/wine/build-macos/config.status" ] || {
      echo 'First header control requires a fresh build-macos'; exit 2;
    }
    verify_pin wine 9129e9684daaeae70da9435e7c6060e59392634e
    # Wine configure.ac accepts --enable-archs=none for native build tools.
    # --without-mingw alone is insufficient on aarch64 and is intentionally avoided.
    bison --version | head -1 | grep -Eq ' [3-9]\.' || { echo 'Bison >=3 required'; exit 2; }
    mkdir -p "$R/wine/build-macos" "$R/wine/build-arm64ec/include"
    (cd "$R/wine/build-macos" && ../configure --enable-archs=none \
       --without-x --without-freetype --without-gnutls --disable-tests \
       --enable-winegstreamer 2>&1 | tee "$E/wine-configure.log"
     make -j"$JOBS" include/all 2>&1 | tee "$E/wine-headers.log")
    # Same explicit static-GnuTLS configuration used in Playport unix-gaps.
    C="$R/wine/build-macos/include/config.h"
    if ! grep -q '^#define SONAME_LIBGNUTLS ' "$C"; then
      printf '\n/* Madeira static iOS GnuTLS binding. */\n#define HAVE_GNUTLS_CIPHER_INIT 1\n#define SONAME_LIBGNUTLS "libgnutls.30.dylib"\n' >> "$C"
    fi
    for f in "$R/wine/build-macos/include/"*.h; do
      [ "$(basename "$f")" = config.h ] || cp "$f" "$R/wine/build-arm64ec/include/"
    done
    for f in config.h dwrite.h dwrite_3.h mfobjects.h mftransform.h; do
      test -s "$R/wine/build-macos/include/$f"
    done
    shasum -a 256 "$C" > "$E/wine-config-sha256.txt"
    ;;
wineserver)
    git -C "$R" diff --exit-code HEAD -- build/wineserver build/madsync build/ntdll-unix/shims
    verify_pin wine 9129e9684daaeae70da9435e7c6060e59392634e
    command -v llvm-objcopy >/dev/null
    test -s "$R/wine/build-macos/include/config.h"
    B="$R/build/wineserver"; W="$R/wine"; A="$R/app/Madeira/libwineserver.a"
    [ ! -e "$A" ] && [ ! -e "$B/obj/libwineserver.a" ] || {
      echo 'Refusing to mix a prior server archive into the clean control'; exit 2;
    }
    mkdir -p "$B/control-base"
    # Exact remainder: current Wine server/Makefile.in's 44 C sources minus
    # upstream Madeira PATCHED_FILES replacement object names = 23 units.
    UNPATCHED='atom change clipboard completion console d3dkmt debugger device directory file hook mailslot mutex named_pipe procfs ptrace registry serial signal symlink timer token trace'
    for u in $UNPATCHED; do
      xcrun --sdk iphoneos clang -arch arm64 -isysroot "$SDK" \
        -miphoneos-version-min=17.0 -O2 \
        -I"$W/include" -I"$W/include/wine" -I"$W/build-macos/include" \
        -I"$B" -I"$W/server" -I"$R/build/ntdll-unix/shims" \
        -I"$R/build/madsync" -DHAVE_LINUX_NTSYNC_H=1 \
        -include "$B/config_ios.h" -include stdarg.h \
        -include "$B/unicode_fix.h" -include "$B/wineserver_ios_kill.h" \
        -DBINDIR=\"/usr/local/bin\" -DDATADIR=\"/usr/local/share\" \
        -D__WINESRC__ -DWINE_IOS=1 -Dmain=wineserver_main \
        -Wno-implicit-function-declaration \
        -c "$W/server/$u.c" -o "$B/control-base/$u.o"
    done
    xcrun ar rcs "$A" "$B/control-base/"*.o
    bash "$B/build.sh" 2>&1 | tee "$E/wineserver-build.log"
    archive_evidence "$A"
    ;;
*) echo "Unknown stage: $STAGE"; exit 2 ;;
esac
