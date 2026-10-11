"""Picture-domain effects: they see the image as a 2-D picture instead of a stream of audio samples.

Every effect is `fn(img, **params) -> ndarray`, with `img` a private (h, w, 3) uint8 copy of the target and
the result the same shape. The target is the whole image or a rectangle selection (see Document.compute).
Randomness is always seeded, so a preview, the applied result and a history tweak agree.

Pixel sorting, channel shifts and block/row displacement are classic glitch-art techniques. The idea of
offering them is inspired by gfejer/databender (GPL-3.0); the code here is written from scratch.
"""
from __future__ import annotations

import io

import numpy as np
from PIL import Image

from .effects import Param, effect

CAT = "Image"
AXIS = ["Rows (horizontal)", "Columns (vertical)"]


def _along(img: np.ndarray, axis: int, fn) -> np.ndarray:
    """Run `fn` on the picture with its lines laid out as rows: axis 0 = rows as they are, 1 = columns."""
    if axis == 0:
        return fn(img)
    return np.ascontiguousarray(fn(np.ascontiguousarray(img.transpose(1, 0, 2))).transpose(1, 0, 2))


def _roll_lines(img: np.ndarray, shifts: np.ndarray) -> np.ndarray:
    """Roll row i of `img` right by shifts[i] pixels, wrapping around."""
    h, w = img.shape[:2]
    cols = (np.arange(w)[None, :] - shifts[:, None]) % w
    return img[np.arange(h)[:, None], cols]


# ------------------------------------------------------------- pixel sort

SORT_KEYS = ["Luminance", "Hue", "Saturation", "Red", "Green", "Blue"]


def _sort_key(img: np.ndarray, kind: int) -> np.ndarray:
    """The value pixels are sorted (and thresholded) by, as floats in 0..255."""
    if kind == 0:
        return img @ np.array([0.299, 0.587, 0.114], np.float32)
    if kind in (1, 2):
        return np.asarray(Image.fromarray(img).convert("HSV"))[..., kind - 1].astype(np.float32)
    return img[..., kind - 3].astype(np.float32)


@effect("Pixel Sort", CAT,
        [Param("axis", "Sort along", 0, 0, 1, 1, "", True, AXIS),
         Param("key", "Sort by", 0, 0, 5, 1, "", True, SORT_KEYS),
         Param("lo", "Only pixels from", 25, 0, 100, 1, " %", True), Param("hi", "... up to", 75, 0, 100, 1, " %", True),
         Param("order", "Order", 0, 0, 1, 1, "", True, ["Ascending", "Descending"])], domain="image")
def pixel_sort(img, axis, key, lo, hi, order):
    lo, hi = sorted((lo, hi))

    def run(a):
        k = _sort_key(a, int(key)); k_pct = k * (100 / 255)
        mask = (k_pct >= lo) & (k_pct <= hi)
        prev = np.zeros_like(mask); prev[:, 1:] = mask[:, :-1]
        idx = np.flatnonzero(mask.ravel())
        if not idx.size:
            return a
        run_id = np.cumsum((mask & ~prev).ravel())[idx]  # runs are contiguous in this order, so sorting inside each keeps them in place
        kk = k.ravel()[idx]
        out = a.copy(); flat = out.reshape(-1, 3)
        flat[idx] = a.reshape(-1, 3)[idx][np.lexsort((-kk if order else kk, run_id))]
        return out
    return _along(img, int(axis), run)


# ----------------------------------------------------------- channel work

SWAPS = ["R G B → B G R", "R G B → B R G", "R G B → G R B", "R G B → G B R", "R G B → R B G"]
_PERMS = [[2, 1, 0], [2, 0, 1], [1, 0, 2], [1, 2, 0], [0, 2, 1]]


@effect("Channel Swap", CAT, [Param("perm", "Reorder", 0, 0, 4, 1, "", True, SWAPS)], domain="image")
def channel_swap(img, perm):
    return np.ascontiguousarray(img[..., _PERMS[int(perm)]])


def _cshift(ch: str, group: str, default_x: int = 0):
    return [Param(f"{ch}x", "Shift right", default_x, -300, 300, 1, " px", True, group=group),
            Param(f"{ch}y", "Shift down", 0, -300, 300, 1, " px", True)]


