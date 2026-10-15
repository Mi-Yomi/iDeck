#!/bin/bash
# Local proposal. The outer control supplies the aggregate/provider timeout.
set -euo pipefail
if [[ $# -lt 3 || $# -gt 4 ]]; then
  printf '%s\n' 'usage: llvm-core-control.sh SOURCE_ROOT BUILD_ROOT native|target [NATIVE_CONTROL_ROOT]' >&2
  exit 2
fi
HERE=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 -I "$HERE/llvm_control_support.py" "$@"
