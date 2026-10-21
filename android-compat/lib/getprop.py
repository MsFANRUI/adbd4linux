import sys

import props


def usage(stream=sys.stdout):
    stream.write("usage: getprop [KEY]\n")


def main(argv):
    if argv and argv[0] in ("-h", "--help"):
        usage()
        return 0
    values = props.load()
    if not argv:
        for key in sorted(values):
            print("[%s]: [%s]" % (key, values[key]))
        return 0
    if len(argv) > 1:
        usage(sys.stderr)
        return 1
    print(values.get(argv[0], ""))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
