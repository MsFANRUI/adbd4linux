# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import glob
import os
import pathlib
import shutil
import subprocess
import sys

import common


def run(command, limit=None, timeout=4):
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                 timeout=timeout)
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write("dumpsys: %s: %s\n" % (command[0], exc))
        return
    lines = result.stdout.rstrip().splitlines()
    if limit:
        lines = lines[:limit]
    if lines:
        print("\n".join(lines))


def read_file(path, limit=None):
    try:
        lines = pathlib.Path(path).read_text(errors="ignore").splitlines()
    except OSError:
        return
    if limit:
        lines = lines[:limit]
    if lines:
        print("\n".join(lines))


def header(name):
    print("== %s ==" % name)


def section_uptime():
    run(["uptime"])


def section_meminfo():
    run(["free", "-h"])
    read_file("/proc/meminfo", limit=12)


def section_cpuinfo():
    run(["ps", "-eo", "pid,pcpu,pmem,comm", "--sort=-pcpu"], limit=20)


def section_can():
    if shutil.which("ip"):
        run(["ip", "-details", "-statistics", "link", "show", "type", "can"])


def section_thermal():
    for path in sorted(glob.glob("/sys/class/thermal/thermal_zone*/temp")):
        try:
            value = int(pathlib.Path(path).read_text().strip())
        except (OSError, ValueError):
            continue
        zone = pathlib.Path(path).parent
        try:
            kind = (zone / "type").read_text().strip()
        except OSError:
            kind = "thermal"
        print("%s: %.1f C" % (kind, value / 1000.0))


def section_power():
    for path in sorted(glob.glob("/sys/class/power_supply/*/uevent")):
        print("-- %s --" % path)
        read_file(path, limit=20)


def section_display():
    if shutil.which("xwininfo"):
        run(["xwininfo", "-display", common.DISPLAY, "-root", "-tree"], limit=40)


def section_adb():
    try:
        result = subprocess.run(["ps", "-eo", "pid,args"], capture_output=True,
                                text=True, timeout=4)
        for line in result.stdout.splitlines():
            if any(name in line for name in ("adbd", "fake_server", "app_process")):
                print(line)
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write("dumpsys: ps: %s\n" % exc)
    if shutil.which("ss"):
        run(["ss", "-ltnp"])


def section_activity():
    section_cpuinfo()


SECTIONS = {
    "uptime": section_uptime,
    "meminfo": section_meminfo,
    "cpuinfo": section_cpuinfo,
    "activity": section_activity,
    "can": section_can,
    "thermal": section_thermal,
    "power": section_power,
    "battery": section_power,
    "display": section_display,
    "adb": section_adb,
}


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        print("usage: dumpsys [%s]" % "|".join(sorted(SECTIONS)))
        return 0
    if not argv:
        for name in ("uptime", "meminfo", "cpuinfo", "can", "thermal",
                     "power", "display", "adb"):
            header(name)
            SECTIONS[name]()
        return 0
    name = argv[0].lower()
    if name not in SECTIONS:
        sys.stderr.write("dumpsys: unknown section %s\n" % argv[0])
        sys.stderr.write("available: %s\n" % " ".join(sorted(SECTIONS)))
        return 1
    header(name)
    SECTIONS[name]()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