@effect("Chromatic Aberration", CAT, _cshift("r", "Red", 8) + _cshift("g", "Green") + _cshift("b", "Blue", -8), domain="image")
def chromatic_aberration(img, rx, ry, gx, gy, bx, by):
    out = img.copy()
    for c, (dx, dy) in enumerate(((rx, ry), (gx, gy), (bx, by))):
        if dx or dy:
            out[..., c] = np.roll(img[..., c], (int(dy), int(dx)), axis=(0, 1))
    return out


# -------------------------------------------------------- displacement

@effect("Row Shift", CAT,
        [Param("axis", "Shift", 0, 0, 1, 1, "", True, AXIS),
         Param("prob", "Share of lines moved", 30, 0, 100, 1, " %"), Param("amount", "Max shift", 50, 1, 500, 1, " px", True),
         Param("seed", "Seed", 1, 0, 9999, 1, "", True)], domain="image")
def row_shift(img, axis, prob, amount, seed):
    def run(a):
        rng = np.random.default_rng(int(seed)); n = a.shape[0]
        move = rng.random(n) < prob / 100
        return _roll_lines(a, np.where(move, rng.integers(-int(amount), int(amount) + 1, n), 0))
    return _along(img, int(axis), run)


@effect("Warp", CAT,
        [Param("axis", "Bend", 0, 0, 1, 1, "", True, AXIS),
         Param("mode", "Shape", 0, 0, 1, 1, "", True, ["Sine wave", "Slant"]),
         Param("amount", "Amount", 30, -500, 500, 1, " px", True),
         Param("period", "Wavelength (sine)", 100, 4, 2000, 1, " px", True)], domain="image")
def warp(img, axis, mode, amount, period):
    def run(a):
        n = a.shape[0]; i = np.arange(n)
        shift = amount * np.sin(2 * np.pi * i / period) if mode == 0 else amount * (i / max(n - 1, 1) - 0.5)
        return _roll_lines(a, np.rint(shift).astype(int))
    return _along(img, int(axis), run)


@effect("Block Displacement", CAT,
        [Param("count", "Blocks", 40, 1, 500, 1, "", True), Param("lo", "Smallest block", 20, 1, 1000, 1, " px", True),
         Param("hi", "Largest block", 150, 1, 1000, 1, " px", True), Param("shift", "Max move", 100, 1, 1000, 1, " px", True),
         Param("seed", "Seed", 1, 0, 9999, 1, "", True)], domain="image")
def block_displacement(img, count, lo, hi, shift, seed):
    h, w = img.shape[:2]; rng = np.random.default_rng(int(seed)); out = img.copy()
    lo, hi = sorted((int(lo), int(hi))); s = int(shift)
    for _ in range(int(count)):
        bw, bh = (int(rng.integers(lo, hi + 1)) for _ in range(2))
        bw, bh = min(bw, w), min(bh, h)
        x, y = int(rng.integers(0, w - bw + 1)), int(rng.integers(0, h - bh + 1))
        dx, dy = (int(rng.integers(-s, s + 1)) for _ in range(2))
        nx, ny = min(max(x + dx, 0), w - bw), min(max(y + dy, 0), h - bh)
        out[ny:ny + bh, nx:nx + bw] = out[y:y + bh, x:x + bw].copy()
    return out


# ------------------------------------------------------ resolution / bytes

@effect("Pixelate", CAT,
        [Param("size", "Block size", 12, 2, 300, 1, " px", True),
         Param("mode", "Colour of a block", 0, 0, 1, 1, "", True, ["Average", "Top-left pixel"])], domain="image")
