"""Render the Oto-e trailer: real effects from the program on a procedurally drawn picture, real screenshots of the window,
and a synthesised ambient score. Everything comes from code; nothing is recorded or sampled.

    make_trailer.py OUT.mp4                 render the whole trailer (about 10 minutes)
    make_trailer.py --stills 3 20 40 ...    write PNGs of single moments to ./stills instead (to check the look quickly)
    --image FILE                            use your own picture instead of the drawn one (any size; it is cropped to 16:9)
"""
import math
import os
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(HERE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = str(Path(os.environ.get("CLAUDE_JOB_DIR", "/tmp")) / "tmp" / "trailer_cfg")  # never touch the real Oto-e settings

import audio  # noqa: E402
import timeline as T  # noqa: E402
from art import dusk  # noqa: E402

W, H, FPS = T.W, T.H, T.FPS
WORK = Path(os.environ.get("CLAUDE_JOB_DIR", "/tmp")) / "tmp" / "trailer_work"
MONO = "/usr/share/fonts/noto/NotoSansMono-Regular.ttf"
LIGHT = "/usr/share/fonts/noto/NotoSans-Light.ttf"
rng = np.random.default_rng(5)


def ease(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def ramp(t, a, b):
    return ease((t - a) / (b - a)) if b > a else float(t >= a)


def window(t, a, b, fi=0.8, fo=0.8):
    """1 between a and b, easing in over fi seconds and out over fo."""
    return ramp(t, a, a + fi) * (1 - ramp(t, b - fo, b))


# ------------------------------------------------------------------ picture states (real Oto-e effects)
def make_states(image_path=None):
    from oto_e import effects, steptext
    from oto_e.core import Document
    if image_path:
        im = Image.open(image_path).convert("RGB"); w, h = im.size
        ch = min(h, int(w * 9 / 16)); cw = int(ch * 16 / 9)
        im = im.crop(((w - cw) // 2, (h - ch) // 2, (w - cw) // 2 + cw, (h - ch) // 2 + ch)).resize((W, H), Image.LANCZOS)
        base = np.asarray(im)
    else:
        base = dusk(W, H)
    d = Document(); d.size = (W, H); d.original = d.live = base.reshape(-1).copy()
    states, labels = [base], []
    for name in T.EFFECTS:
        e = effects.by_name(name); p = {**{q.key: q.default for q in e.params}, **T.OVERRIDES.get(name, {})}
        print("effect", name, flush=True)
        states.append(d.compute(e, p, None).reshape(H, W, 3))
        s = steptext._settings({"name": name, "params": p})
        labels.append(", ".join(s.split(", ")[:3]))
    return d, base, states, labels


# ------------------------------------------------------------------ the program window (real screenshots)
def grab_ui(d, base):
    from PyQt6.QtWidgets import QApplication
    a = QApplication.instance() or QApplication([])
    from oto_e import app, effects, uiscale
    paths = [WORK / f"ui{i}.png" for i in (1, 2, 3)]
    if all(p.exists() for p in paths):
        return paths
    WORK.mkdir(parents=True, exist_ok=True)
    uiscale.apply(145)  # bigger interface text, so it reads at video size
    w = app.MainWindow(); w.resize(W, H); w.show()
    Image.fromarray(base).save(WORK / "base.png")
    w.doc.open(str(WORK / "base.png")); w._refresh(reset=True); w.image_view.fit()

    def settle():
        for _ in range(25):
            a.processEvents()
    def step(name):
        e = effects.by_name(name); p = {q.key: q.default for q in e.params}
        w.doc.commit(w.doc.compute(e, p, None), {"name": name, "params": p, "sel": None, "mode": 0, "fmt": 0, "random": False})
    for n in T.EFFECTS[:3]:
        step(n)
    w._refresh(); settle(); w.grab().save(str(paths[0]))
    # 2: the settings window of a step, open over the main window
    e = effects.by_name("Echo"); w.run_effect(e, initial={q.key: q.default for q in e.params}); settle()
    w.grab().save(str(WORK / "shot.png")); w._dlg.grab().save(str(WORK / "dlg.png"))
    shot, dlg = Image.open(WORK / "shot.png").convert("RGBA"), Image.open(WORK / "dlg.png").convert("RGBA")
    shot.alpha_composite(dlg, ((W - dlg.width) // 2, (H - dlg.height) // 2)); shot.convert("RGB").save(paths[1])
    w._dlg.reject(); settle()
    # 3: a second branch, in the full history view
    w.doc.goto(2); step("Block Displacement"); step("Spectral Blur")
    w._refresh(); settle(); w.grab().save(str(paths[2]))
    w.hide()
    return paths


# ------------------------------------------------------------------ text
_fonts = {}
def font(path, size):
    return _fonts.setdefault((path, size), ImageFont.truetype(path, size))


_layers = {}
def text_layer(text, size, path=MONO, color=(240, 240, 245), spacing=0, glow=True):
    """An RGBA image of `text` with a faint cyan and magenta fringe, cached."""
    key = (text, size, path, color, spacing)
    if key in _layers:
        return _layers[key]
    f = font(path, size)
    widths = [f.getlength(c) + spacing for c in text]
    tw, th = int(sum(widths)) + 40, int(size * 1.5) + 20
    out = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
    for off, col in (((-3, 0), (0, 230, 255, 110)), ((3, 0), (255, 60, 190, 110)), ((0, 0), color + (255,))):
        if off != (0, 0) and not glow:
            continue
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0)); dr = ImageDraw.Draw(layer); x = 20 + off[0]
        for c, wd in zip(text, widths):
            dr.text((x, 10 + off[1]), c, font=f, fill=col); x += wd
        out.alpha_composite(layer)
    arr = np.asarray(out)
    _layers[key] = (arr, tw, th)
    return _layers[key]


def put(frame, layer, x, y, alpha=1.0, anchor="l"):
    """Blend a cached text layer onto `frame` at (x, y); anchor 'c' centres it on x."""
    if alpha <= 0.003:
        return
    arr, tw, th = layer
    if anchor == "c":
        x -= tw // 2
    x0, y0 = max(x, 0), max(y, 0); x1, y1 = min(x + tw, W), min(y + th, H)
    if x1 <= x0 or y1 <= y0:
        return
    sub = arr[y0 - y:y1 - y, x0 - x:x1 - x].astype(np.float32)
    a = sub[..., 3:4] / 255.0 * alpha
    region = frame[y0:y1, x0:x1].astype(np.float32)
    frame[y0:y1, x0:x1] = (region * (1 - a) + sub[..., :3] * a).astype(np.uint8)


def shade(frame, y0, y1, alpha):
    frame[y0:y1] = (frame[y0:y1].astype(np.float32) * (1 - alpha)).astype(np.uint8)


# ------------------------------------------------------------------ glitch toolbox
def glitch_amount(t):
    a = 0.0
    for gt, gs in T.glitches:
        a = max(a, gs * math.exp(-((t - gt) / 0.16) ** 2))
    return a


def slice_glitch(img, amt, r):
    if amt < 0.04:
        return img
    out = img.copy()
    for _ in range(int(2 + amt * 9)):
        y0 = int(r.integers(0, H - 8)); hh = int(r.integers(4, 18 + int(amt * 70)))
        dx = int(r.normal(0, 18 + amt * 110))
        out[y0:y0 + hh] = np.roll(out[y0:y0 + hh], dx, axis=1)
    dx = int(3 + amt * 16)
    out[..., 0] = np.roll(out[..., 0], dx, axis=1); out[..., 2] = np.roll(out[..., 2], -dx, axis=1)
    return out


def reveal(prev, nxt, p, downwards, r):
    """Swap `prev` for `nxt` with a soft edge that moves down the picture in reading order, the way the program reads its bytes,
    with a thin playhead line on it. Nothing tears; upwards is the same thing played backwards."""
    if p <= 0:
        return prev
    if p >= 1:
        return nxt
    feather = 220
    ye = p * (H + feather) - feather / 2          # centre of the soft edge
    if not downwards:
        prev, nxt = prev[::-1], nxt[::-1]
    out = prev.copy()
    top, bot = int(max(ye - feather / 2, 0)), int(min(ye + feather / 2, H))
    out[:top] = nxt[:top]
    if bot > top:
        rows = np.arange(top, bot)
        a = np.clip((ye + feather / 2 - rows) / feather, 0, 1); a = (a * a * (3 - 2 * a))[:, None, None].astype(np.float32)
        out[top:bot] = (prev[top:bot] * (1 - a) + nxt[top:bot] * a).astype(np.uint8)
    y = int(ye)
    if 0 <= y < H - 2:
        out[y:y + 2] = np.minimum(out[y:y + 2].astype(np.int16) + 85, 255).astype(np.uint8)
    return out if downwards else out[::-1]


_scan = np.where(np.arange(H) % 3 == 0, 0.93, 1.0).astype(np.float32)[:, None, None]
_vy, _vx = np.meshgrid(np.linspace(-1, 1, H), np.linspace(-1, 1, W), indexing="ij")
_vign = (1 - 0.32 * np.clip(_vx ** 2 * .6 + _vy ** 2 * .9, 0, 1))[..., None].astype(np.float32)
_grain = rng.normal(0, 2.2, (H, W, 1)).astype(np.float32)


def finish(img, t, r):
    f = img.astype(np.float32) * _scan * _vign
    f += np.roll(_grain, int(r.integers(0, W)), axis=1)
    return np.clip(f, 0, 255).astype(np.uint8)


def drift(img, t, strength=1.0):
    """Slow zoom and pan, as if the picture were being looked at."""
    s = 1.06 + 0.02 * math.sin(t * 0.21) * strength
    cw, ch = W / s, H / s
    cx = W / 2 + 36 * math.sin(t * 0.13) * strength; cy = H / 2 + 14 * math.cos(t * 0.17) * strength
    cx = min(max(cx, cw / 2), W - cw / 2); cy = min(max(cy, ch / 2), H - ch / 2)
    box = (cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2)
    return np.asarray(Image.fromarray(img).resize((W, H), Image.BILINEAR, box=box))


# ------------------------------------------------------------------ the film
class Film:
    def __init__(self, image_path=None):
        self.doc, self.base, self.states, self.labels = make_states(image_path)
        self.ui = [np.asarray(Image.open(p).convert("RGB").resize((W, H), Image.LANCZOS)) for p in grab_ui(self.doc, self.base)]
        self.black = np.zeros((H, W, 3), np.uint8)
        s = np.asarray(self.doc.stream(self.base.reshape(-1)), np.float64)
        n = len(s) // W * W
        cols = s[:n].reshape(W, -1)
        self.wave_lo, self.wave_hi = cols.min(axis=1), cols.max(axis=1)
        m = max(abs(self.wave_lo).max(), abs(self.wave_hi).max(), 1e-9)
        self.wave_lo, self.wave_hi = self.wave_lo / m, self.wave_hi / m
        from oto_e import recipe
        self.recipe_text = recipe.to_text({"name": "Echo", "params": {q.key: q.default for q in __import__("oto_e").effects.by_name("Echo").params}})

    def picture_at(self, t, r):
        """The (unfinished) picture for the scenes that show the glitched image, and the label to draw."""
        if t < T.UNDO[0]:
            i = min(int((t - T.EFFECT_START) // T.EFFECT_LEN), len(T.EFFECTS) - 1) if t >= T.EFFECT_START else -1
            if i < 0:
                return self.states[0]
            p = (t - T.effect_times[i] - 0.1) / T.REVEAL_LEN
            return reveal(self.states[i], self.states[i + 1], ease(p), True, r)
        p = (t - T.UNDO[0] - 0.1) / T.REVEAL_LEN
        return reveal(self.states[-1], self.states[0], ease(p), False, r)

    def frame(self, t):
        r = np.random.default_rng(int(t * FPS) + 1000)
        if T.UI[0] <= t < T.RECIPE[0]:
            return self.ui_frame(t, r)
        if T.RECIPE[0] <= t < T.END[0]:
            return self.recipe_frame(t, r)
        if t < T.TITLE[1]:
            return self.title_frame(t, r)
        img = self.picture_at(t, r) if t < T.UI[0] else self.states[0]
        if t >= T.END[0]:
            img = np.asarray(Image.fromarray(self.states[0]).filter(ImageFilter.GaussianBlur(7)))
            img = (img * 0.32).astype(np.uint8)
        frame = drift(img, t, 1.0 if t < T.END[0] else 0.3)
        frame = slice_glitch(frame, glitch_amount(t), r)
        frame = finish(frame, t, r)
        self.overlay_text(frame, t)
        # fades: in from black at the start of the picture, out at the very end
        fade = ramp(t, T.BYTES[0], T.BYTES[0] + 2.5) * (1 - ramp(t, T.TOTAL - 1.8, T.TOTAL))
        if t < T.UI[0] and fade < 1:
            frame = (frame.astype(np.float32) * fade).astype(np.uint8)
        elif t >= T.END[0]:
            frame = (frame.astype(np.float32) * (1 - ramp(t, T.TOTAL - 1.8, T.TOTAL))).astype(np.uint8)
        if T.UI[0] - 0.8 <= t < T.UI[0]:  # handled by the UI scene's crossfade; nothing here
            pass
        return frame

    # ---- scenes
    def title_frame(self, t, r):
        frame = self.black.copy()
        # faint data streaks
        for _ in range(5):
            y = int(r.integers(0, H)); x0 = int(r.integers(0, W // 2)); frame[y:y + 1, x0:x0 + int(r.integers(80, 700))] = 26
        tl = text_layer("OTO-E", 190, MONO, (245, 245, 250), spacing=46)
        a = ramp(t, 1.0, 3.2) * (1 - ramp(t, 6.2, 7.0))
        slid = int(24 * (1 - ramp(t, 1.0, 3.6)))
        put(frame, tl, W // 2 + slid, H // 2 - 150, a, "c")
        sub = text_layer("glitch pictures with audio effects", 44, LIGHT, (190, 200, 215), spacing=3, glow=False)
        put(frame, sub, W // 2, H // 2 + 60, ramp(t, 3.8, 5.4) * (1 - ramp(t, 6.2, 7.0)), "c")
        frame = slice_glitch(frame, glitch_amount(t), r)
        return finish(frame, t, r)

    def overlay_text(self, frame, t):
        if T.BYTES[0] <= t < T.EFFECT_START:
            put(frame, text_layer("A picture is only bytes.", 62, LIGHT, (245, 240, 245), spacing=2), W // 2, H - 330, window(t, 8.6, 12.8), "c")
            put(frame, text_layer("Bytes can be sound.", 62, LIGHT, (245, 240, 245), spacing=2), W // 2, H - 440, window(t, 13.2, 17.0, fo=0.5), "c")
            self.draw_wave(frame, t)
        for i, ts in enumerate(T.effect_times):
            if ts <= t < ts + T.EFFECT_LEN:
                a = window(t, ts + 0.9, ts + T.EFFECT_LEN - 0.7, 0.9, 0.7)
                shade(frame, H - 300, H, 0.0)
                put(frame, text_layer(T.SHORT[i], 60, MONO, (248, 248, 252), spacing=2), 96, H - 250, a)
                put(frame, text_layer(self.labels[i][:70], 31, MONO, (150, 215, 230), spacing=1, glow=False), 100, H - 168, a * .9)
                put(frame, text_layer(f"{i + 1:02d} / {len(T.EFFECTS):02d}", 30, MONO, (190, 190, 205), spacing=3, glow=False), W - 270, 70, a * .8)
        if T.UNDO[0] <= t < T.UI[0]:
            put(frame, text_layer("Undo.", 64, MONO, (248, 248, 252), spacing=2), 96, H - 250, window(t, T.UNDO[0] + 1.0, T.UNDO[0] + 3.0))
            put(frame, text_layer("Nothing is ever lost.", 60, LIGHT, (245, 240, 245), spacing=2), W // 2, H - 330, window(t, T.UNDO[0] + 3.2, T.UI[0] + 0.0, 0.8, 0.6), "c")
        if t >= T.END[0]:
            tl = text_layer("OTO-E", 170, MONO, (245, 245, 250), spacing=42)
            put(frame, tl, W // 2, H // 2 - 190, ramp(t, T.END[0] + 0.6, T.END[0] + 2.4), "c")
            put(frame, text_layer("free and open source  ·  GPL-3.0", 38, LIGHT, (235, 235, 245), spacing=3, glow=False), W // 2, H // 2 + 30, ramp(t, T.END[0] + 2.4, T.END[0] + 3.8), "c")
            put(frame, text_layer("github.com/mxtrnhf/oto-e", 40, MONO, (170, 230, 245), spacing=2, glow=False), W // 2, H // 2 + 100, ramp(t, T.END[0] + 3.2, T.END[0] + 4.6), "c")

    def draw_wave(self, frame, t):
        a = ramp(t, 12.6, 13.6) * (1 - ramp(t, 16.4, 17.0))
        if a <= 0:
            return
        y0, y1 = H - 300, H - 130
        prog = ramp(t, 13.2, 16.6)
        shade(frame, y0 - 20, y1 + 20, 0.55 * a)
        mid = (y0 + y1) // 2; hh = (y1 - y0) // 2
        step = 3
        lit = int(prog * W)
        for x in range(0, W, step):
            lo, hi = self.wave_lo[x], self.wave_hi[x]
            ya, yb = mid - int(hi * hh), mid - int(lo * hh)
            col = np.array([120, 230, 255]) if x < lit else np.array([70, 90, 110])
            frame[ya:max(yb, ya + 1), x:x + 2] = (frame[ya:max(yb, ya + 1), x:x + 2] * (1 - a) + col * a).astype(np.uint8)
        if 0 < lit < W:
            frame[y0 - 10:y1 + 10, lit:lit + 2] = (255 * a + frame[y0 - 10:y1 + 10, lit:lit + 2] * (1 - a)).astype(np.uint8)

    def ui_frame(self, t, r):
        k = (t - T.UI[0]) / (T.UI[1] - T.UI[0]) * 3
        i = min(int(k), 2); local = k - i
        def view(j):
            q = min(max((t - T.UI[0] - j * 4.67) / 4.67, 0), 1)  # how far into this screenshot's slow push-in
            z = 1.0 + 0.03 * q
            cw, ch = W / z, H / z
            ox, oy = [(0.0, .02), (0.0, 0.0), (0.0, .03)][j]
            cx = min(max(W / 2 + ox * W * q, cw / 2), W - cw / 2); cy = min(max(H / 2 + oy * H * q, ch / 2), H - ch / 2)
            return np.asarray(Image.fromarray(self.ui[j]).resize((W, H), Image.BILINEAR, box=(cx - cw / 2, cy - ch / 2, cx + cw / 2, cy + ch / 2))).astype(np.float32)
        cur = view(i)
        if i < 2 and local > 0.82:
            m = ease((local - 0.82) / 0.18); cur = cur * (1 - m) + view(i + 1) * m
        a_in = ramp(t, T.UI[0], T.UI[0] + 1.0)
        frame = np.clip(cur, 0, 255).astype(np.uint8)
        frame = slice_glitch(frame, glitch_amount(t), r)
        frame = (frame.astype(np.float32) * a_in).astype(np.uint8)
        caps = ["Every step is kept.", "Tweak any step.", "Branch. Compare. Duplicate."]
        for j, c in enumerate(caps):
            ts = T.UI[0] + j * 4.67
            al = window(t, ts + 0.8, ts + 4.2, 0.7, 0.6)
            if al > 0:
                shade(frame, H - 170, H - 60, 0.0)
                layer = text_layer(c, 56, LIGHT, (248, 246, 250), spacing=2)
                tw = layer[1]
                band = frame[H - 180:H - 60].astype(np.float32)
                x0 = W // 2 - tw // 2 - 40
                frame[H - 180:H - 60, max(x0, 0):min(x0 + tw + 80, W)] = (band[:, max(x0, 0):min(x0 + tw + 80, W)] * (1 - 0.62 * al)).astype(np.uint8)
                put(frame, layer, W // 2, H - 168, al, "c")
        return frame

    def recipe_script(self):
        """Everything typed in the recipe scene: (text, x, y, colour, start time, characters per second, part). Part 0 is the recipe, 1 the file."""
        R = T.RECIPE[0]
        cmd, text, grey = (150, 215, 230), (240, 238, 245), (170, 175, 190)
        out = [("$ right-click a step  >  Copy as recipe", 150, 300, cmd, R + 1.4, 16, 0),
               (self.recipe_text, 150, 380, text, R + 4.4, 22, 0),
               ("effect", 150, 520, cmd, R + 8.0, 40, 0), ("which effect to run", 520, 520, grey, R + 8.3, 40, 0),
               ("params", 150, 590, cmd, R + 9.6, 40, 0), ("its settings, by name", 520, 590, grey, R + 9.9, 40, 0),
               ("", 150, 620, grey, R + 11, 40, 0),
               ("no selection and no picture in it: paste it anywhere", 150, 700, text, R + 11.2, 30, 0)]
        names = ["dusk.otoe", "├─ original.png", "├─ current.png", "├─ history.json", "└─ steps/", "    ├─ 1.bin", "    ├─ 2.bin", "    └─ 3.bin"]
        says = ["a zip file: any archive tool opens it", "the picture as you opened it", "the picture as it is now",
                "every step, its settings, how they connect", "", "the bytes step 1 overwrote", "the bytes step 2 overwrote", "the bytes step 3 overwrote"]
        for k, (nm, sy) in enumerate(zip(names, says)):
            st = R + 14.0 + k * 1.05
            out.append((nm, 150, 280 + k * 74, text if k else cmd, st, 30, 1))
            if sy:
                out.append((sy, 820, 280 + k * 74, grey, st + 0.35, 34, 1))
        return out

    def recipe_frame(self, t, r):
        R = T.RECIPE[0]
        frame = self.black.copy()
        frame[...] = (np.linspace(14, 6, H)[:, None, None] * np.array([1.0, 1.0, 1.3])).astype(np.uint8)
        a1 = ramp(t, R + 0.4, R + 1.6) * (1 - ramp(t, R + 12.4, R + 13.2))
        a2 = ramp(t, R + 13.4, R + 14.6) * (1 - ramp(t, T.RECIPE[1] - 0.8, T.RECIPE[1]))
        put(frame, text_layer("Share a recipe.", 66, LIGHT, (245, 240, 245), spacing=2), 150, 120, a1)
        put(frame, text_layer("Keep the whole session.", 66, LIGHT, (245, 240, 245), spacing=2), 150, 120, a2)
        cursor = None
        for text, x, y, col, start, cps, part in self.recipe_script():
            n = int(max(t - start, 0) * cps)
            if n <= 0 or not text:
                continue
            seg = text[:n]
            al = (1 - ramp(t, R + 12.4, R + 13.2)) if part == 0 else (1 - ramp(t, T.RECIPE[1] - 0.8, T.RECIPE[1]))
            put(frame, text_layer(seg, 42, MONO, col, spacing=1, glow=False), x, y, al)
            if n < len(text) + 8:
                cursor = (x + 20 + int(sum(font(MONO, 42).getlength(c) + 1 for c in seg)), y + 14)
        if cursor and int(t * 2.5) % 2 == 0:
            frame[cursor[1]:cursor[1] + 48, cursor[0]:cursor[0] + 18] = 215
        out = slice_glitch(frame, glitch_amount(t), r)
        return finish(out, t, r)

    def click_times(self):
        ts = [T.UI[0] + 4.67, T.UI[0] + 9.33]
        for text, x, y, col, start, cps, part in self.recipe_script():
            ts += [start + k / cps for k in range(0, len(text), 5)] if len(text) > 12 else [start]
        return ts


def write_wav(path, a):
    w = wave.open(str(path), "wb"); w.setnchannels(2); w.setsampwidth(2); w.setframerate(audio.SR)
    w.writeframes((a * 32767).astype("<i2").tobytes()); w.close()


def main():
    args = sys.argv[1:]
    image = None
    if "--image" in args:
        i = args.index("--image"); image = args[i + 1]; del args[i:i + 2]
    film = Film(image)
    if args and args[0] == "--stills":
        out = Path("stills"); out.mkdir(exist_ok=True)
        for s in args[1:]:
            Image.fromarray(film.frame(float(s))).save(out / f"t{float(s):05.1f}.png"); print("still", s, flush=True)
        return
    out = args[0]
    score = audio.score(T.TOTAL, T.glitches, film.click_times(), list(T.effect_times) + [T.UNDO[0]], 3.0, T.END[0], T.UI)
    WORK.mkdir(parents=True, exist_ok=True); wav = WORK / "score.wav"; write_wav(wav, score)
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                           "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                           "-movflags", "+faststart", "-shortest", out], stdin=subprocess.PIPE)
    n = int(T.TOTAL * FPS)
    for k in range(n):
        ff.stdin.write(film.frame(k / FPS).tobytes())
        if k % 90 == 0:
            print(f"frame {k}/{n}", flush=True)
    ff.stdin.close(); ff.wait()
    print("wrote", out)


main()
