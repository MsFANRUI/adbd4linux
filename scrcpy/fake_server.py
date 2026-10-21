#!/usr/bin/env python3
"""Small scrcpy 5.x compatibility server for a Linux target.

This is intentionally a protocol probe: it emits a bundled H.264 test stream
and maps the two useful control messages to Linux uinput. The capture backend
is kept separate so a DRM/KMS source can replace the test stream later.
"""

import fcntl
import ctypes
import os
import pathlib
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent
STREAM = pathlib.Path(os.environ.get("SCRCPY_COMPAT_STREAM", ROOT / "test.h264"))
DISPLAY = os.environ.get("SCRCPY_COMPAT_DISPLAY", "")
WIDTH = int(os.environ.get("SCRCPY_COMPAT_WIDTH", "1280" if DISPLAY else "320"))
HEIGHT = int(os.environ.get("SCRCPY_COMPAT_HEIGHT", "720" if DISPLAY else "240"))

EV_SYN = 0x00
EV_KEY = 0x01
EV_ABS = 0x03
SYN_REPORT = 0
BTN_TOUCH = 0x14a
ABS_X = 0x00
ABS_Y = 0x01

UI_SET_EVBIT = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_ABSBIT = 0x40045567
UI_DEV_CREATE = 0x5501
UI_DEV_DESTROY = 0x5502

KEY_ESC = 1
KEY_ENTER = 28
KEY_BACKSPACE = 14
KEY_TAB = 15
KEY_SPACE = 57
KEY_LEFT = 105
KEY_RIGHT = 106
KEY_UP = 103
KEY_DOWN = 108
KEY_A = 30


def read_exact(sock, size):
    data = bytearray()
    while len(data) < size:
        block = sock.recv(size - len(data))
        if not block:
            raise EOFError
        data.extend(block)
    return bytes(data)


def write_all(sock, data):
    view = memoryview(data)
    while view:
        view = view[sock.send(view):]


def input_event(event_type, code, value):
    return struct.pack("llHHi", 0, 0, event_type, code, value)


class UInput:
    def __init__(self):
        self.fd = None
        try:
            self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_KEY)
            fcntl.ioctl(self.fd, UI_SET_EVBIT, EV_ABS)
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, ABS_X)
            fcntl.ioctl(self.fd, UI_SET_ABSBIT, ABS_Y)
            fcntl.ioctl(self.fd, UI_SET_KEYBIT, BTN_TOUCH)
            for code in range(KEY_A, KEY_A + 26):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            for code in (KEY_ESC, KEY_ENTER, KEY_BACKSPACE, KEY_TAB, KEY_SPACE,
                         KEY_LEFT, KEY_RIGHT, KEY_UP, KEY_DOWN):
                fcntl.ioctl(self.fd, UI_SET_KEYBIT, code)
            ident = struct.pack("HHHHI", 3, 0x1209, 0x0001, 1, 0)
            absmax = [WIDTH - 1, HEIGHT - 1] + [0] * 62
            payload = struct.pack("80s", b"RoboPi2 scrcpy compat")
            payload += ident
            payload += struct.pack("i" * 64, *absmax)
            payload += struct.pack("i" * 64, *([0] * 64))
            payload += struct.pack("i" * 64, *([0] * 64))
            payload += struct.pack("i" * 64, *([0] * 64))
            os.write(self.fd, payload)
            fcntl.ioctl(self.fd, UI_DEV_CREATE)
        except OSError as exc:
            print("uinput unavailable: %s" % exc, file=sys.stderr, flush=True)
            self.close()

    def emit(self, event_type, code, value):
        if self.fd is not None:
            os.write(self.fd, input_event(event_type, code, value))

    def sync(self):
        self.emit(EV_SYN, SYN_REPORT, 0)

    def close(self):
        if self.fd is not None:
            try:
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            except OSError:
                pass
            os.close(self.fd)
            self.fd = None


