"""Miles Morales hanging upside down from the top of your screen (Windows).

Run:   python miles_hanging.py [--scale 1.3]
Quit:  Ctrl+Shift+Q  (or Ctrl+C in the console)

A click-through transparent strip along the top of the screen holds a web
thread with Miles dangling from it like a pendulum:
  * move the mouse sideways and he swings after it
  * move the mouse lower and he lets out more web
  * click and he scurries up the web, then drops back down
Nothing you click is blocked: the overlay ignores the mouse.
"""
import math
import sys
import tkinter as tk

IS_WIN = sys.platform == "win32"
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()

KEY = "#010101"  # transparent colour key
FPS_MS = 16

SUIT, RED, DARK_RED, WHITE, THREAD = "#0d0d12", "#e4202a", "#8f1119", "#f2f2f2", "#e8e8f0"
RIM = "#5a5a8a"  # light edge so the black suit reads on dark backgrounds
CYAN, MAGENTA = "#00e5ff", "#ff2878"

# ---------------------------------------------------------------- Windows glue


def virtual_screen():
    if not IS_WIN:
        return 0, 0, 1280, 800
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))


def make_click_through(root):
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
    # LAYERED | TRANSPARENT (click-through) | TOOLWINDOW | NOACTIVATE
    user32.SetWindowLongW(hwnd, -20, style | 0x80000 | 0x20 | 0x80 | 0x08000000)


def pointer_pos(root):
    if IS_WIN:
        pt = wintypes.POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return pt.x, pt.y
    return root.winfo_pointerxy()


def left_down():
    return IS_WIN and bool(user32.GetAsyncKeyState(0x01) & 0x8000)


def quit_combo():
    return IS_WIN and all(user32.GetAsyncKeyState(k) & 0x8000
                          for k in (0x11, 0x10, 0x51))  # Ctrl+Shift+Q


# --------------------------------------------------------------------- physics

G, DAMP = 2200.0, 0.9      # gravity (px/s^2) and pendulum damping
SPRING, SPRING_DAMP = 30.0, 8.0


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class Hanger:
    def __init__(self, ax):
        self.ax, self.avx = ax, 0.0     # web anchor on the top edge
        self.L = 150.0                  # web length
        self.phi, self.w = 0.35, 0.0    # swing angle (rad) and angular speed
        self.retract = 0.0              # >0 while scurrying up the web
        self.t = 0.0
        self.was_down = False

    def update(self, dt, mx, my, down):
        self.t += dt
        if down and not self.was_down:
            self.retract = 1.2
        self.was_down = down
        self.retract = max(0.0, self.retract - dt)
        n = 4
        h = dt / n
        for _ in range(n):
            a = clamp(SPRING * (mx - self.ax) - SPRING_DAMP * self.avx, -6000, 6000)
            self.avx += a * h
            self.ax += self.avx * h
            target = 30.0 if self.retract > 0 else clamp(90 + 0.25 * my, 90, 340)
            self.L += (target - self.L) * min(1.0, h * 6)
            alpha = -(G / self.L) * math.sin(self.phi) - DAMP * self.w \
                - (a / self.L) * math.cos(self.phi)
            self.w += alpha * h
            self.phi = clamp(self.phi + self.w * h, -1.2, 1.2)


# ------------------------------------------------------------------- rendering


