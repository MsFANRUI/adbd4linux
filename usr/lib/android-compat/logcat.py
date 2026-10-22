# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import shutil
import subprocess
import sys


def usage(stream=sys.stdout):
    stream.write(
        "usage: logcat [-d] [-f FILE] [-s TAG] [-t COUNT] [-T COUNT]\n"
        "       Maps Android logcat to journalctl; -c does not clear logs.\n")


def main(argv):
    follow = True
    count = 200
    tag = None
    output = None
    index = 0

    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            usage()
            return 0
        elif arg == "-d":
            follow = False
        elif arg == "-f" and index + 1 < len(argv):
            output = argv[index + 1]
            index += 1
        elif arg == "-s" and index + 1 < len(argv):
            tag = argv[index + 1].split(":", 1)[0]
            index += 1
        elif arg in ("-t", "-T") and index + 1 < len(argv):
            try:
                count = int(argv[index + 1])
            except ValueError:
                pass
            if arg == "-t":
                follow = False
            index += 1
        elif arg in ("-v", "-b") and index + 1 < len(argv):
            index += 1
        elif arg == "-G" and index + 1 < len(argv):
            index += 1
        elif arg == "-c":
            sys.stderr.write("logcat: -c is a no-op; journald logs are not cleared\n")
            return 0
        elif arg == "-g":
            print("Log buffer size: 256 KiB")
            return 0
        elif arg == "-B":
            pass
        index += 1

    journalctl = shutil.which("journalctl")
    if not journalctl:
        sys.stderr.write("logcat: journalctl not found\n")
        return 1

    command = [journalctl, "-q", "--no-pager", "-n", str(count)]
    if tag:
        command += ["-g", tag]
    if follow:
        command.append("-f")

    try:
        if output:
            with open(output, "ab") as stream:
                return subprocess.call(command, stdout=stream)
        return subprocess.call(command)
    except KeyboardInterrupt:
        return 0
    except OSError as exc:
        sys.stderr.write("logcat: %s\n" % exc)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
