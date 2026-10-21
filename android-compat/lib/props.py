import os
import pathlib
import socket


def _serial():
    for path in ("/proc/device-tree/serial-number",
                 "/sys/class/net/eth0/address"):
        try:
            value = pathlib.Path(path).read_text(errors="ignore").strip("\x00\n ")
            if value:
                return value
        except OSError:
            pass
    return socket.gethostname()


def _overlay_paths():
    override = os.environ.get("ANDROID_COMPAT_PROP_FILE")
    if override:
        return [pathlib.Path(override)]
    return [pathlib.Path("/run/android-compat.properties"),
            pathlib.Path.home() / ".android-compat.properties"]


def _defaults():
    serial = _serial()
    return {
        "ro.product.model": "RoboPi2",
        "ro.product.brand": "RoboParty",
        "ro.product.device": "robopi2",
        "ro.product.name": "robopi2",
        "ro.product.manufacturer": "RoboParty",
        "ro.product.cpu.abi": "arm64-v8a",
        "ro.product.cpu.abilist": "arm64-v8a",
        "ro.board.platform": "rk3588",
        "ro.hardware": "rockchip",
        "ro.build.version.sdk": "35",
        "ro.build.version.release": "15",
        "ro.build.version.incremental": "android-compat",
        "ro.build.type": "userdebug",
        "ro.build.tags": "test-keys",
        "ro.build.fingerprint": "RoboParty/robopi2/robopi2:15/AC/eng.root:userdebug/test-keys",
        "ro.debuggable": "1",
        "ro.secure": "0",
        "ro.adb.secure": "0",
        "ro.kernel.qemu": "0",
        "ro.boot.serialno": serial,
        "ro.serialno": serial,
        "sys.boot_completed": "1",
        "persist.sys.usb.config": "adb",
    }


def _read_overlay(path):
    values = {}
    try:
        for line in path.read_text(errors="ignore").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


def load():
    values = _defaults()
    for path in _overlay_paths():
        values.update(_read_overlay(path))
    return values


def set_prop(key, value):
    errors = []
    for path in _overlay_paths():
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            values = _read_overlay(path)
            values[key] = value
            path.write_text("".join("%s=%s\n" % (k, v)
                                    for k, v in sorted(values.items())))
            return path
        except OSError as exc:
            errors.append(str(exc))
    raise OSError("; ".join(errors) or "no writable property file")
