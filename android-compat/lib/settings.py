import json
import os
import pathlib
import sys


def _path():
    override = os.environ.get("ANDROID_COMPAT_SETTINGS_FILE")
    if override:
        return pathlib.Path(override)
    return pathlib.Path("/run/android-compat.settings.json")


def _load():
    path = _path()
    try:
        data = json.loads(path.read_text())
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return {}


def _save(data):
    path = _path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
        return True
    except OSError as exc:
        sys.stderr.write("settings: %s\n" % exc)
        return False


def usage(stream=sys.stdout):
    stream.write(
        "usage: settings [--user USER] get|put|delete|list "
        "NAMESPACE [KEY] [VALUE]\n")


def main(argv):
    args = []
    skip = False
    for arg in argv:
        if skip:
            skip = False
            continue
        if arg == "--user":
            skip = True
            continue
        if arg.startswith("--user="):
            continue
        args.append(arg)
    if not args or args[0] in ("-h", "--help"):
        usage(sys.stdout if args else sys.stderr)
        return 0 if args else 1
    if len(args) < 2:
        usage(sys.stderr)
        return 1

    action = args[0]
    namespace = args[1]
    data = _load()
    values = data.setdefault(namespace, {})

    if action == "get" and len(args) >= 3:
        print(values.get(args[2], "null"))
        return 0
    if action == "put" and len(args) >= 4:
        values[args[2]] = args[3]
        data[namespace] = values
        return 0 if _save(data) else 1
    if action == "delete" and len(args) >= 3:
        values.pop(args[2], None)
        data[namespace] = values
        return 0 if _save(data) else 1
    if action == "list":
        for key in sorted(values):
            print("%s=%s" % (key, values[key]))
        return 0
    usage(sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