def draw_miles(cv, hg, ox, oy, scale, ghost=None):
    """Draw the web and Miles. `ghost` flattens everything to one colour."""
    c, s = math.cos(hg.phi), math.sin(hg.phi)
    bx = hg.ax + hg.L * math.sin(hg.phi)
    by = hg.L * math.cos(hg.phi)

    def P(x, y):  # figure-local (hanging, y down) -> screen
        x, y = x * scale, y * scale
        return bx + ox + x * c + y * s, by + oy - x * s + y * c

    def col(color):
        return ghost or color

    def flat(pts):
        out = []
        for x, y in pts:
            out += P(x, y)
        return out

    def poly(pts, fill):
        rim = RIM if (fill == SUIT and not ghost) else ""
        cv.create_polygon(flat(pts), fill=col(fill), outline=rim, width=2 if rim else 1)

    def ellipse(cx, cy, rx, ry, fill, n=22):
        poly([(cx + rx * math.cos(k / n * math.tau), cy + ry * math.sin(k / n * math.tau))
              for k in range(n)], fill)

    def line(pts, color, width, smooth=False):
        if color == SUIT and not ghost:
            cv.create_line(*flat(pts), fill=RIM, width=max(1, (width + 3) * scale),
                           smooth=smooth, capstyle="round", joinstyle="round")
        cv.create_line(*flat(pts), fill=col(color), width=max(1, width * scale),
                       smooth=smooth, capstyle="round", joinstyle="round")

    # web thread
    cv.create_line(hg.ax + ox, -6 + oy, bx + ox + 0, by + oy, fill=col(THREAD), width=2)

    sway = clamp(-hg.w * 0.06, -0.7, 0.7) + 0.06 * math.sin(hg.t * 2.1)

    # legs + shoes (feet are at the top, by the web)
    for side in (-1, 1):
        knee = (side * (8 + 2 * math.sin(hg.t * 1.7 + side)), 36)
        line([(side * 5, 12), knee, (side * 8, 58)], SUIT, 10, smooth=True)
        line([(side * 11, 20), (side * 12, 36)], RED, 1.6)           # red leg stripe
        ellipse(side * 6, 6, 6, 9, WHITE)                           # sneaker
        line([(side * 12, -3), (side * 0.5, -3)], RED, 3)           # sole

    # arms dangle past the head
    for side in (-1, 1):
        sh = (side * 14, 97)
        a1 = side * 0.35 + sway
        el = (sh[0] + 22 * math.sin(a1), sh[1] + 22 * math.cos(a1))
        a2 = a1 + side * 0.25 + sway * 0.5
        hand = (el[0] + 22 * math.sin(a2), el[1] + 22 * math.cos(a2))
        line([sh, el, hand], SUIT, 9, smooth=True)
        wr = (el[0] + 15 * math.sin(a2), el[1] + 15 * math.cos(a2))
        line([wr, hand], RED, 2.2)                                   # glove band
        ellipse(hand[0], hand[1], 5, 5, SUIT)

    # torso
    poly([(-9, 56), (9, 56), (8, 74), (15, 98), (-15, 98), (-8, 74)], SUIT)
    line([(-9, 58), (-8, 74), (-14, 97)], RED, 1.6)
    line([(9, 58), (8, 74), (14, 97)], RED, 1.6)
    # chest spider
    ellipse(0, 86, 2.6, 5, RED)
    ellipse(0, 93, 1.8, 1.8, RED)
    for dy in (-3, 0, 3):
        line([(0, 86 + dy), (7, 83 + dy * 2), (10, 88 + dy * 2)], RED, 1.2)
        line([(0, 86 + dy), (-7, 83 + dy * 2), (-10, 88 + dy * 2)], RED, 1.2)

    # head + mask details (head is at the bottom: eyes sit toward the body)
    ellipse(0, 118, 12.5, 14.5, SUIT)
    line([(0, 105), (0, 132)], DARK_RED, 1)
    line([(-11, 124), (0, 127), (11, 124)], DARK_RED, 1, smooth=True)
    line([(-9, 112), (0, 109), (9, 112)], DARK_RED, 1, smooth=True)
    for side in (-1, 1):
        poly([(side * 2, 111), (side * 12, 115), (side * 13, 123), (side * 2, 119)], WHITE)


def render(cv, hg, ox, oy, scale):
    cv.delete("all")
    g = 1.5 + min(abs(hg.w) * 2.5, 5)  # chromatic misprint grows with swing speed
    for color, dx, dy in ((CYAN, -g, 0), (MAGENTA, g, g * 0.5)):
        draw_miles(cv, hg, dx - ox, dy - oy, scale, ghost=color)
    draw_miles(cv, hg, -ox, -oy, scale)


def main():
    scale = 1.2
    if "--scale" in sys.argv:
        scale = float(sys.argv[sys.argv.index("--scale") + 1])
    vx, vy, vw, vh = virtual_screen()
    band = int(min(vh, 640 * scale))

    root = tk.Tk()
    root.overrideredirect(True)
    root.attributes("-topmost", True)
    root.geometry(f"{vw}x{band}+{vx}+{vy}")
    root.config(bg=KEY)
    if IS_WIN:
        root.attributes("-transparentcolor", KEY)
    cv = tk.Canvas(root, width=vw, height=band, bg=KEY, highlightthickness=0)
    cv.pack()
    root.update_idletasks()
    if IS_WIN:
        make_click_through(root)

    mx, my = pointer_pos(root)
    hg = Hanger(mx - vx)
    state = {"last": None}

    def tick():
        if quit_combo():
            root.destroy()
            return
        now = root.tk.call("clock", "milliseconds")
        dt = 0.016 if state["last"] is None else min((now - state["last"]) / 1000, 0.05)
        state["last"] = now
        mx, my = pointer_pos(root)
        hg.update(dt, mx - vx, my - vy, left_down())
        render(cv, hg, vx, vy, scale)
        root.after(FPS_MS, tick)

    try:
        tick()
        root.mainloop()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