class X11Input:
    def __init__(self):
        self.display = None
        if not DISPLAY:
            return
        try:
            self.x11 = ctypes.CDLL("libX11.so.6")
            self.xtst = ctypes.CDLL("libXtst.so.6")
            self.x11.XOpenDisplay.restype = ctypes.c_void_p
            self.x11.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.x11.XDefaultScreen.argtypes = [ctypes.c_void_p]
            self.x11.XDefaultScreen.restype = ctypes.c_int
            self.x11.XRootWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
            self.x11.XRootWindow.restype = ctypes.c_ulong
            self.x11.XStringToKeysym.argtypes = [ctypes.c_char_p]
            self.x11.XStringToKeysym.restype = ctypes.c_ulong
            self.x11.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            self.x11.XKeysymToKeycode.restype = ctypes.c_ubyte
            self.x11.XWarpPointer.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong,
                                              ctypes.c_int, ctypes.c_int, ctypes.c_uint,
                                              ctypes.c_uint, ctypes.c_int, ctypes.c_int]
            self.xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                       ctypes.c_int, ctypes.c_ulong]
            self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                    ctypes.c_int, ctypes.c_ulong]
            self.xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                       ctypes.c_int, ctypes.c_int, ctypes.c_ulong]
            self.x11.XDisplayKeycodes.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                                  ctypes.POINTER(ctypes.c_int)]
            self.x11.XGetKeyboardMapping.argtypes = [ctypes.c_void_p, ctypes.c_ubyte,
                                                     ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
            self.x11.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
            self.x11.XFree.argtypes = [ctypes.c_void_p]
            self.x11.XFree.restype = ctypes.c_int
            self.x11.XFlush.argtypes = [ctypes.c_void_p]
            self.display = self.x11.XOpenDisplay(DISPLAY.encode())
            if not self.display:
                return
            self.screen = self.x11.XDefaultScreen(self.display)
            self.root = self.x11.XRootWindow(self.display, self.screen)
            self.shift_code = self.x11.XKeysymToKeycode(self.display, 0xFFE1)
            self.keymap = {}
            lo = ctypes.c_int()
            hi = ctypes.c_int()
            self.x11.XDisplayKeycodes(self.display, ctypes.byref(lo), ctypes.byref(hi))
            count = hi.value - lo.value + 1
            per = ctypes.c_int()
            syms = self.x11.XGetKeyboardMapping(self.display, lo.value, count, ctypes.byref(per))
            if syms:
                for index in range(count):
                    keycode = lo.value + index
                    for level in range(min(per.value, 2)):
                        keysym = syms[index * per.value + level]
                        if keysym and keysym not in self.keymap:
                            self.keymap[keysym] = (keycode, level == 1)
                self.x11.XFree(syms)
        except (AttributeError, OSError):
            self.display = None

    def keysym_code(self, name):
        if not self.display:
            return 0
        sym = self.x11.XStringToKeysym(name.encode())
        return self.x11.XKeysymToKeycode(self.display, sym) if sym else 0

    def key(self, name, down, shift=False):
        code = self.keysym_code(name)
        if code:
            if shift and down and self.shift_code:
                self.xtst.XTestFakeKeyEvent(self.display, self.shift_code, 1, 0)
            self.xtst.XTestFakeKeyEvent(self.display, code, int(down), 0)
            if shift and down and self.shift_code:
                self.xtst.XTestFakeKeyEvent(self.display, self.shift_code, 0, 0)
            self.x11.XFlush(self.display)

    def text(self, content):
        if not self.display:
            return
        special = {"\n": 0xFF0D, "\r": 0xFF0D, "\t": 0xFF09, "\b": 0xFF08}
        for char in content:
            keysym = special.get(char, ord(char))
            if keysym > 0xFF and keysym not in special.values():
                continue
            entry = self.keymap.get(keysym)
            if not entry:
                continue
            code, shift = entry
            if shift and self.shift_code:
                self.xtst.XTestFakeKeyEvent(self.display, self.shift_code, 1, 0)
            self.xtst.XTestFakeKeyEvent(self.display, code, 1, 0)
            self.xtst.XTestFakeKeyEvent(self.display, code, 0, 0)
            if shift and self.shift_code:
                self.xtst.XTestFakeKeyEvent(self.display, self.shift_code, 0, 0)
        self.x11.XFlush(self.display)

    def touch(self, action, x, y, width, height):
        if not self.display:
            return
        px = max(0, min(WIDTH - 1, x * WIDTH // max(1, width)))
        py = max(0, min(HEIGHT - 1, y * HEIGHT // max(1, height)))
        self.xtst.XTestFakeMotionEvent(self.display, self.screen, px, py, 0)
        if action in (0, 5):
            self.xtst.XTestFakeButtonEvent(self.display, 1, 1, 0)
        elif action in (1, 6, 3):
            self.xtst.XTestFakeButtonEvent(self.display, 1, 0, 0)
        self.x11.XFlush(self.display)

    def scroll(self, x, y, width, height, hscroll, vscroll):
        if not self.display:
            return
        self.touch(2, x, y, width, height)
        button = 4 if vscroll > 0 else 5
        for _ in range(max(1, abs(vscroll) // 4096)):
            self.xtst.XTestFakeButtonEvent(self.display, button, 1, 0)
            self.xtst.XTestFakeButtonEvent(self.display, button, 0, 0)
        self.x11.XFlush(self.display)

    def close(self):
        if self.display:
            self.x11.XCloseDisplay(self.display)
            self.display = None


def android_key_to_linux(keycode):
    if 29 <= keycode <= 54:
        return KEY_A + keycode - 29
    return {
        4: KEY_ESC,
        66: KEY_ENTER,
        67: KEY_BACKSPACE,
        61: KEY_TAB,
        62: KEY_SPACE,
        19: KEY_UP,
        20: KEY_DOWN,
        21: KEY_LEFT,
        22: KEY_RIGHT,
    }.get(keycode)


def handle_control(sock, ui, xinput):
    try:
        while True:
            msg_type = read_exact(sock, 1)[0]
            if msg_type == 0:  # inject keycode
                action, keycode, _repeat, meta = struct.unpack(">BIII", read_exact(sock, 13))
                shift = bool(meta & 0xC1)
                code = android_key_to_linux(keycode)
                if xinput.display:
                    names = {4: "Escape", 66: "Return", 67: "BackSpace", 61: "Tab",
                             62: "space", 19: "Up", 20: "Down", 21: "Left", 22: "Right"}
                    name = names.get(keycode, chr(ord("a") + keycode - 29) if 29 <= keycode <= 54 else None)
                    if name:
                        xinput.key(name, action != 1, shift)
                elif code is not None:
                    ui.emit(EV_KEY, code, 0 if action == 1 else 1)
                    ui.sync()
            elif msg_type == 1:  # inject text
                size = struct.unpack(">I", read_exact(sock, 4))[0]
                text = read_exact(sock, size).decode("utf-8", "ignore")
                xinput.text(text)
            elif msg_type == 9:  # set clipboard
                read_exact(sock, 9)
                size = struct.unpack(">I", read_exact(sock, 4))[0]
                read_exact(sock, size)
            elif msg_type in (8, 10, 18):  # clipboard/power/torch flag
                read_exact(sock, 1)
            elif msg_type == 21:  # resize display
                read_exact(sock, 4)
            elif msg_type in (5, 6, 7, 11, 15, 17, 19, 20):
                pass
            elif msg_type == 2:  # inject touch event
                action = read_exact(sock, 1)[0]
                _pointer_id = struct.unpack(">Q", read_exact(sock, 8))[0]
                x, y, screen_w, screen_h = struct.unpack(">iiHH", read_exact(sock, 12))
                pressure = struct.unpack(">H", read_exact(sock, 2))[0]
                _action_button, _buttons = struct.unpack(">II", read_exact(sock, 8))
                px = max(0, min(WIDTH - 1, x * WIDTH // max(1, screen_w)))
                py = max(0, min(HEIGHT - 1, y * HEIGHT // max(1, screen_h)))
                if xinput.display:
                    xinput.touch(action, x, y, screen_w, screen_h)
                else:
                    ui.emit(EV_ABS, ABS_X, px)
                    ui.emit(EV_ABS, ABS_Y, py)
                    if action in (0, 5):
                        ui.emit(EV_KEY, BTN_TOUCH, 1)
                    elif action in (1, 6):
                        ui.emit(EV_KEY, BTN_TOUCH, 0)
                    ui.sync()
            elif msg_type == 3:  # inject scroll event
                x, y, screen_w, screen_h = struct.unpack(">iiHH", read_exact(sock, 12))
                hscroll, vscroll, _buttons = struct.unpack(">hhI", read_exact(sock, 8))
                if xinput.display:
                    xinput.scroll(x, y, screen_w, screen_h, hscroll, vscroll)
            elif msg_type == 4:  # back or screen on
                action = read_exact(sock, 1)[0]
                if xinput.display:
                    xinput.key("Escape", action != 1)
                else:
                    ui.emit(EV_KEY, KEY_ESC, 0 if action == 1 else 1)
                    ui.sync()
            else:
                # Unsupported commands are length-variable; terminate rather
                # than desynchronizing the control stream.
                print("unsupported control message %d" % msg_type, file=sys.stderr, flush=True)
                return
    except (EOFError, OSError):
        return


def socket_name(args):
    scid = None
    for arg in args:
        if arg.startswith("scid="):
            scid = arg[5:]
    return "scrcpy" if not scid else "scrcpy_" + scid


def make_connections(name, tunnel_forward, audio, control):
    abstract = "\0" + name
    if tunnel_forward:
        listener = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        listener.bind(abstract)
        count = 1 + int(audio) + int(control)
        listener.listen(count)
        video = listener.accept()[0]
        write_all(video, b"\x00")
        audio_sock = listener.accept()[0] if audio else None
        ctl = listener.accept()[0] if control else None
        listener.close()
        return video, audio_sock, ctl
    video = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    video.connect(abstract)
    audio_sock = None
    if audio:
        audio_sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        audio_sock.connect(abstract)
    ctl = None
    if control:
        ctl = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        ctl.connect(abstract)
    return video, audio_sock, ctl


def split_h264(stream):
    units = []
    starts = []
    pos = 0
    while pos < len(stream):
        four = stream.find(b"\0\0\0\1", pos)
        three = stream.find(b"\0\0\1", pos)
        candidates = [x for x in (four, three) if x >= 0]
        if not candidates:
            break
        start = min(candidates)
        prefix = 4 if stream[start:start + 4] == b"\0\0\0\1" else 3
        starts.append((start, prefix))
        pos = start + prefix
    current = bytearray()
    for index, (start, prefix) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else len(stream)
        nal = stream[start + prefix:end]
        nal_type = nal[0] & 0x1f if nal else 0
        if nal_type == 9 and current:
            units.append(bytes(current))
            current.clear()
        current.extend(stream[start:end])
    if current:
        units.append(bytes(current))
    return units or [stream]


def capture_display():
    fd, filename = tempfile.mkstemp(prefix="scrcpy-compat-", suffix=".h264")
    os.close(fd)
    command = [
        "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "x11grab", "-draw_mouse", "0", "-video_size", "%dx%d" % (WIDTH, HEIGHT),
        "-framerate", "30", "-i", DISPLAY,
        "-t", "1", "-c:v", "libx264", "-preset", "ultrafast",
        "-tune", "zerolatency", "-x264-params", "aud=1",
        "-pix_fmt", "yuv420p", "-f", "h264", filename,
    ]
    try:
        subprocess.run(command, check=True, stdout=subprocess.DEVNULL,
                       stderr=subprocess.PIPE, timeout=8)
        return pathlib.Path(filename).read_bytes()
    except (OSError, subprocess.SubprocessError):
        return None
    finally:
        try:
            os.unlink(filename)
        except OSError:
            pass


def write_video_header(sock):
    write_all(sock, b"RoboPi2 Linux\0".ljust(64, b"\0"))
    write_all(sock, struct.pack(">I", 0x68323634))  # h264
    write_all(sock, struct.pack(">III", 0x80000000, WIDTH, HEIGHT))


def iter_pipe_units(pipe):
    pending = b""
    while True:
        chunk = os.read(pipe.fileno(), 65536)
        if not chunk:
            break
        pending += chunk
        while True:
            starts = []
            pos = 0
            while pos < len(pending) - 4:
                four = pending.find(b"\0\0\0\1\x09", pos)
                three = pending.find(b"\0\0\1\x09", pos)
                candidates = [x for x in (four, three) if x >= 0]
                if not candidates:
                    break
                start = min(candidates)
                starts.append(start)
                pos = start + 3
            if len(starts) < 2:
                break
            end = starts[1]
            yield pending[:end]
            pending = pending[end:]
    if pending:
        yield pending


def send_units(sock, units, pts=0):
    for unit in units:
        key = b"\0\0\1\x65" in unit or b"\0\0\0\1\x65" in unit
        flags = (1 << 61) if key else 0
        packet = struct.pack(">Q I", flags | pts, len(unit))
        write_all(sock, packet + unit)
        pts += 33333
    return pts


def stream_display(sock):
    command = [
        "/usr/bin/ffmpeg", "-hide_banner", "-loglevel", "error",
        "-f", "x11grab", "-draw_mouse", "0", "-video_size", "%dx%d" % (WIDTH, HEIGHT),
        "-framerate", "30", "-i", DISPLAY,
        "-c:v", "libx264", "-preset", "ultrafast", "-tune", "zerolatency",
        "-x264-params", "aud=1", "-pix_fmt", "yuv420p", "-flush_packets", "1",
        "-f", "h264", "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        write_video_header(sock)
        pts = 0
        for unit in iter_pipe_units(process.stdout):
            pts = send_units(sock, [unit], pts)
    finally:
        process.terminate()
        process.wait(timeout=2)


def send_video(sock):
    if DISPLAY:
        stream_display(sock)
        return
    first = True
    pts_base = 0
    while True:
        stream = capture_display() if DISPLAY else None
        if stream is None:
            stream = STREAM.read_bytes()
        if first:
            write_video_header(sock)
            first = False
        pts = pts_base
        for unit in split_h264(stream):
            key = b"\0\0\1\x65" in unit or b"\0\0\0\1\x65" in unit
            flags = (1 << 61) if key else 0
            write_all(sock, struct.pack(">Q I", flags | pts, len(unit)) + unit)
            pts += 33333
            time.sleep(1 / 30)
        pts_base = pts
        if not DISPLAY:
            return


def main(argv):
    args = argv[1:]
    tunnel = any(arg == "tunnel_forward=true" for arg in args)
    audio = not any(arg == "audio=false" for arg in args)
    control = not any(arg == "control=false" for arg in args)
    video, audio_sock, ctl = make_connections(socket_name(args), tunnel, audio, control)
    if audio_sock is not None:
        # The client accepts a disabled audio stream and continues with video.
        write_all(audio_sock, b"\0\0\0\0")
    ui = UInput()
    xinput = X11Input()
    if ctl is not None:
        threading.Thread(target=handle_control, args=(ctl, ui, xinput), daemon=True).start()
    try:
        send_video(video)
    finally:
        ui.close()
        xinput.close()
        if ctl is not None:
            ctl.close()
        if audio_sock is not None:
            audio_sock.close()
        video.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv))
    except BrokenPipeError:
        raise SystemExit(0)
