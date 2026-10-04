"""Spider-Verse spider that replaces your mouse pointer, system-wide (Windows).

Run:   python spider_cursor.py
Quit:  Ctrl+Shift+Q  (or Ctrl+C in the console)

A click-through transparent window covers the screen and a procedurally
animated spider chases the real pointer. The normal arrow is hidden while
this runs and restored on exit. If the arrow is ever stuck invisible, run
`python spider_cursor.py --restore`.
"""
import math
import sys
import tkinter as tk

IS_WIN = sys.platform == "win32"
if IS_WIN:
    import atexit
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()  # make pointer coords match real pixels

KEY = "#010101"  # transparent colour key
FPS_MS = 16

# ---------------------------------------------------------------- Windows glue


def virtual_screen():
    if not IS_WIN:
        return 0, 0, 1280, 800
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),   # x, y
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))   # w, h


def restore_cursors():
    # SPI_SETCURSORS = 0x0057: reload the user's configured cursors
    user32.SystemParametersInfoW(0x0057, 0, None, 0)


def hide_system_cursor():
    # Blank 32x32 cursor (AND mask all 1s, XOR mask all 0s = fully transparent).
    and_mask = (ctypes.c_ubyte * 128)(*([0xFF] * 128))
    xor_mask = (ctypes.c_ubyte * 128)(*([0x00] * 128))
    # OCR_NORMAL=32512 arrow, OCR_IBEAM=32513, OCR_HAND=32649, OCR_WAIT=32514,
    # OCR_CROSS=32515, OCR_SIZEALL=32646, OCR_SIZENWSE=32642, OCR_SIZENESW=32643,
    # OCR_SIZEWE=32644, OCR_SIZENS=32645, OCR_NO=32648, OCR_APPSTARTING=32650
    for ocr in (32512, 32513, 32649, 32514, 32515, 32646, 32642, 32643,
                32644, 32645, 32648, 32650):
        blank = user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)
        user32.SetSystemCursor(blank, ocr)  # takes ownership of the handle
    atexit.register(restore_cursors)


def make_click_through(root):
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    GWL_EXSTYLE = -20
    # LAYERED | TRANSPARENT (click-through) | TOOLWINDOW (no taskbar) | NOACTIVATE
    style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                          style | 0x80000 | 0x20 | 0x80 | 0x08000000)


def pointer_pos(root):
    if IS_WIN:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    return root.winfo_pointerxy()


def left_down():
    return IS_WIN and bool(user32.GetAsyncKeyState(0x01) & 0x8000)


def quit_combo():
    # Ctrl + Shift + Q
    return IS_WIN and all(user32.GetAsyncKeyState(k) & 0x8000
                          for k in (0x11, 0x10, 0x51))


# ---------------------------------------------------------------------- spider


class Leg:
    def __init__(self, side, i, x, y):
        self.side, self.i = side, i
        self.reach = 34 + (8 if i in (1, 2) else 0)
        self.fx, self.fy = x, y
        self.from_ = (x, y)
        self.to = (x, y)
        self.t = 1.0


class Spider:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.vx = self.vy = 0.0
        self.angle = -math.pi / 2
        self.hop = 0.0
        self.was_down = False
        self.legs = [Leg(s, i, x, y) for s in (-1, 1) for i in range(4)]

    def rest(self, l):
        d = self.angle + l.side * (0.6 + l.i * 0.55)
        return self.x + math.cos(d) * l.reach, self.y + math.sin(d) * l.reach

    def update(self, dt, mx, my, down):
        if down and not self.was_down:
            self.hop = 1.0
        self.was_down = down
        k = 14
        self.vx += ((mx - self.x) * k - self.vx * 6) * dt
        self.vy += ((my - self.y) * k - self.vy * 6) * dt
        self.x += self.vx * dt
        self.y += self.vy * dt
        speed = math.hypot(self.vx, self.vy)
        if speed > 25:
            d = math.atan2(self.vy, self.vx) - self.angle
            d = math.atan2(math.sin(d), math.cos(d))
            self.angle += d * min(1, dt * 12)
        self.hop = max(0.0, self.hop - dt * 3)

        for l in self.legs:
            rx, ry = self.rest(l)
            if l.t >= 1:
                if math.hypot(l.fx - rx, l.fy - ry) > l.reach * 0.7:
                    lead = min(speed * 0.08, 30)
                    l.from_ = (l.fx, l.fy)
                    l.to = (rx + math.cos(self.angle) * lead,
                            ry + math.sin(self.angle) * lead)
                    l.t = 0.0
            else:
                l.t = min(1.0, l.t + dt * (6 + speed / 120))
                e = l.t * l.t * (3 - 2 * l.t)
                l.fx = l.from_[0] + (l.to[0] - l.from_[0]) * e
                l.fy = l.from_[1] + (l.to[1] - l.from_[1]) * e
        return speed


