#!/usr/bin/env python3
"""Audit the BSP launcher offline; never access host USB or execute systemctl."""
import configparser
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile


def main():
    source = Path(sys.argv[1]).read_text()
    payloads = {}
    for index in range(5):
        marker = f"__ADBD_PAYLOAD_{index}__"
        match = re.search(r"cat <<'" + marker + r"'[^\n]*\n(.*?)\n" + marker,
                          source, re.DOTALL)
        if not match:
            raise RuntimeError(f"missing payload {marker}")
        payloads[index] = match.group(1) + "\n"

    with tempfile.TemporaryDirectory(prefix="service-audit-", dir="build") as directory:
        root = Path(directory).resolve()
        helper = root / "usbdevice"
        # Remap every device/configuration path before executing any script branch.
        script = payloads[0]
        for old, new in {
            "/sys/kernel/config": str(root / "configfs"),
            "/sys/class/udc": str(root / "udc"),
            "/dev/usb-ffs/adb": str(root / "ffs"),
            "/etc/default/adbd-gadget": str(root / "defaults"),
            "/proc/device-tree": str(root / "device-tree"),
            "/etc/machine-id": str(root / "machine-id"),
            "/usr/bin/adbd": str(root / "missing-adbd"),
            "/tmp/adbd.log": str(root / "adbd.log"),
        }.items():
            script = script.replace(old, new)
        helper.write_text(script)
        helper.chmod(0o755)
        # Fail closed if a tested branch unexpectedly attempts system mutation.
        bin_dir = root / "bin"
        bin_dir.mkdir()
        for name in ("mount", "umount", "pkill", "setsid", "modprobe", "systemctl"):
            command = bin_dir / name
            command.write_text('#!/bin/sh\necho "BLOCKED: unexpected command" >&2\nexit 99\n')
            command.chmod(0o755)
        env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin")
        subprocess.run(["sh", "-n", str(helper)], check=True)
        for index in (2, 4):
            subprocess.run(["sh", "-n"], input=payloads[index], text=True, check=True)

        def run(action):
            return subprocess.run([str(helper), action], env=env, text=True,
                                  capture_output=True, timeout=5)

        result = run("start")
        assert result.returncode == 0 and "no USB Device Controller" in result.stdout
        result = run("status")
        assert result.returncode == 0 and "inactive" in result.stdout
        result = run("invalid")
        assert result.returncode == 1 and "Usage:" in result.stderr
        print("PASS: shell syntax; no-UDC start; inactive status; invalid argument")

        (root / "udc" / "fake-controller").mkdir(parents=True)
        gadget = root / "configfs" / "usb_gadget" / "adbd"
        gadget.mkdir(parents=True)
        (gadget / "UDC").write_text("fake-controller\n")
        result = run("start")
        assert result.returncode == 0 and "already bound" in result.stdout
        result = run("status")
        assert result.returncode == 0 and "active (udc=" in result.stdout
        assert not (root / "missing-adbd").exists()
        print("CONFIRMED GAP: bound gadget reports active/start success without an adbd executable")

        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(payloads[1])
        assert parser["Service"]["Type"] == "oneshot"
        assert parser["Service"]["RemainAfterExit"] == "yes"
        print("CONFIRMED GAP: oneshot service tracks launcher completion, not daemon liveness")
        # Map the Exec path for verifier existence checks; never start the unit.
        unit = root / "usbdevice.service"
        unit.write_text(payloads[1].replace("/usr/bin/usbdevice", str(helper)))
        subprocess.run(["systemd-analyze", "verify", str(unit)], check=True)
        print("PASS: systemd unit verification with Exec path mapped to extracted helper")
        assert "libcomposite" in payloads[3] and "usb_f_fs" in payloads[3]
        assert "os_desc/use" not in payloads[0]
        print("REVIEW: modules declared; Windows OS descriptor configfs enablement absent")


if __name__ == "__main__":
    main()
