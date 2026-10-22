# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import glob
import os
import pathlib
import platform
import socket

DT_ROOT = pathlib.Path("/proc/device-tree")
DT_FALLBACK = pathlib.Path("/sys/firmware/devicetree/base")
DMI_ROOT = pathlib.Path("/sys/class/dmi/id")


def _read(path):
    try:
        return pathlib.Path(path).read_text(errors="ignore").strip("\x00\n ")
    except OSError:
        return ""


def _first(*values):
    for value in values:
        if value:
            return value
    return ""


def _dt(name):
    return _first(_read(DT_ROOT / name), _read(DT_FALLBACK / name))


def _dt_strings(name):
    for root in (DT_ROOT, DT_FALLBACK):
        try:
            raw = (root / name).read_text(errors="ignore")
        except OSError:
            continue
        strings = [item.strip("\x00\n ") for item in raw.split("\x00")]
        strings = [item for item in strings if item]
        if strings:
            return strings
    return []


def _dmi(name):
    return _read(DMI_ROOT / name)


def _slug(value):
    result = []
    for char in value.lower():
        if char.isalnum():
            result.append(char)
        elif result and result[-1] != "-":
            result.append("-")
    return "".join(result).strip("-") or "linux"


def _serial():
    candidates = [
        _dt("serial-number"),
        _dmi("product_serial"),
        _dmi("board_serial"),
    ]
    for path in sorted(glob.glob("/sys/class/net/*/address")):
        candidates.append(_read(path))
    candidates.append(socket.gethostname())
    for value in candidates:
        if value and value != "00:00:00:00:00:00":
            return value
    return "unknown"


def _abi():
    machine = platform.machine().lower()
    return {
        "aarch64": "arm64-v8a",
        "arm64": "arm64-v8a",
        "armv7l": "armeabi-v7a",
        "armv7": "armeabi-v7a",
        "x86_64": "x86_64",
        "amd64": "x86_64",
        "i386": "x86",
        "i686": "x86",
    }.get(machine, machine or "unknown")


def _platform(compatible):
    soc = _first(_read("/sys/devices/soc0/machine"),
                 _read("/sys/devices/soc0/family"))
    if soc:
        return soc.strip()
    for value in compatible:
        _, _, model = value.partition(",")
        model = model.strip()
        if model:
            return model
    return _first(_dmi("product_name"), _dmi("board_name"),
                  platform.machine(), "unknown").strip() or "unknown"


def _hardware(compatible):
    for value in compatible:
        vendor = value.partition(",")[0].strip()
        if vendor:
            return vendor
    return _slug(_first(_dmi("board_vendor"), _dmi("sys_vendor"),
                        platform.machine(), "unknown"))


def _compatible_vendor(compatible):
    for value in compatible:
        vendor = value.partition(",")[0].strip()
        if vendor:
            return vendor
    return ""


def _overlay_paths():
    override = os.environ.get("ANDROID_COMPAT_PROP_FILE")
    if override:
        return [pathlib.Path(override)]
    return [pathlib.Path("/etc/android-compat.properties"),
            pathlib.Path("/run/android-compat.properties"),
            pathlib.Path.home() / ".android-compat.properties"]


def _defaults():
    compatible = _dt_strings("compatible")
    model = _first(_dt("model"), _dmi("product_name"), _dmi("board_name"),
                   "Linux")
    brand = _first(_dt("manufacturer"), _dt("vendor"),
                   _dmi("sys_vendor"), _dmi("board_vendor"),
                   _compatible_vendor(compatible), "Linux")
    device = _slug(model)
    abi = _abi()
    release = os.environ.get("ANDROID_COMPAT_RELEASE", "15")
    sdk = os.environ.get("ANDROID_COMPAT_SDK", "35")
    build_id = os.environ.get("ANDROID_COMPAT_BUILD_ID", "AC")
    incremental = os.environ.get("ANDROID_COMPAT_INCREMENTAL", "android-compat")
    build_type = os.environ.get("ANDROID_COMPAT_BUILD_TYPE", "userdebug")
    tags = os.environ.get("ANDROID_COMPAT_BUILD_TAGS", "test-keys")
    qemu = "1" if "qemu" in (_dmi("sys_vendor") + _dmi("product_name")).lower() else "0"
    serial = _serial()
    return {
        "ro.product.model": model,
        "ro.product.brand": brand,
        "ro.product.device": device,
        "ro.product.name": device,
        "ro.product.manufacturer": brand,
        "ro.product.cpu.abi": abi,
        "ro.product.cpu.abilist": abi,
        "ro.board.platform": _platform(compatible),
        "ro.hardware": _hardware(compatible),
        "ro.build.version.sdk": sdk,
        "ro.build.version.release": release,
        "ro.build.version.incremental": incremental,
        "ro.build.type": build_type,
        "ro.build.tags": tags,
        "ro.build.fingerprint": "%s/%s/%s:%s/%s/%s:%s/%s" % (
            _slug(brand), device, device, release, build_id, incremental,
            build_type, tags),
        "ro.debuggable": "1",
        "ro.secure": "0",
        "ro.adb.secure": "0",
        "ro.kernel.qemu": qemu,
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
