"""The edit history as plain text, for pasting into a chat, an issue or a caption.

This is deliberately *not* a file format: nothing reads it back in, so its wording can change freely. It lists the steps that lead
to the picture you are looking at (not other branches), each with its exact settings.
"""
from __future__ import annotations

import textwrap

from . import effects
from .core import FORMAT_NAMES, MODE_NAMES, Document
from .effects import SR
from .history import _fmt_value

WIDTH = 100  # lines are wrapped here so the text reads well when pasted


def _place(info: dict) -> str:
    sel = info.get("sel")
    if not sel:
        return "the whole image"
    if len(sel) == 4:
        x0, y0, x1, y1 = sel
        return f"a rectangle (x {x0}–{x1}, y {y0}–{y1}, {x1 - x0}×{y1 - y0} px)"
    a, b = sel
    return f"samples {a:,}–{b:,} ({a / SR:.2f}–{b / SR:.2f} s)"


def _settings(info: dict) -> str:
    try:
        spec = {p.key: p for p in effects.by_name(info["name"]).params}
    except (KeyError, StopIteration):
        spec = {}
    return ", ".join(f"{spec[k].label}: {_fmt_value(spec[k], v)}" if k in spec else f"{k}: {v}"
                     for k, v in (info.get("params") or {}).items())


def _reading(info: dict) -> tuple[int, int]:
    return info.get("mode", 0), info.get("fmt", 0)


def _wrap(text: str, indent: str) -> str:
    return textwrap.fill(text, width=WIDTH, initial_indent=indent, subsequent_indent=indent, break_long_words=False)


def history_text(doc: Document) -> tuple[str, int] | None:
    """(text, number of steps) for the chain of steps behind the current picture, or None if there are no edits yet."""
    chain, n = [], doc.node
    while n is not None:
        chain.append(n); n = n.parent
    chain.reverse()
    steps = [n for n in chain if n.parent is not None]
    if not steps:
        return None
    w, h = doc.size
    lines = [f"Edit history of {doc.source_name or 'an image'} ({w}×{h} px)"]
    if chain[0].info.get("name") == "(earlier steps trimmed)":
        lines.append("(Earlier steps were trimmed to save memory.)")
    lines.append("")
    reading = (0, 0)  # the layout and sample format in force; every file starts as interleaved, unsigned 8-bit
    for i, step in enumerate(steps, 1):
        info = step.info; name = info.get("name", "?")
        if name == "Revert to original":
            lines.append(f"{i}. Back to the original picture"); continue
        lines.append(_wrap(f"{i}. {name} on {_place(info)}" + (" (randomized)" if info.get("random") else ""), "").rstrip())
        if _reading(info) != reading and "mode" in info:
            reading = _reading(info)
            lines.append(_wrap(f"Reading the bytes as: {MODE_NAMES[reading[0]]}, {FORMAT_NAMES[reading[1]]}", "   "))
        settings = _settings(info)
        if settings:
            lines.append(_wrap(settings, "   "))
    lines += ["", "Made with Oto-e: https://github.com/mxtrnhf/oto-e"]
    return "\n".join(lines), len(steps)
