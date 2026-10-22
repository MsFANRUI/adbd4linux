# SPDX-License-Identifier: GPL-3.0
# Copyright (C) 2026 wentywenty
import sys
import time

import common
import x11

SOURCES = {"touchscreen", "keyboard", "mouse", "joystick", "trackball",
           "stylus", "gamepad", "touchnavigation"}

KEYCODES = {
    3: "Home", 4: "Escape", 17: "*", 18: "#",
    19: "Up", 20: "Down", 21: "Left", 22: "Right", 23: "Return",
    24: "XF86AudioRaiseVolume", 25: "XF86AudioLowerVolume",
    26: "Pause", 27: "Pause", 28: "Delete",
    55: ",", 56: ".", 57: "Alt_L", 58: "Alt_R", 59: "Shift_L", 60: "Shift_R",
    61: "Tab", 62: "space", 66: "Return", 67: "BackSpace",
    68: "`", 69: "-", 70: "=", 71: "[", 72: "]", 73: "\\", 74: ";", 75: "'",
    76: "/", 77: "@", 81: "+", 82: "Menu", 83: "Menu", 84: "XF86Search",
    85: "XF86AudioPlay", 86: "XF86AudioStop", 87: "XF86AudioNext",
    88: "XF86AudioPrev", 89: "XF86AudioRewind", 90: "XF86AudioForward",
    91: "XF86AudioMute", 92: "Prior", 93: "Next",
    111: "Escape", 112: "Delete", 113: "Control_L", 114: "Control_R",
    115: "Caps_Lock", 117: "Super_L", 118: "Super_R",
    122: "Home", 123: "End", 124: "Insert", 125: "End", 143: "Num_Lock",
    154: "KP_Divide", 155: "KP_Multiply", 156: "KP_Subtract", 157: "KP_Add",
    158: "KP_Decimal", 160: "KP_Enter", 161: "KP_Equal",
    164: "XF86AudioMute", 187: "Tab", 223: "Pause", 224: "Pause",
}
for index, char in enumerate("abcdefghijklmnopqrstuvwxyz"):
    KEYCODES[29 + index] = char
for index, char in enumerate("0123456789"):
    KEYCODES[7 + index] = char
for index in range(12):
    KEYCODES[131 + index] = "F%d" % (index + 1)
for index in range(10):
    KEYCODES[144 + index] = "KP_%d" % index

ANDROID_NAMES = {name.upper(): code for code, name in KEYCODES.items()}
ANDROID_NAMES.update({
    "BACK": 4, "DPAD_UP": 19, "DPAD_DOWN": 20, "DPAD_LEFT": 21,
    "DPAD_RIGHT": 22, "DPAD_CENTER": 23, "VOLUME_UP": 24, "VOLUME_DOWN": 25,
    "POWER": 26, "CAMERA": 27, "CLEAR": 28, "STAR": 17, "POUND": 18,
    "COMMA": 55, "PERIOD": 56, "ALT_LEFT": 57, "ALT_RIGHT": 58,
    "SHIFT_LEFT": 59, "SHIFT_RIGHT": 60, "TAB": 61, "SPACE": 62,
    "ENTER": 66, "DEL": 67, "GRAVE": 68, "MINUS": 69, "EQUALS": 70,
    "LEFT_BRACKET": 71, "RIGHT_BRACKET": 72, "BACKSLASH": 73,
    "SEMICOLON": 74, "APOSTROPHE": 75, "SLASH": 76, "AT": 77, "PLUS": 81,
    "MENU": 82, "NOTIFICATION": 83, "SEARCH": 84, "MEDIA_PLAY_PAUSE": 85,
    "MEDIA_STOP": 86, "MEDIA_NEXT": 87, "MEDIA_PREVIOUS": 88,
    "MEDIA_REWIND": 89, "MEDIA_FAST_FORWARD": 90, "MUTE": 91,
    "PAGE_UP": 92, "PAGE_DOWN": 93, "ESCAPE": 111, "FORWARD_DEL": 112,
    "CTRL_LEFT": 113, "CTRL_RIGHT": 114, "CAPS_LOCK": 115,
    "META_LEFT": 117, "META_RIGHT": 118, "MOVE_HOME": 122, "MOVE_END": 123,
    "INSERT": 124, "FORWARD": 125, "NUM_LOCK": 143, "VOLUME_MUTE": 164,
    "APP_SWITCH": 187, "SLEEP": 223, "WAKEUP": 224,
})


def usage(stream=sys.stdout):
    stream.write(
        "usage: input [<source>] <command> [<arg>...]\n"
        "commands: text, keyevent, tap, swipe, draganddrop, motionevent, "
        "roll, keycombination, press\n")


