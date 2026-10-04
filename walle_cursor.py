"""WALL-E that replaces your mouse pointer, system-wide (Windows).

Run:   python walle_cursor.py [--scale 1.0] [--keep-pointer]
Quit:  Ctrl+Shift+Q  (or Ctrl+C in the console)

A click-through transparent window covers the screen and WALL-E rolls after
the real pointer on his treads:
  * treads roll with his speed, he leans into starts and stops
  * his head and arm lag behind on springs, his eyes look where he's going
  * he turns around to face the way he's heading
  * stop moving and he looks around, tilts his head and blinks
  * click and he pops his eyes and waves hello
The normal arrow is hidden while this runs and restored on exit (use
--keep-pointer to leave it visible). If the arrow is ever stuck invisible,
run `python walle_cursor.py --restore`.
"""
import math
import random
import sys
import tkinter as tk

IS_WIN = sys.platform == "win32"
if IS_WIN:
    import atexit
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    user32.SetProcessDPIAware()

KEY = "#010101"  # transparent colour key
FPS_MS = 16

BODY, BODY_HI, BODY_LO = "#d9a22f", "#efc255", "#b97a2a"
RUST, BODY_EDGE = "#8d5420", "#6b4516"
DARK, DARK_EDGE, GREY, HOUSING = "#3a3a3f", "#1a1a1d", "#6e6e72", "#9a978a"
RING, LENS, IRIS, PUPIL = "#55555a", "#0e1118", "#2c4a6e", "#05070a"
DUST = "#c9b99a"

BODY_CENTER_Y = 42   # local height of the body centre above the ground contact

# ---------------------------------------------------------------- Windows glue


def virtual_screen():
    if not IS_WIN:
        return 0, 0, 1280, 800
    return (user32.GetSystemMetrics(76), user32.GetSystemMetrics(77),
            user32.GetSystemMetrics(78), user32.GetSystemMetrics(79))


def restore_cursors():
    user32.SystemParametersInfoW(0x0057, 0, None, 0)  # SPI_SETCURSORS


def hide_system_cursor():
    and_mask = (ctypes.c_ubyte * 128)(*([0xFF] * 128))
    xor_mask = (ctypes.c_ubyte * 128)(*([0x00] * 128))
    for ocr in (32512, 32513, 32649, 32514, 32515, 32646, 32642, 32643,
                32644, 32645, 32648, 32650):
        blank = user32.CreateCursor(None, 0, 0, 32, 32, and_mask, xor_mask)
        user32.SetSystemCursor(blank, ocr)
    atexit.register(restore_cursors)


def make_click_through(root):
    hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
    style = user32.GetWindowLongW(hwnd, -20)  # GWL_EXSTYLE
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


# ------------------------------------------------------------------ simulation


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


