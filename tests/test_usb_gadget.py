#!/usr/bin/env python3
"""Regression checks for the packaged FunctionFS gadget manager."""
import configparser
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parent.parent
GADGET = ROOT / "usb-gadget"


def main():
    helper_src = (GADGET / "usbdevice").read_text()
    service_src = (GADGET / "usbdevice.service").read_text()
    defaults_src = (GADGET / "adbd-gadget").read_text()
    modules_src = (GADGET / "usb-gadget.conf").read_text()
    profile_src = (GADGET / "usbdevice.sh").read_text()

    assert os.access(GADGET / "usbdevice", os.X_OK)
    assert "libcomposite" in modules_src and "usb_f_fs" in modules_src

    with tempfile.TemporaryDirectory(prefix="usb-gadget-test-") as directory:
        root = Path(directory).resolve()
        helper = root / "usbdevice"
        script = helper_src
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
        (root / "defaults").write_text(defaults_src)

        # Fail closed if a tested branch unexpectedly attempts system mutation.
        bin_dir = root / "bin"
        bin_dir.mkdir()
        for name in ("mount", "umount", "pkill", "setsid", "modprobe", "systemctl"):
            command = bin_dir / name
            command.write_text('#!/bin/sh\necho "BLOCKED: unexpected command" >&2\nexit 99\n')
            command.chmod(0o755)
        env = dict(os.environ, PATH=f"{bin_dir}:/usr/bin:/bin")

        subprocess.run(["sh", "-n", str(helper)], check=True)
        subprocess.run(["sh", "-n"], input=profile_src, text=True, check=True)

        def run(action):
            return subprocess.run([str(helper), action], env=env, text=True,
                                  capture_output=True, timeout=5)

        result = run("start")
        assert result.returncode == 0 and "no USB Device Controller" in result.stdout
        result = run("status")
        assert result.returncode == 0 and "inactive" in result.stdout
        result = run("invalid")
        assert result.returncode == 1 and "Usage:" in result.stderr
        print("PASS: syntax; no-UDC start; inactive status; invalid argument")

        (root / "udc" / "fake-controller").mkdir(parents=True)
        gadget = root / "configfs" / "usb_gadget" / "adbd"
        gadget.mkdir(parents=True)
        (gadget / "UDC").write_text("fake-controller\n")
        result = run("start")
        assert result.returncode == 0 and "already bound" in result.stdout
        result = run("status")
        assert result.returncode == 0 and "active (udc=" in result.stdout
        assert not (root / "missing-adbd").exists()
        print("PASS: bound gadget reported; no adbd launched by this branch")

        parser = configparser.ConfigParser(interpolation=None)
        parser.read_string(service_src)
        assert parser["Service"]["Type"] == "oneshot"
        assert parser["Service"]["RemainAfterExit"] == "yes"
        assert parser["Service"]["ExecStart"] == "/usr/bin/usbdevice start"
        assert parser["Service"]["ExecStop"] == "/usr/bin/usbdevice stop"
        assert "ADBD_SHELL=/bin/bash" in parser["Service"]["Environment"]
        print("PASS: systemd unit fields")

        unit = root / "usbdevice.service"
        unit.write_text(service_src.replace("/usr/bin/usbdevice", str(helper)))
        verifier = shutil.which("systemd-analyze")
        if verifier:
            result = subprocess.run([verifier, "verify", str(unit)],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                print("PASS: systemd-analyze verify")
            else:
                print("WARN: systemd-analyze verify:", result.stderr.strip())
        else:
            print("SKIP: systemd-analyze not available")

        install = (ROOT / "debian" / "adbd.install").read_text()
        for line in install.splitlines():
            source = line.split()[0]
            assert (ROOT / source).is_file(), source
        links = (ROOT / "debian" / "adbd.links").read_text().split()
        assert links[0] == "/usr/lib/systemd/system/usbdevice.service"
        assert links[1] == "etc/systemd/system/sysinit.target.wants/usbdevice.service"
        print("PASS: packaging paths")

        assert "os_desc/use" not in script
        print("REVIEW: Windows OS descriptor configfs setup is BSP-owned")


if __name__ == "__main__":
    main()