def pixelate(img, size, mode):
    b = int(size); h, w = img.shape[:2]
    p = np.pad(img, ((0, -h % b), (0, -w % b), (0, 0)), mode="edge")
    blocks = p.reshape(p.shape[0] // b, b, p.shape[1] // b, b, 3)
    small = blocks.mean(axis=(1, 3)).astype(np.uint8) if mode == 0 else blocks[:, 0, :, 0]
    return np.repeat(np.repeat(small, b, 0), b, 1)[:h, :w]


def _jpeg_pass(img: np.ndarray, quality: int, subsampling: int, flips: int = 0, rng=None) -> np.ndarray:
    """One save-and-reload through an in-memory JPEG, optionally damaging the compressed picture data first."""
    buf = io.BytesIO(); Image.fromarray(img).save(buf, "JPEG", quality=quality, subsampling=subsampling)
    data = bytearray(buf.getvalue())
    if flips:
        sos = bytes(data).find(b"\xff\xda")  # start of scan: everything after its header is entropy-coded picture data
        start = sos + 2 + int.from_bytes(data[sos + 2:sos + 4], "big") if sos >= 0 else len(data)
        # never touch an 0xFF or the byte after it, so no marker is created or destroyed and the file still decodes
        ok = [i for i in range(start, len(data) - 2) if data[i] != 0xFF and data[i - 1] != 0xFF]
        for i in (rng.choice(ok, min(flips, len(ok)), replace=False) if ok else []):
            data[i] = int(rng.integers(0, 255))
    try:
        return np.asarray(Image.open(io.BytesIO(bytes(data))).convert("RGB"))
    except OSError:  # corruption broke the stream; fall back to the clean pass
        return np.asarray(Image.open(io.BytesIO(buf.getvalue())).convert("RGB"))


@effect("JPEG Crunch", CAT,
        [Param("quality", "Quality", 8, 1, 100, 1, "", True), Param("flips", "Corrupt bytes", 0, 0, 300, 1, "", True),
         Param("seed", "Seed", 1, 0, 9999, 1, "", True)], domain="image")
def jpeg_crunch(img, quality, flips, seed):
    return _jpeg_pass(img, int(quality), 2, int(flips), np.random.default_rng(int(seed)))


@effect("JPEG Cruncher", CAT,
        [Param("gens", "Generations (re-saves)", 30, 1, 100, 1, "", True),
         Param("quality", "Quality of each save", 60, 1, 100, 1, "", True),
         Param("chroma", "Colour detail", 2, 0, 2, 1, "", True, ["Full (4:4:4)", "Half (4:2:2)", "Quarter (4:2:0)"]),
         Param("drift", "Grid drift per save", 2, 0, 16, 1, " px", True),
         Param("resize", "Resize between saves", 10, 0, 60, 1, " %", True),
         Param("vary", "Resize varies", 100, 0, 100, 1, " %", True),
         Param("stretch", "Uneven stretch", 50, 0, 100, 1, " %", True),
         Param("resample", "Resampling", 0, 0, 2, 1, "", True, ["Smooth (bilinear)", "Sharp (bicubic)", "Blocky (nearest)"]),
         Param("flips", "Corrupt bytes (last save)", 0, 0, 300, 1, "", True),
         Param("seed", "Seed", 1, 0, 9999, 1, "", True)], domain="image")
def jpeg_cruncher(img, gens, quality, chroma, drift, resize, vary, stretch, resample, flips, seed):
    h, w = img.shape[:2]; rng = np.random.default_rng(int(seed)); d = int(drift)
    cur, ty, tx = img, 0, 0
    rs = (Image.BILINEAR, Image.BICUBIC, Image.NEAREST)[int(resample)]; k = stretch / 100; v = vary / 100
    amount = lambda: resize * (1 - v + v * rng.random()) if v else resize  # exactly `resize` when v = 0, anywhere from 0 to `resize` when v = 1
    for g in range(int(gens)):
        if d:  # nudge the picture so each save's 8x8 blocks land somewhere new, as re-uploads and crops do
            dy, dx = (int(v) for v in rng.integers(-d, d + 1, 2))
            cur = np.roll(cur, (dy, dx), (0, 1)); ty += dy; tx += dx
        size = (w, h)
        if resize:  # a re-upload at another size: save it smaller (by a fixed or random amount, differently per axis if stretched), then blow it back up
            a = amount()
            ax, ay = ((1 - k) * a + k * amount() for _ in range(2))
            size = (max(1, round(w * (1 - ax / 100))), max(1, round(h * (1 - ay / 100))))
        if size != (w, h):
            cur = np.asarray(Image.fromarray(cur).resize(size, rs))
        cur = _jpeg_pass(np.ascontiguousarray(cur), int(quality), int(chroma), int(flips) if g == gens - 1 else 0, rng)
        if size != (w, h):
            cur = np.asarray(Image.fromarray(cur).resize((w, h), rs))
    return np.ascontiguousarray(np.roll(cur, (-ty, -tx), (0, 1))) if ty or tx else cur