class WallE:
    def __init__(self, x, y, scale):
        self.scale = scale
        self.x, self.y = x, y            # body centre (chases the pointer)
        self.vx = self.vy = 0.0
        self.ax = self.ay = 0.0
        self.face_sign, self.face = 1, 1.0
        self.phase = 0.0                 # tread roll, in local units
        self.pitch = self.pv = 0.0       # body lean (rad, + = nose down)
        self.hx, self.hy, self.hvx, self.hvy = 4.0, -26.0, 0.0, 0.0   # head offset
        self.arm, self.armv = 0.45, 0.0  # arm angle from straight down
        self.wave = self.wave_t = 0.0
        self.excite = 0.0
        self.look = [0.0, 0.0]
        self.look_t = [0.0, 0.0]
        self.tilt = self.tilt_t = 0.0    # head roll
        self.sad = self.sad_t = 0.0
        self.idle_t = 0.0
        self.wander = 0.0
        self.blink_t, self.blink_next = 0.0, random.uniform(1.5, 4.0)
        self.puffs = []
        self.puff_acc = 0.0
        self.t = 0.0
        self.was_down = False

    # local (figure) space -> screen
    def T(self, px, py):
        c, s = math.cos(self.pitch), math.sin(self.pitch)
        rx, ry = px * c - py * s, px * s + py * c
        gy = self.y + BODY_CENTER_Y * self.scale
        return self.x + rx * self.face * self.scale, gy + ry * self.scale

    def update(self, dt, mx, my, down):
        self.t += dt
        click = down and not self.was_down
        self.was_down = down

        # critically damped chase of the pointer
        k, c = 10.0, 6.3
        self.ax = k * (mx - self.x) - c * self.vx
        self.ay = k * (my - self.y) - c * self.vy
        self.vx += self.ax * dt
        self.vy += self.ay * dt
        sp = math.hypot(self.vx, self.vy)
        if sp > 1600:
            self.vx, self.vy = self.vx * 1600 / sp, self.vy * 1600 / sp
        self.x += self.vx * dt
        self.y += self.vy * dt
        speed = math.hypot(self.vx, self.vy)
        moving = speed > 40

        # facing (turns around smoothly)
        if abs(self.vx) > 40:
            self.face_sign = 1 if self.vx > 0 else -1
        self.face += (self.face_sign - self.face) * min(1.0, dt * 14)
        vF, aF = self.vx * self.face_sign, self.ax * self.face_sign

        # treads roll
        roll = speed if vF >= 0 else -speed
        self.phase += roll / self.scale * dt

        # body lean: into motion, forward when braking, along slopes
        target = (clamp(vF * 0.00025, -0.14, 0.14) + clamp(-aF * 0.00002, -0.1, 0.1)
                  + clamp(self.vy / 1000, -0.35, 0.35))
        self.pv += ((target - self.pitch) * 140 - self.pv * 15) * dt
        self.pitch += self.pv * dt

        # head on a spring (feels inertia), stretches up when excited
        rest_x, rest_y = 4.0, -26.0 - 12 * self.excite
        self.hvx += (-(self.hx - rest_x) * 180 - self.hvx * 14 - 0.3 * aF) * dt
        self.hvy += (-(self.hy - rest_y) * 180 - self.hvy * 14 - 0.3 * self.ay) * dt
        self.hx = clamp(self.hx + self.hvx * dt, -8, 20)
        self.hy = clamp(self.hy + self.hvy * dt, -44, -8)

        # click: eyes pop and he waves
        if click:
            self.excite = 1.0
            self.wave_t = 0.9
        self.excite = max(0.0, self.excite - dt * 2.2)
        self.wave_t = max(0.0, self.wave_t - dt)
        self.wave += ((1.0 if self.wave_t > 0 else 0.0) - self.wave) * min(1.0, dt * 10)

        # arm trails behind when moving, sways at idle, waves on click
        base = 0.45 - clamp(vF * 0.0007, -0.9, 0.9) + 0.08 * math.sin(self.t * 1.6)
        goal = base * (1 - self.wave) + (2.4 + 0.35 * math.sin(self.t * 24)) * self.wave
        self.armv += ((goal - self.arm) * 110 - self.armv * 10) * dt
        self.arm += self.armv * dt

        # eyes: look where he's going, wander when idle, tilt head, blink
        if moving:
            self.idle_t = 0.0
            f = min(1.0, speed / 200)
            self.look_t = [vF / (speed + 1) * f, self.vy / (speed + 1) * f]
            self.tilt_t = self.sad_t = 0.0
            self.wander = 0.0
        else:
            self.idle_t += dt
            if self.idle_t > 1.0:
                self.wander -= dt
                if self.wander <= 0:
                    self.wander = random.uniform(1.5, 3.5)
                    self.look_t = [random.uniform(-1, 1), random.uniform(-0.8, 0.8)]
                    self.tilt_t = random.choice((-0.3, 0.0, 0.25, 0.45))
                    self.sad_t = 0.5 if self.tilt_t > 0.3 else 0.0
            else:
                self.look_t = [0.0, 0.0]
        e = min(1.0, dt * 10)
        self.look[0] += (self.look_t[0] - self.look[0]) * e
        self.look[1] += (self.look_t[1] - self.look[1]) * e
        self.tilt += (self.tilt_t - self.tilt) * min(1.0, dt * 6)
        self.sad += (self.sad_t - self.sad) * min(1.0, dt * 6)
        self.blink_next -= dt
        if self.blink_next <= 0:
            self.blink_t, self.blink_next = 0.18, random.uniform(2.0, 5.0)
        self.blink_t = max(0.0, self.blink_t - dt)

        # dust kicked up by the treads
        if speed > 260:
            self.puff_acc += dt
            while self.puff_acc > 0.045:
                self.puff_acc -= 0.045
                px, py = self.T(-26, -3)
                ang = math.atan2(self.vy, self.vx) + math.pi + random.uniform(-0.5, 0.5)
                self.puffs.append([px, py, math.cos(ang) * 60, math.sin(ang) * 60 - 25,
                                   0.0, random.uniform(3, 5.5) * self.scale])
        for p in self.puffs:
            p[0] += p[2] * dt
            p[1] += p[3] * dt
            p[2] *= 0.92
            p[3] *= 0.92
            p[4] += dt
        self.puffs = [p for p in self.puffs if p[4] < 0.45]
        return speed


# ------------------------------------------------------------------- rendering


def circle_pts(cx, cy, r, n=20):
    return [(cx + r * math.cos(k / n * math.tau), cy + r * math.sin(k / n * math.tau))
            for k in range(n)]


