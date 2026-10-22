# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import os
import subprocess
import sys

import common


def usage(stream=sys.stdout):
    stream.write("usage: screencap [-p] [-d DISPLAY_ID] [FILENAME]\n")


def main(argv):
    png = False
    filename = None
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            usage()
            return 0
        elif arg == "-p":
            png = True
        elif arg == "-d":
            index += 1
        elif arg.startswith("-d"):
            pass
        elif arg.startswith("-"):
            sys.stderr.write("screencap: unknown option %s\n" % arg)
            return 1
        else:
            filename = arg
        index += 1

    width, height = common.screen_size()
    command = [
        common.ffmpeg(), "-hide_banner", "-loglevel", "error",
        "-f", "x11grab", "-draw_mouse", "0",
        "-video_size", "%dx%d" % (width, height),
        "-framerate", "30", "-i", common.DISPLAY,
        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-",
    ]
    try:
        if filename:
            with open(filename, "wb") as output:
                return subprocess.call(command, stdout=output)
        return subprocess.call(command, stdout=sys.stdout.buffer)
    except OSError as exc:
        sys.stderr.write("screencap: %s\n" % exc)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
