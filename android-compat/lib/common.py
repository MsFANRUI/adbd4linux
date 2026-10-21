import os
import shutil
import subprocess

DISPLAY = (os.environ.get("ANDROID_COMPAT_DISPLAY")
           or os.environ.get("SCRCPY_COMPAT_DISPLAY")
           or ":99")


def ffmpeg():
    return shutil.which("ffmpeg") or "/usr/bin/ffmpeg"


def screen_size():
    width = int(os.environ.get("ANDROID_COMPAT_WIDTH", "1280"))
    height = int(os.environ.get("ANDROID_COMPAT_HEIGHT", "720"))
    xwininfo = shutil.which("xwininfo")
    if xwininfo:
        try:
            result = subprocess.run([xwininfo, "-display", DISPLAY, "-root"],
                                    capture_output=True, text=True, timeout=3)
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Width:"):
                    width = int(line.split(":", 1)[1])
                elif line.startswith("Height:"):
                    height = int(line.split(":", 1)[1])
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    return width, height