def keysym_of(disp, arg):
    name = arg[8:] if arg.startswith("KEYCODE_") else arg
    if name.lstrip("-").isdigit():
        code = int(name)
        value = KEYCODES.get(code)
    else:
        code = ANDROID_NAMES.get(name.upper())
        if code is None:
            value = name
        else:
            value = KEYCODES.get(code)
    if value is None:
        return None
    if isinstance(value, int):
        return value
    if len(value) == 1:
        return ord(value)
    sym = disp.lib.XStringToKeysym(value.encode())
    return sym or None


def keycode_of(disp, arg):
    sym = keysym_of(disp, arg)
    if sym is None:
        return None
    entry = disp.keymap.get(sym)
    if entry:
        return entry[0]
    return disp.lib.XKeysymToKeycode(disp.display, sym) or None


def parse_int(value, name):
    try:
        return int(float(value))
    except ValueError:
        raise SystemExit("input: invalid %s: %s" % (name, value))


def main(argv):
    dry = "--dry-run" in argv
    args = [arg for arg in argv if arg != "--dry-run"]
    if not args or args[0] in ("-h", "--help"):
        usage()
        return 0 if args else 1
    if args[0] in SOURCES:
        args = args[1:]
    if not args:
        usage(sys.stderr)
        return 1

    command = args[0]
    rest = args[1:]
    disp = x11.X11(common.DISPLAY)
    try:
        if command == "text":
            value = " ".join(rest)
            if dry:
                print("TEXT %r" % value)
            else:
                disp.text(value)
        elif command in ("keyevent", "press"):
            for arg in rest:
                if arg == "--longpress":
                    continue
                sym = keysym_of(disp, arg)
                if sym is None:
                    sys.stderr.write("input: unknown key %s\n" % arg)
                    return 1
                if dry:
                    print("KEYEVENT %s keysym=0x%x" % (arg, sym))
                else:
                    disp.keysym(sym, True)
                    disp.keysym(sym, False)
        elif command == "tap":
            if len(rest) < 2:
                usage(sys.stderr)
                return 1
            x, y = parse_int(rest[0], "x"), parse_int(rest[1], "y")
            if dry:
                print("TAP %d %d" % (x, y))
            else:
                disp.motion(x, y)
                disp.button(1, True)
                disp.button(1, False)
        elif command in ("swipe", "draganddrop"):
            if len(rest) < 4:
                usage(sys.stderr)
                return 1
            x1, y1 = parse_int(rest[0], "x1"), parse_int(rest[1], "y1")
            x2, y2 = parse_int(rest[2], "x2"), parse_int(rest[3], "y2")
            duration = parse_int(rest[4], "duration") if len(rest) > 4 else 300
            if dry:
                print("%s %d %d %d %d %dms"
                      % (command.upper(), x1, y1, x2, y2, duration))
            else:
                steps = max(2, min(120, duration // 10))
                delay = max(0.0, duration / 1000.0 / steps)
                disp.motion(x1, y1)
                disp.button(1, True)
                for step in range(1, steps + 1):
                    x = x1 + (x2 - x1) * step // steps
                    y = y1 + (y2 - y1) * step // steps
                    disp.motion(x, y)
                    time.sleep(delay)
                disp.button(1, False)
        elif command == "motionevent":
            if len(rest) < 3:
                usage(sys.stderr)
                return 1
            action = rest[0].upper()
            x, y = parse_int(rest[1], "x"), parse_int(rest[2], "y")
            if dry:
                print("MOTIONEVENT %s %d %d" % (action, x, y))
            else:
                disp.motion(x, y)
                if action == "DOWN":
                    disp.button(1, True)
                elif action in ("UP", "CANCEL"):
                    disp.button(1, False)
        elif command == "roll":
            if len(rest) < 2:
                usage(sys.stderr)
                return 1
            dx, dy = parse_int(rest[0], "dx"), parse_int(rest[1], "dy")
            if dry:
                print("ROLL %d %d" % (dx, dy))
            else:
                clicks = max(1, min(20, abs(dy) // 120 + 1))
                if dy > 0:
                    button = 5
                elif dy < 0:
                    button = 4
                else:
                    button = None
                if button:
                    for _ in range(clicks):
                        disp.button(button, True)
                        disp.button(button, False)
                clicks = max(1, min(20, abs(dx) // 120 + 1))
                if dx > 0:
                    button = 7
                elif dx < 0:
                    button = 6
                else:
                    button = None
                if button:
                    for _ in range(clicks):
                        disp.button(button, True)
                        disp.button(button, False)
        elif command == "keycombination":
            if not rest:
                usage(sys.stderr)
                return 1
            codes = []
            for arg in rest:
                code = keycode_of(disp, arg)
                if code is None:
                    sys.stderr.write("input: unknown key %s\n" % arg)
                    return 1
                codes.append(code)
            if dry:
                print("KEYCOMBINATION " + " ".join("%d" % c for c in codes))
            else:
                for code in codes:
                    disp.keycode(code, True)
                for code in reversed(codes):
                    disp.keycode(code, False)
        else:
            usage(sys.stderr)
            return 1
    finally:
        disp.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1:]))
    except BrokenPipeError:
        raise SystemExit(0)
