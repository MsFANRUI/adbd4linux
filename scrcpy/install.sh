#!/bin/sh
set -eu

prefix=${PREFIX:-/usr/local/lib/scrcpy-compat}
bindir=${BIN_DIR:-/usr/local/bin}
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

install -d "$prefix" "$bindir"
install -m 0755 "$script_dir/fake_server.py" "$prefix/fake_server.py"
install -m 0755 "$script_dir/app_process" "$bindir/app_process"
if [ -f "$script_dir/test.h264" ]; then
    install -m 0644 "$script_dir/test.h264" "$prefix/test.h264"
fi
printf 'installed scrcpy compatibility server under %s\n' "$prefix"