def rrect_pts(x0, y0, x1, y1, r, n=5):
    pts = []
    for cx, cy, a0 in ((x1 - r, y0 + r, -90), (x1 - r, y1 - r, 0),
                       (x0 + r, y1 - r, 90), (x0 + r, y0 + r, 180)):
        for k in range(n + 1):
            a = math.radians(a0 + 90 * k / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def clip_half_plane(pts, nx, ny, c):
    """Keep the part of a polygon where p.n >= c (Sutherland-Hodgman)."""
    out = []
    for i, p in enumerate(pts):
        q = pts[(i + 1) % len(pts)]
        dp, dq = p[0] * nx + p[1] * ny - c, q[0] * nx + q[1] * ny - c
        if dp >= 0:
            out.append(p)
        if (dp >= 0) != (dq >= 0):
            t = dp / (dp - dq)
            out.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return out


def render(cv, w, ox, oy):
    cv.delete("all")
    s = w.scale
    speed = math.hypot(w.vx, w.vy)
    bob = -abs(math.sin(w.phase * 0.25)) * 1.4 * min(1.0, speed / 300)

    def flat(pts, upper):
        out = []
        for x, y in pts:
            sx, sy = w.T(x, y + (bob if upper else 0))
            out += [sx - ox, sy - oy]
        return out

    def poly(pts, fill, edge="", width=1, upper=True):
        if len(pts) >= 3:
            cv.create_polygon(flat(pts, upper), fill=fill, outline=edge, width=width)

    def line(pts, color, width, upper=True):
        cv.create_line(*flat(pts, upper), fill=color, width=max(1, width * s),
                       capstyle="round", joinstyle="round")

    # dust puffs (screen space, behind everything)
    for px, py, _, _, age, r in w.puffs:
        rr = r * (1 + age * 1.5) * (1 - age / 0.45)
        if rr > 0.6:
            cv.create_oval(px - ox - rr, py - oy - rr, px - ox + rr, py - oy + rr,
                           fill=DUST, outline="")

    # ground shadow
    sh = [(28 * math.cos(a / 12 * math.tau), 2 + 4.5 * math.sin(a / 12 * math.tau))
          for a in range(12)]
    cv.create_polygon(flat(sh, False), fill="#202024", outline="", stipple="gray50")

    # ----- treads
    belt = []
    for a in range(-90, 91, 15):
        belt.append((18 + 10 * math.cos(math.radians(a)), -10 + 10 * math.sin(math.radians(a))))
    for a in range(90, 271, 15):
        belt.append((-18 + 10 * math.cos(math.radians(a)), -10 + 10 * math.sin(math.radians(a))))
    poly(belt, DARK, DARK_EDGE, 2, upper=False)
    for i in range(6):
        xt = -18 + (i * 6 + w.phase) % 36
        xb = -18 + (i * 6 - w.phase) % 36
        line([(xt, -19.2), (xt, -15.5)], DARK_EDGE, 1.4, upper=False)
        line([(xb, -4.5), (xb, -0.8)], DARK_EDGE, 1.4, upper=False)
    for cx in (-18, 0, 18):
        poly(circle_pts(cx, -10, 6.2), "#5b5b60", DARK_EDGE, 1.5, upper=False)
        for k in range(3):
            a = w.phase / 6.2 + k * math.tau / 3
            line([(cx, -10), (cx + 4.6 * math.cos(a), -10 + 4.6 * math.sin(a))],
                 DARK, 1.6, upper=False)
        poly(circle_pts(cx, -10, 1.8, 8), RUST, "", upper=False)

    # ----- body
    poly(rrect_pts(-23, -26, 23, -19, 2), DARK, DARK_EDGE, 1.5)
    poly(rrect_pts(-22, -62, 22, -24, 5), BODY, BODY_EDGE, 2)
    poly(rrect_pts(-20, -60, 20, -55, 2, 3), BODY_HI)
    poly(rrect_pts(-20, -36, 20, -26, 3, 3), BODY_LO)
    for bx, by, rx, ry in ((-14, -30, 5, 2.4), (10, -33, 4, 2), (-3, -28, 3, 1.5), (16, -52, 3, 1.5)):
        poly([(bx + rx * math.cos(a / 8 * math.tau), by + ry * math.sin(a / 8 * math.tau))
              for a in range(8)], RUST)
    poly(rrect_pts(-15, -53, 9, -37, 3), "", BODY_EDGE, 1.5)
    for vy_ in (-49, -45, -41):
        line([(-10, vy_), (4, vy_)], BODY_EDGE, 1)
    for bx, by in ((-19, -58), (19, -58)):
        poly(circle_pts(bx, by, 1.3, 6), BODY_EDGE)

    # ----- neck
    n0 = (10.0, -61.0)
    h = (n0[0] + w.hx, n0[1] + w.hy)
    line([n0, h], DARK_EDGE, 9)
    line([n0, h], GREY, 6.5)
    dx, dy = h[0] - n0[0], h[1] - n0[1]
    ln = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / ln, dx / ln
    for tt in (0.3, 0.55, 0.8):
        px, py = n0[0] + dx * tt, n0[1] + dy * tt
        line([(px - nx * 4, py - ny * 4), (px + nx * 4, py + ny * 4)], DARK_EDGE, 1)
    poly([(10 + 7 * math.cos(a / 12 * math.tau), -61 + 2.6 * math.sin(a / 12 * math.tau))
          for a in range(12)], DARK, DARK_EDGE, 1.5)

    # ----- arm
    sh_ = (13.0, -43.0)
    a1 = w.arm
    a2 = a1 + 0.5
    el = (sh_[0] + 13 * math.sin(a1), sh_[1] + 13 * math.cos(a1))
    hd = (el[0] + 13 * math.sin(a2), el[1] + 13 * math.cos(a2))
    line([sh_, el, hd], DARK_EDGE, 6.5)
    line([sh_, el, hd], GREY, 4.2)
    poly(circle_pts(el[0], el[1], 3, 8), DARK, DARK_EDGE, 1.2)
    for da in (-0.55, 0.55):
        a3 = a2 + da
        line([hd, (hd[0] + 6 * math.sin(a3), hd[1] + 6 * math.cos(a3))], DARK, 2.6)

    # ----- head (binocular eyes) rolled by `tilt`, bobbing with the body
    roll = w.tilt - w.pitch * 0.6 - w.look[1] * 0.12
    cr, sr = math.cos(roll), math.sin(roll)

    def hp(pts):
        return [(h[0] + x * cr - y * sr, h[1] + x * sr + y * cr) for x, y in pts]

    poly(hp(rrect_pts(-13, -5.5, 13, 5.5, 4)), HOUSING, DARK_EDGE, 1.5)
    pop = 1 + 0.25 * w.excite
    if w.blink_t > 0:
        blink = math.sin(math.pi * (1 - w.blink_t / 0.18))
    else:
        blink = 0.0
    for ex, r0, side in ((-9.2, 9.4, -1), (9.4, 10.2, 1)):
        r = r0 * pop
        e = (ex, 0.0)
        poly(hp(circle_pts(e[0], e[1], r + 2.2, 22)), RING, DARK_EDGE, 1.5)
        poly(hp(circle_pts(e[0], e[1], r, 22)), LENS)
        lx, ly = w.look
        poly(hp(circle_pts(e[0] + lx * r * 0.22, e[1] + ly * r * 0.22, r * 0.62, 18)), IRIS)
        poly(hp(circle_pts(e[0] + lx * r * 0.32, e[1] + ly * r * 0.32, r * 0.3, 12)), PUPIL)
        poly(hp(circle_pts(e[0] - r * 0.32, e[1] - r * 0.38, r * 0.2, 8)), "#ffffff")
        poly(hp(circle_pts(e[0] + r * 0.36, e[1] + r * 0.3, r * 0.09, 6)), "#9fd6ff")
        # eyelid: a chord cut across the eye, lowered by blink/sadness, angled by `sad`
        th = w.sad * 0.7 * side
        drop = clamp(blink + w.sad * 0.35, 0.0, 1.0)
        lid = clip_half_plane(circle_pts(e[0], e[1], r + 2.2, 28),
                              math.sin(th), -math.cos(th),
                              (r + 2.2) * (1 - 2 * drop) + e[0] * math.sin(th) - e[1] * math.cos(th))
        poly(hp(lid), HOUSING, DARK_EDGE if drop > 0.05 else "", 1.2)


def main():
    if "--restore" in sys.argv:
        if IS_WIN:
            restore_cursors()
        return
    scale = 0.85
    if "--scale" in sys.argv:
        scale = float(sys.argv[sys.argv.index("--scale") + 1])
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
        if "--keep-pointer" not in sys.argv:
            hide_system_cursor()

    mx, my = pointer_pos(root)
    w = WallE(mx, my, scale)
    state = {"last": None}

    def tick():
        if quit_combo():
            root.destroy()
            return
        now = root.tk.call("clock", "milliseconds")
        dt = 0.016 if state["last"] is None else min((now - state["last"]) / 1000, 0.05)
        state["last"] = now
        px, py = pointer_pos(root)
        w.update(dt, px, py, left_down())
        render(cv, w, vx, vy)
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
