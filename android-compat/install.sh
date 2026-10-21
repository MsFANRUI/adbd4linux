#!/bin/sh
set -eu

prefix=${PREFIX:-/usr/local}
libdir="$prefix/lib/android-compat"
bindir="$prefix/bin"
script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
commands="screencap screenrecord input getprop setprop wm logcat dumpsys settings"

install -d "$libdir" "$bindir"
for module in "$script_dir"/lib/*.py; do
    install -m 0644 "$module" "$libdir/$(basename "$module")"
done
for command in $commands; do
    install -m 0755 "$script_dir/bin/_wrapper" "$bindir/$command"
done

printf 'installed android-compat to %s (lib: %s)\n' "$bindir" "$libdir"
