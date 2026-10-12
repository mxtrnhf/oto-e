"""Document model: an RGB image treated as a stream of audio samples."""
from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import numpy as np
from PIL import Image, ImageOps

from . import exportopts
from .effects import SR, Effect

MAX_STEPS = 1000  # history entries kept ...
MAX_HISTORY_BYTES = 1 << 30  # ... or until their stored deltas exceed this (oldest abandoned ones go first)
INTERLEAVED, PLANAR = 0, 1
MODE_NAMES = ["Interleaved RGB (classic)", "Planar (R, then G, then B)"]

# How the bytes are read as audio, like the encoding choice in Audacity's raw import. Every format keeps
# the picture's bytes untouched until an effect changes them; they only decide what a "sample" is.
U8, S8, S16LE, S16BE, ULAW = range(5)
FORMAT_NAMES = ["Unsigned 8-bit (classic)", "Signed 8-bit", "16-bit little-endian", "16-bit big-endian", "µ-law (8-bit)"]
BYTES_PER_SAMPLE = [1, 1, 2, 2, 1]


def _ulaw_table() -> np.ndarray:
    """G.711 µ-law decode: code -> linear value in [-1, 1). The two zero codes would collide when encoding back, so
    the negative zero sits one step below zero; untouched samples then always come back as the same byte."""
    u = ~np.arange(256) & 0xFF
    mag = (((u & 0x0F) << 3) + 0x84 << ((u >> 4) & 7)) - 0x84
    v = np.where(u & 0x80, -mag, mag).astype(np.float32)
    v[0x7F] = -1.0
    return v / 32768


_ULAW = _ulaw_table()
_ULAW_ORDER = np.argsort(_ULAW)  # codes sorted by value, for nearest-value encoding
_ULAW_MIDS = (_ULAW[_ULAW_ORDER][1:] + _ULAW[_ULAW_ORDER][:-1]) / 2


def decode(b: np.ndarray, fmt: int) -> np.ndarray:
    """Bytes -> float32 samples in [-1, 1]. 16-bit formats pair the bytes up (a leftover odd byte is ignored)."""
    if fmt == U8:
        return (b.astype(np.float32) - 127.5) / 127.5
    if fmt == S8:
        return b.view(np.int8).astype(np.float32) / 128
    if fmt == ULAW:
        return _ULAW[b]
    n = len(b) // 2 * 2
    return np.frombuffer(np.ascontiguousarray(b[:n]).tobytes(), "<i2" if fmt == S16LE else ">i2").astype(np.float32) / 32768


def encode(x: np.ndarray, fmt: int) -> np.ndarray:
    """Float samples -> bytes: the inverse of decode (clipped to the format's range)."""
    if fmt == U8:
        return np.clip(np.rint(x * 127.5 + 127.5), 0, 255).astype(np.uint8)
    if fmt == S8:
        return np.clip(np.rint(x * 128), -128, 127).astype(np.int8).view(np.uint8)
    if fmt == ULAW:
        return _ULAW_ORDER[np.searchsorted(_ULAW_MIDS, x)].astype(np.uint8)
    q = np.clip(np.rint(x * 32768), -32768, 32767).astype("<i2" if fmt == S16LE else ">i2")
    return np.frombuffer(q.tobytes(), np.uint8)


def sel_bytes(sel, fmt: int, size) -> tuple[int, int]:
    """A run of samples as the byte range it covers (the last sample also takes an odd leftover byte)."""
    bps = BYTES_PER_SAMPLE[fmt]; total = 3 * size[0] * size[1]; a, b = sel
    return a * bps, total if b * bps > total - bps else b * bps


class Rect(NamedTuple):
    """A rectangular selection in pixels, half-open: columns x0..x1-1, rows y0..y1-1."""
    x0: int
    y0: int
    x1: int
    y1: int

    @property
    def w(self) -> int: return self.x1 - self.x0

    @property
    def h(self) -> int: return self.y1 - self.y0


