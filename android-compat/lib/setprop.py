import sys

import props


def usage(stream=sys.stdout):
    stream.write("usage: setprop KEY VALUE\n")


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        usage()
        return 0
    if len(argv) != 2:
        usage(sys.stderr)
        return 1
    try:
        props.set_prop(argv[0], argv[1])
    except OSError as exc:
        sys.stderr.write("setprop: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