def draw_leg(cv, sp, l, ox, oy, color):
    hx, hy = sp.x + ox, sp.y + oy
    fx, fy = l.fx + ox, l.fy + oy
    d = math.hypot(fx - hx, fy - hy) or 1.0
    nx, ny = -(fy - hy) / d, (fx - hx) / d
    bow = 14 * l.side
    kx = (hx + fx) / 2 + nx * bow
    ky = (hy + fy) / 2 + ny * bow - 10
    cv.create_line(hx, hy, kx, ky, fx, fy, fill=color, width=3,
                   smooth=True, capstyle="round")


def draw_body(cv, sp, ox, oy, body, mark=False):
    s = 1 + sp.hop * 0.35
    c, sn = math.cos(sp.angle + math.pi / 2), math.sin(sp.angle + math.pi / 2)

    def pt(x, y):  # local -> screen (rotate, scale, translate)
        x, y = x * s, y * s
        return sp.x + ox + x * c - y * sn, sp.y + oy + x * sn + y * c

    def ellipse(cx, cy, rx, ry, fill):
        pts = []
        for k in range(20):
            a = k / 20 * math.tau
            pts += pt(cx + rx * math.cos(a), cy + ry * math.sin(a))
        cv.create_polygon(pts, fill=fill, outline="")

    ellipse(0, 9, 9, 12, body)    # abdomen
    ellipse(0, -7, 6.5, 7, body)  # head
    if mark:
        pts = []
        for x, y in ((-4, 3), (4, 3), (0, 9), (4, 15), (-4, 15), (0, 9)):
            pts += pt(x, y)
        cv.create_polygon(pts, fill="#e4202a", outline="")
        ellipse(-2.8, -9, 1.8, 2.4, "#ffffff")
        ellipse(2.8, -9, 1.8, 2.4, "#ffffff")


def render(cv, sp, speed, ox0, oy0):
    cv.delete("all")
    g = 1.5 + min(speed / 220, 4) + sp.hop * 4  # chromatic misprint widens with speed
    for color, dx, dy in (("#00e5ff", -g, 0), ("#ff2878", g, g * 0.5)):
        for l in sp.legs:
            draw_leg(cv, sp, l, dx - ox0, dy - oy0, color)
        draw_body(cv, sp, dx - ox0, dy - oy0, color)
    for l in sp.legs:
        draw_leg(cv, sp, l, -ox0, -oy0, "#0a0a0a")
    draw_body(cv, sp, -ox0, -oy0, "#0a0a0a", mark=True)


def main():
    if "--restore" in sys.argv:
        if IS_WIN:
            restore_cursors()
        return
    vx, vy, vw, vh = virtual_screen()
    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{vw}x{vh}+{vx}+{vy}")
    root.config(bg=KEY)
    if IS_WIN:
        root.attributes("-transparentcolor", KEY)
    cv = tk.Canvas(root, width=vw, height=vh, bg=KEY, highlightthickness=0)
    cv.pack()
    root.update_idletasks()
    if IS_WIN:
        make_click_through(root)
        hide_system_cursor()

    mx, my = pointer_pos(root)
    sp = Spider(mx, my)
    state = {"last": None}

    def tick():
        if quit_combo():
            root.destroy()
            return
        now = root.tk.call("clock", "milliseconds")
        dt = 0.016 if state["last"] is None else min((now - state["last"]) / 1000, 0.05)
        state["last"] = now
        mx, my = pointer_pos(root)
        speed = sp.update(dt, mx, my, left_down())
        render(cv, sp, speed, vx, vy)
        root.after(FPS_MS, tick)

    try:
        tick()
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        if IS_WIN:
            restore_cursors()


if __name__ == "__main__":
    main()