def norm_sel(sel):
    """A usable selection, or None. A selection is a Rect, or a (start, end) run of samples in reading order."""
    if isinstance(sel, Rect):
        return sel if sel.x1 > sel.x0 and sel.y1 > sel.y0 else None
    return sel if sel and sel[1] - sel[0] > 1 else None


def run_as_rect(sel, mode: int, size, fmt: int = U8) -> "Rect | None":
    """The rectangle a run of samples covers exactly, if it is one: whole rows (or the whole image) of full width."""
    W, H = size; a, b = sel_bytes(sel, fmt, size)
    if mode == INTERLEAVED:
        r = 3 * W
        return Rect(0, a // r, W, b // r) if b > a and a % r == 0 and b % r == 0 else None
    return Rect(0, 0, W, H) if a == 0 and b == 3 * W * H else None


def run_rows(sel, mode: int, size, fmt: int = U8) -> tuple[int, int]:
    """First row and one past the last row that a run of samples touches."""
    W, H = size; a, b = sel_bytes(sel, fmt, size)
    if mode == INTERLEAVED:
        p0, p1 = a // 3, -(-b // 3)
    else:
        P = W * H
        if b - a >= P or a // P != (b - 1) // P:
            return 0, H
        p0, p1 = a % P, (b - 1) % P + 1
    return p0 // W, min(-(-p1 // W), H)


def _rect_view(px: np.ndarray, mode: int, size, r: Rect) -> np.ndarray:
    """The rectangle as a writable array in stream order: rows of 3w samples (interleaved) or (plane, row, x) (planar)."""
    W, H = size
    if mode == INTERLEAVED:
        return px.reshape(H, W * 3)[r.y0:r.y1, r.x0 * 3:r.x1 * 3]
    return px.reshape(H, W, 3)[r.y0:r.y1, r.x0:r.x1].transpose(2, 0, 1)


def to_stream(pixels: np.ndarray, mode: int, fmt: int = U8) -> np.ndarray:
    """Flat uint8 RGB bytes -> float32 samples in [-1, 1]."""
    return decode(pixels.reshape(-1, 3).T.ravel() if mode == PLANAR else pixels, fmt)


def read_bytes(px: np.ndarray, mode: int, a: int, b: int) -> np.ndarray:
    """Bytes [a, b) of the stream (planar mode: all of R, then G, then B)."""
    if mode == INTERLEAVED:
        return px[a:b]
    rgb = px.reshape(-1, 3); P = len(rgb)
    return np.concatenate([rgb[max(a, k * P) - k * P:min(b, (k + 1) * P) - k * P, k] for k in range(3) if max(a, k * P) < min(b, (k + 1) * P)])


def write_bytes(px: np.ndarray, mode: int, a: int, q: np.ndarray):
    """Write bytes `q` into the stream starting at byte `a`."""
    if mode == INTERLEAVED:
        px[a:a + len(q)] = q; return
    rgb = px.reshape(-1, 3); P = len(rgb); b = a + len(q); pos = 0
    for k in range(3):
        lo, hi = max(a, k * P) - k * P, min(b, (k + 1) * P) - k * P
        if lo < hi:
            rgb[lo:hi, k] = q[pos:pos + hi - lo]; pos += hi - lo


def read_range(px: np.ndarray, mode: int, fmt: int, a: int, b: int) -> np.ndarray:
    """Samples [a, b) of the stream as float32, converting only that range."""
    bb = sel_bytes((a, b), fmt, (len(px) // 3, 1))  # `size` only supplies the total byte count
    return decode(read_bytes(px, mode, *bb), fmt)


def write_range(px: np.ndarray, mode: int, fmt: int, a: int, x: np.ndarray):
    """Write samples `x` into the stream starting at sample `a`."""
    write_bytes(px, mode, a * BYTES_PER_SAMPLE[fmt], encode(x, fmt))


class Step:
    """The bytes of [lo, lo+len(data)) that are *not* currently in the live image for one history edge.

    Moving across the edge in either direction is the same operation: swap this slice with the live
    image. So an edit costs only the region it changed, once, instead of a whole-image copy.
    """
    __slots__ = ("lo", "data")

    def __init__(self, lo: int, data: np.ndarray):
        self.lo, self.data = lo, data

    def swap(self, px: np.ndarray):
        region = px[self.lo:self.lo + len(self.data)]
        old = region.copy()
        region[:] = self.data
        self.data = old


class Node:
    """One state in the history tree. `step` converts between the parent's state and this one."""
    __slots__ = ("id", "parent", "children", "info", "step", "redo_child")

    def __init__(self, id: int, parent: "Node | None", info: dict, step: Step | None):
        self.id, self.parent, self.info, self.step = id, parent, info, step
        self.children: list[Node] = []
        self.redo_child: Node | None = None  # which branch Redo follows


class Document:
    def __init__(self):
        self.live = np.zeros(0, np.uint8)  # the live image, flat RGB
        self.original = self.live
        self._reset_history()
        self.size = (0, 0)  # w, h
        self.path: Path | None = None  # the .otoe project Save writes to
        self.source_name = ""
        self.mode = INTERLEAVED
        self.fmt = U8
        self.dirty = False

    def _reset_history(self):
        self.root = self.node = Node(0, None, {"name": "Original"}, None)
        self.nodes: dict[int, Node] = {0: self.root}
        self._next_id = 1

    @property
    def pixels(self) -> np.ndarray:
        return self.live

    @property
    def loaded(self) -> bool:
        return self.pixels.size > 0

    def open(self, path: str):
        with Image.open(path) as im:
            im = ImageOps.exif_transpose(im)
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGBA")
                bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
                im = Image.alpha_composite(bg, im)
            im = im.convert("RGB")
            self.size = im.size
            px = np.asarray(im, dtype=np.uint8).reshape(-1).copy()
        self.original = px.copy()
        self.live = px; self._reset_history()
        self.source_name = Path(path).name
        self.path = None  # first Save always asks, so the source is never overwritten by accident
        self.dirty = False

    def export(self, path: str, options: dict | None = None):
        """Write the current picture as an image file. `options`: the format's settings (see exportopts);
        omitted ones take their defaults. The document itself is untouched; see project.py for saving the session."""
        w, h = self.size
        im = Image.fromarray(self.pixels.reshape(h, w, 3), "RGB")
        im.save(path, **exportopts.pillow_kwargs(exportopts.kind(path), options))

    # ---- editing
    def stream(self, pixels: np.ndarray | None = None) -> np.ndarray:
        return to_stream(self.pixels if pixels is None else pixels, self.mode, self.fmt)

    @property
    def nsamples(self) -> int:
        """Length of the stream: the number of samples the current format makes of the picture's bytes."""
        return self.live.size // BYTES_PER_SAMPLE[self.fmt]

    def sel_from_bytes(self, a: int, b: int) -> tuple[int, int]:
        """A byte range as the run of samples that covers it."""
        bps = BYTES_PER_SAMPLE[self.fmt]
        return a // bps, min(-(-b // bps), self.nsamples)

    def compute(self, eff: Effect, params: dict, sel: tuple[int, int] | None,
                base: np.ndarray | None = None, mode: int | None = None, keep_from: int | None = None,
                keep_rows: int = 0, fmt: int | None = None) -> np.ndarray:
        """Return new pixel data with `eff` applied to `sel` (or everything). Pure.

        `base` (which this call then owns and modifies) and `mode` let a background thread work on a
        snapshot while the document stays free to change. `keep_from` runs the effect on all of `sel` but only
        keeps the result from that sample onwards: the part before it is a lead-in that lets echoes, reverb and
        filters build up their tails, as they would have in a full run."""
        mode = self.mode if mode is None else mode
        fmt = self.fmt if fmt is None else fmt
        out = self.live.copy() if base is None else base
        if eff.domain == "image":
            return self._compute_image(eff, params, norm_sel(sel), out, mode, fmt)
        if isinstance(sel, Rect):
            # the effect sees the rectangle as its own small picture. `keep_rows` leading rows are a lead-in:
            # they are processed (so tails build up) but their original pixels are kept.
            view = _rect_view(out, mode, self.size, sel)
            orig = view.copy()
            seg = decode(orig.ravel(), fmt)
            res = np.nan_to_num(np.asarray(eff.fn(seg, SR, **params), dtype=np.float32), nan=0.0, posinf=1.0, neginf=-1.0)
            res = np.pad(res, (0, max(len(seg) - len(res), 0)))[:len(seg)]
            q = orig.ravel().copy(); q[:len(res) * BYTES_PER_SAMPLE[fmt]] = encode(res, fmt)  # an odd leftover byte stays as it was
            q = q.reshape(view.shape)
            if keep_rows:
                q[..., :keep_rows, :] = orig[..., :keep_rows, :]
            view[...] = q
            return out
        a, b = sel if sel and sel[1] - sel[0] > 1 else (0, self.nsamples)
        seg = read_range(out, mode, fmt, a, b)
        res = np.asarray(eff.fn(seg, SR, **params), dtype=np.float32)
        res = np.nan_to_num(res, nan=0.0, posinf=1.0, neginf=-1.0)  # a misbehaving effect must never corrupt the image
        if len(res) < len(seg):
            res = np.pad(res, (0, len(seg) - len(res)))
        lo = 0 if keep_from is None else min(max(keep_from - a, 0), len(seg))
        if lo < len(seg):
            write_range(out, mode, fmt, a + lo, res[lo:len(seg)])
        return out

    def _compute_image(self, eff: Effect, params: dict, sel, out: np.ndarray, mode: int, fmt: int = U8) -> np.ndarray:
        """Apply a picture-domain effect to the whole image or a rectangle; `out` is modified and returned.
        A run selection (reading order) has no picture shape, so it is refused unless it covers whole rows."""
        if sel is not None and not isinstance(sel, Rect):
            sel = run_as_rect(sel, mode, self.size, fmt)
            if sel is None:
                raise ValueError("Image effects need a rectangle selection (or no selection). Switch to rectangle selection.")
        W, H = self.size
        r = sel or Rect(0, 0, W, H)
        view = out.reshape(H, W, 3)[r.y0:r.y1, r.x0:r.x1]
        res = np.asarray(eff.fn(view.copy(), **params))
        view[...] = np.clip(res, 0, 255).astype(np.uint8).reshape(view.shape)
        return out

    def commit(self, pixels: np.ndarray, info: dict):
        """Make `pixels` the live image as a new history node under the current one.

        Anything that was undone stays in the tree as a side branch; nothing is ever discarded
        except by the memory budget in _trim().
        """
        changed = np.flatnonzero(pixels != self.live)
        lo, hi = (int(changed[0]), int(changed[-1]) + 1) if changed.size else (0, 0)
        n = Node(self._next_id, self.node, info, Step(lo, self.live[lo:hi].copy()))  # keep only what gets overwritten
        self._next_id += 1
        self.node.children.append(n); self.node.redo_child = n
        self.nodes[n.id] = n
        self.live = pixels
        self.node = n
        self._trim()
        self.dirty = True

    def _path_ids(self) -> set[int]:
        out, n = set(), self.node
        while n:
            out.add(n.id); n = n.parent
        return out

    def _trim(self):
        """Over budget: drop the oldest branch tips that are not on the way to the current state."""
        total = sum(len(n.step.data) for n in self.nodes.values() if n.step)
        while len(self.nodes) > 2 and (len(self.nodes) > MAX_STEPS or total > MAX_HISTORY_BYTES):
            on_path = self._path_ids()
            tips = [n for n in self.nodes.values() if not n.children and n.id not in on_path]
            if tips:
                t = min(tips, key=lambda n: n.id)
                t.parent.children.remove(t)
                if t.parent.redo_child is t:
                    t.parent.redo_child = t.parent.children[-1] if t.parent.children else None
                total -= len(t.step.data); del self.nodes[t.id]
                continue
            # only a straight line is left: the oldest state becomes unreachable, so the next one is the new base
            c = self.root.children[0]
            total -= len(c.step.data)
            del self.nodes[self.root.id]
            c.parent = None; c.step = None; c.info = {"name": "(earlier steps trimmed)"}
            self.root = c

    def goto(self, node_id: int) -> bool:
        """Move the live image to any state in the tree (up to the common ancestor, then down)."""
        target = self.nodes.get(node_id)
        if target is None or target is self.node:
            return False
        ancestors = set()
        n = self.node
        while n:
            ancestors.add(n.id); n = n.parent
        down, n = [], target
        while n.id not in ancestors:
            down.append(n); n = n.parent
        while self.node is not n:  # climb: step back across each edge
            self.node.step.swap(self.live)
            self.node.parent.redo_child = self.node
            self.node = self.node.parent
        for d in reversed(down):  # descend
            d.step.swap(self.live)
            self.node = d
        self.dirty = True
        return True

    def undo(self) -> bool:
        return self.node.parent is not None and self.goto(self.node.parent.id)

    def redo(self) -> bool:
        n = self.node.redo_child or (self.node.children[-1] if self.node.children else None)
        return n is not None and self.goto(n.id)

    def entries(self) -> list[dict]:
        """All history states in creation order. rel: 0 = current, 1 = leads to current, 2 = other branch."""
        path = self._path_ids()
        return [{"id": n.id, "parent": n.parent.id if n.parent else None, "info": n.info,
                 "rel": 0 if n is self.node else 1 if n.id in path else 2}
                for n in sorted(self.nodes.values(), key=lambda n: n.id)]

    def history_bytes(self) -> int:
        return sum(len(n.step.data) for n in self.nodes.values() if n.step)

    def revert(self):
        self.commit(self.original.copy(), {"name": "Revert to original"})

    @property
    def can_undo(self): return self.node.parent is not None
    @property
    def can_redo(self): return bool(self.node.children)

    def selection_rects(self, sel) -> list:
        return [sel] if isinstance(sel, Rect) and self.loaded else []

    def selection_runs(self, sel):
        """The selection as sample runs in stream coordinates: (starts, ends) arrays. A Rect is one run per row
        (per plane in planar mode)."""
        if not sel or not self.loaded:
            return np.zeros(0, np.int64), np.zeros(0, np.int64)
        if not isinstance(sel, Rect):
            return np.array([sel[0]], np.int64), np.array([sel[1]], np.int64)
        W, H = self.size
        y = np.arange(sel.y0, sel.y1, dtype=np.int64)
        if self.mode == INTERLEAVED:
            a, b = (y * W + sel.x0) * 3, (y * W + sel.x1) * 3
        else:
            base = (np.arange(3, dtype=np.int64)[:, None] * (W * H) + y[None, :] * W).ravel()
            a, b = base + sel.x0, base + sel.x1
        bps = BYTES_PER_SAMPLE[self.fmt]  # bytes -> samples
        return a // bps, -(-b // bps)

    def selection_pixel_ranges(self, sel):
        """Map a sample range to [(pixel_start, pixel_end)) ranges for highlighting."""
        if not sel or not self.loaded or isinstance(sel, Rect):
            return []
        a, b = sel_bytes(sel, self.fmt, self.size)
        if self.mode == INTERLEAVED:
            return [(a // 3, -(-b // 3))]
        n = self.size[0] * self.size[1]
        out = []
        for k in range(3):
            lo, hi = max(a, k * n), min(b, (k + 1) * n)
            if lo < hi:
                out.append((lo - k * n, hi - k * n))
        return out
