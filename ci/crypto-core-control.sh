#!/bin/bash
# Reviewed source-only GnuTLS dependency control. No package installation.
# Usage: crypto-core-control.sh SOURCE_ROOT FRESH_SOURCE_DOTWORK_BUILD_ROOT
# A reviewed outer wrapper owns the aggregate timeout and cancellation.
set -euo pipefail
[ "$#" -eq 2 ] || { echo 'Usage: crypto-core-control.sh SOURCE_ROOT BUILD_ROOT' >&2; exit 2; }
HERE=$(cd "$(dirname "$0")" && pwd)
# -I ignores PYTHONPATH/user-site injection. The Python program builds a new,
# allowlisted environment before invoking any compiler/configure/build tool.
exec python3 -I "$HERE/crypto_control_support.py" "$1" "$2"
