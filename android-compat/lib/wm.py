import sys

import common


def usage(stream=sys.stdout):
    stream.write("usage: wm size [reset]\n       wm density\n")


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        usage()
        return 0 if argv else 1
    if argv[0] == "size":
        width, height = common.screen_size()
        if len(argv) > 1 and argv[1] != "reset":
            sys.stderr.write("wm: changing the Xvfb screen size is not supported\n")
            return 1
        print("Physical size: %dx%d" % (width, height))
        return 0
    if argv[0] == "density":
        if len(argv) > 1:
            sys.stderr.write("wm: changing density is not supported\n")
            return 1
        print("Physical density: 160")
        return 0
    if argv[0] == "overscan":
        print("android-compat: overscan is not supported")
        return 0
    usage(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
