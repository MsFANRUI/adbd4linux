# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import os
import sys

import common


def usage(stream=sys.stdout):
    stream.write(
        "usage: screenrecord [--size WxH] [--bit-rate BPS] "
        "[--time-limit SECONDS] [--rotate] FILENAME\n")


def parse_size(value):
    parts = value.lower().split("x")
    if len(parts) != 2:
        raise ValueError(value)
    return int(parts[0]), int(parts[1])


def parse_rate(value):
    value = value.strip().lower()
    multiplier = 1
    if value.endswith("k"):
        multiplier = 1000
        value = value[:-1]
    elif value.endswith("m"):
        multiplier = 1000000
        value = value[:-1]
    return int(float(value) * multiplier)


def main(argv):
    width, height = common.screen_size()
    bitrate = 4000000
    time_limit = 180
    rotate = False
    filename = None
    index = 0

    while index < len(argv):
        arg = argv[index]
        if arg in ("-h", "--help"):
            usage()
            return 0
        elif arg == "--size" and index + 1 < len(argv):
            width, height = parse_size(argv[index + 1])
            index += 1
        elif arg.startswith("--size="):
            width, height = parse_size(arg.split("=", 1)[1])
        elif arg == "--bit-rate" and index + 1 < len(argv):
            bitrate = parse_rate(argv[index + 1])
            index += 1
        elif arg.startswith("--bit-rate="):
            bitrate = parse_rate(arg.split("=", 1)[1])
        elif arg == "--time-limit" and index + 1 < len(argv):
            time_limit = int(argv[index + 1])
            index += 1
        elif arg.startswith("--time-limit="):
            time_limit = int(arg.split("=", 1)[1])
        elif arg == "--rotate":
            rotate = True
        elif arg == "--verbose":
            pass
        elif arg.startswith("-"):
            sys.stderr.write("screenrecord: unknown option %s\n" % arg)
            return 1
        else:
            filename = arg
        index += 1

    if not filename:
        usage(sys.stderr)
        return 1
    if rotate:
        width, height = height, width

    command = [
        common.ffmpeg(), "-hide_banner", "-loglevel", "error", "-y",
        "-f", "x11grab", "-draw_mouse", "1",
        "-video_size", "%dx%d" % (width, height),
        "-framerate", "30", "-i", common.DISPLAY,
        "-t", str(time_limit), "-c:v", "libx264", "-preset", "ultrafast",
        "-tune", "zerolatency", "-b:v", str(bitrate), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", filename,
    ]
    try:
        os.execvp(command[0], command)
    except OSError as exc:
        sys.stderr.write("screenrecord: %s\n" % exc)
        return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
