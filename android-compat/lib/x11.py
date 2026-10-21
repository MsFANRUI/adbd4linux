import ctypes


class X11:
    def __init__(self, display):
        self.display = None
        try:
            self.lib = ctypes.CDLL("libX11.so.6")
            self.xtst = ctypes.CDLL("libXtst.so.6")
            self.lib.XOpenDisplay.restype = ctypes.c_void_p
            self.lib.XOpenDisplay.argtypes = [ctypes.c_char_p]
            self.lib.XDefaultScreen.argtypes = [ctypes.c_void_p]
            self.lib.XDefaultScreen.restype = ctypes.c_int
            self.lib.XStringToKeysym.argtypes = [ctypes.c_char_p]
            self.lib.XStringToKeysym.restype = ctypes.c_ulong
            self.lib.XKeysymToKeycode.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            self.lib.XKeysymToKeycode.restype = ctypes.c_ubyte
            self.lib.XDisplayKeycodes.argtypes = [ctypes.c_void_p,
                                                  ctypes.POINTER(ctypes.c_int),
                                                  ctypes.POINTER(ctypes.c_int)]
            self.lib.XGetKeyboardMapping.argtypes = [ctypes.c_void_p, ctypes.c_ubyte,
                                                     ctypes.c_int,
                                                     ctypes.POINTER(ctypes.c_int)]
            self.lib.XGetKeyboardMapping.restype = ctypes.POINTER(ctypes.c_ulong)
            self.lib.XFree.argtypes = [ctypes.c_void_p]
            self.lib.XFree.restype = ctypes.c_int
            self.lib.XFlush.argtypes = [ctypes.c_void_p]
            self.lib.XCloseDisplay.argtypes = [ctypes.c_void_p]
            self.xtst.XTestFakeKeyEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                    ctypes.c_int, ctypes.c_ulong]
            self.xtst.XTestFakeButtonEvent.argtypes = [ctypes.c_void_p, ctypes.c_uint,
                                                       ctypes.c_int, ctypes.c_ulong]
            self.xtst.XTestFakeMotionEvent.argtypes = [ctypes.c_void_p, ctypes.c_int,
                                                       ctypes.c_int, ctypes.c_int,
                                                       ctypes.c_ulong]
            self.display = self.lib.XOpenDisplay(display.encode())
            if not self.display:
                raise OSError("cannot open display %s" % display)
            self.screen = self.lib.XDefaultScreen(self.display)
            self.shift = self.lib.XKeysymToKeycode(self.display, 0xFFE1)
            self.keymap = {}
            low = ctypes.c_int()
            high = ctypes.c_int()
            self.lib.XDisplayKeycodes(self.display, ctypes.byref(low), ctypes.byref(high))
            count = high.value - low.value + 1
            per = ctypes.c_int()
            syms = self.lib.XGetKeyboardMapping(self.display, low.value, count,
                                                ctypes.byref(per))
            if syms:
                for index in range(count):
                    keycode = low.value + index
                    for level in range(min(per.value, 2)):
                        keysym = syms[index * per.value + level]
                        if keysym and keysym not in self.keymap:
                            self.keymap[keysym] = (keycode, level == 1)
                self.lib.XFree(syms)
        except (AttributeError, OSError):
            self.display = None
            raise

    def keycode(self, code, down, shift=False):
        if shift and down and self.shift:
            self.xtst.XTestFakeKeyEvent(self.display, self.shift, 1, 0)
        self.xtst.XTestFakeKeyEvent(self.display, code, int(down), 0)
        if shift and down and self.shift:
            self.xtst.XTestFakeKeyEvent(self.display, self.shift, 0, 0)
        self.lib.XFlush(self.display)

    def keysym(self, keysym, down):
        entry = self.keymap.get(keysym)
        if entry:
            self.keycode(entry[0], down, entry[1])
        else:
            code = self.lib.XKeysymToKeycode(self.display, keysym)
            if code:
                self.keycode(code, down, False)

    def text(self, content):
        special = {"\n": 0xFF0D, "\r": 0xFF0D, "\t": 0xFF09, "\b": 0xFF08}
        for char in content:
            keysym = special.get(char, ord(char))
            if keysym > 0xFF and keysym not in special.values():
                continue
            entry = self.keymap.get(keysym)
            if not entry:
                continue
            self.keycode(entry[0], True, entry[1])
            self.keycode(entry[0], False, False)
        self.lib.XFlush(self.display)

    def motion(self, x, y):
        self.xtst.XTestFakeMotionEvent(self.display, self.screen, int(x), int(y), 0)
        self.lib.XFlush(self.display)

    def button(self, button, down):
        self.xtst.XTestFakeButtonEvent(self.display, button, int(down), 0)
        self.lib.XFlush(self.display)

    def close(self):
        if self.display:
            self.lib.XCloseDisplay(self.display)
            self.display = None
