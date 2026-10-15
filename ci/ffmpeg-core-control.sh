#!/bin/bash
# iDeck source-only FFmpeg control. An outer wrapper enforces wall-clock limits.
set -euo pipefail
R=$(cd "${1:?source required}" && pwd)
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ]
XCODE=$(xcodebuild -version)
printf '%s\n' "$XCODE"
[ "${XCODE%%$'\n'*}" = 'Xcode 26.6' ]
[ "$(xcrun --sdk iphoneos --show-sdk-version)" = 26.5 ]
[ "$(git -C "$R" rev-parse HEAD)" = 279fd0f83170425db002fe25d6bd62f6355f497d ]
git -C "$R" diff --exit-code HEAD -- .
SDK=$(xcrun --sdk iphoneos --show-sdk-path)
MAKE=$(xcrun --find make)
SRC="$R/build/ffmpeg/control-source/ffmpeg-7.1.1"
BUILD="$R/build/ffmpeg/control-build"
PREFIX="$R/build/ffmpeg/control-prefix"
E="$R/build/ffmpeg/control-evidence"
[ ! -e "$BUILD" ] && [ ! -e "$PREFIX" ]
mkdir -p "$BUILD" "$PREFIX" "$E/tmp" "$E/pkgconfig-empty"
export TMPDIR="$E/tmp" LC_ALL=C
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH OBJC_INCLUDE_PATH LIBRARY_PATH \
 CC CXX CFLAGS CXXFLAGS CPPFLAGS LDFLAGS LIBS SDKROOT MACOSX_DEPLOYMENT_TARGET IPHONEOS_DEPLOYMENT_TARGET
export PKG_CONFIG_PATH= PKG_CONFIG_LIBDIR="$E/pkgconfig-empty"
HOSTCC=$(xcrun --sdk macosx --find clang)
HOST_SDK=$(xcrun --sdk macosx --show-sdk-path)
HOSTFLAGS="-arch arm64 -isysroot $SDK -miphoneos-version-min=17.0"
CONFIG_ARGS=(
    --prefix="$PREFIX"
    --enable-cross-compile
    --arch=aarch64
    --cpu=generic
    --target-os=darwin
    --sysroot="$SDK"
    --cc="$(xcrun -sdk iphoneos -f clang)"
    --cxx="$(xcrun -sdk iphoneos -f clang++)"
    --ar="$(xcrun -sdk iphoneos -f ar)"
    --ranlib="$(xcrun -sdk iphoneos -f ranlib)"
    --nm="$(xcrun -sdk iphoneos -f nm) -g"
    --strip="$(xcrun -sdk iphoneos -f strip)"
    "--extra-cflags=$HOSTFLAGS -fno-stack-protector -fvisibility=hidden -O2"
    "--extra-ldflags=$HOSTFLAGS -Wl,-no_adhoc_codesign"
    --disable-gpl
    --disable-nonfree
    --disable-version3
    --disable-everything
    --enable-decoder=wmav1,wmav2,wmapro,wmalossless,xma1,xma2
    --enable-decoder=mp1,mp2,mp3
    --enable-decoder=pcm_u8,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le,pcm_f64le
    --enable-demuxer=mp3,wav,mov
    --enable-parser=mpegaudio
    --disable-programs
    --disable-doc
    --disable-network
    --disable-avdevice
    --enable-avformat
    --disable-swscale
    --disable-avfilter
    --disable-postproc
    --enable-avcodec
    --enable-avutil
    --enable-swresample
    --disable-asm
    --disable-shared
    --enable-static
    --enable-pic
    --disable-iconv
    --disable-zlib
    --disable-bzlib
    --disable-lzma
    --disable-sdl2
    --disable-schannel
    --disable-securetransport
    --disable-audiotoolbox
    --disable-videotoolbox
    --disable-coreimage
    --disable-appkit
    --disable-avfoundation
    --disable-metal
    --disable-debug
)
# Native compiler probes stay native; target probes are cross-compiled, never run.
# Prevent host-installed optional libraries from changing the exact source control.
CONFIG_ARGS+=(--disable-autodetect --host-cc="$HOSTCC" "--host-cflags=-isysroot $HOST_SDK")
{ xcodebuild -version; xcrun --sdk iphoneos clang --version; "$MAKE" --version;
 printf 'SDK=%s\nHOST_SDK=%s\nHOSTCC=%s\n' "$SDK" "$HOST_SDK" "$HOSTCC";
} > "$E/toolchain.txt"
printf '%s\n' "${CONFIG_ARGS[@]}" > "$E/configure-arguments.txt"
cd "$BUILD"
"$SRC/configure" "${CONFIG_ARGS[@]}"
"$MAKE" -j4
"$MAKE" install-libs install-headers
for lib in avformat avcodec swresample avutil; do
 archive="$PREFIX/lib/lib$lib.a"
 test -s "$archive"
 xcrun ar -t "$archive" > "$E/lib$lib.members.txt"
 xcrun otool -l "$archive" > "$E/lib$lib.load-commands.txt"
 xcrun nm -g "$archive" > "$E/lib$lib.symbols.txt"
 xcrun lipo -info "$archive" > "$E/lib$lib.arch.txt"
done
git -C "$R" diff --exit-code HEAD -- .
