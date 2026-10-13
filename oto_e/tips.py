"""Tooltips that read well: padded, wrapped to a comfortable width, with a bold title and quiet secondary lines.

Qt shows a plain-text tooltip as one unwrapped, unpadded strip, which makes long descriptions wide and cramped. `tip()`
builds the nicer layout for the tooltips that deserve structure (title, text, shortcut or range). `TooltipStyler` is an
application-wide filter that gives every other plain tooltip the same padding and wrapping, so nothing looks different
just because nobody formatted it, and tooltips added later look right without any extra work.
"""
from __future__ import annotations

import html
import re

from PyQt6.QtCore import QEvent, QObject, QRect, Qt
from PyQt6.QtGui import QFontMetrics
from PyQt6.QtWidgets import QAbstractItemView, QToolTip, QWidget

from . import theme, uiscale
from .helptext import _fmt_range

TITLE_SIZE = "110%"
TEXT_WIDTH = 340  # px a tooltip's text may take before it wraps
GREY = f"color:{theme.TEXT_DIM}"
KEYCAP = f"background-color:{theme.BG3}; color:{theme.TEXT}"  # a shortcut's keys, drawn like keys


def _box(inner: str, measure: str) -> str:
    """Pad the content, and fix its width only when it is long enough to need wrapping (short tips stay snug)."""
    fm = QFontMetrics(QToolTip.font())
    longest = max((fm.horizontalAdvance(line) for line in measure.splitlines()), default=0)
    limit = uiscale.px(TEXT_WIDTH)  # the text column grows with the text size
    width = f' width="{limit}"' if longest > limit else ""
    return f'<table cellspacing="0" cellpadding="9"{width}><tr><td>{inner}</td></tr></table>'


def _hint_html(hint: str) -> str:
    """'Shortcut: Ctrl+R' shows its keys as key caps; any other hint is just quiet text."""
    label, sep, keys = hint.partition(": ")
    if sep and label == "Shortcut":
        caps = " ".join(f'<span style="{KEYCAP}">&nbsp;{html.escape(k)}&nbsp;</span>' for k in re.findall(r"[^+]+|\+(?=$)", keys))
        return f"{label} &nbsp;{caps}"
    return html.escape(hint)


def tip(title: str | None, body: str = "", hint: str | None = None, detail: str | None = None) -> str:
    """A structured tooltip. `title` is bold, `body` is the explanation (a blank line starts a new paragraph),
    `detail` is a quiet line such as a value range, and `hint` is a quiet last line such as a shortcut."""
    parts = []
    if title:
        parts.append(f'<p style="margin:0 0 6px 0; font-size:{TITLE_SIZE}"><b>{html.escape(title)}</b></p>')
    for para in (p for p in body.split("\n\n") if p.strip()):
        parts.append(f'<p style="margin:0 0 6px 0">{html.escape(para.strip()).replace(chr(10), "<br>")}</p>')
    if detail:
        parts.append(f'<p style="margin:0 0 2px 0;{GREY}">{html.escape(detail)}</p>')
    if hint:
        parts.append(f'<p style="margin:4px 0 2px 0;{GREY}">{_hint_html(hint)}</p>')
    return _box("".join(parts), "\n".join(x for x in (title, body, detail, hint) if x))


def shortcut_tip(text: str) -> str:
    """'Zoom out (Ctrl+-)' -> a tip titled 'Zoom out' with the shortcut as its quiet line."""
    if text.endswith(")") and " (" in text:
        title, _, rest = text.rpartition(" (")
        return tip(title, hint=f"Shortcut: {rest[:-1]}")
    return tip(None, text)


def param_tip(p) -> str:
    """The tooltip of one effect or export setting: its name, what it does, and the range it accepts."""
    return tip(p.label, p.help, detail=_fmt_range(p))


class TooltipStyler(QObject):
    """Install on the application: every plain-text tooltip is shown with the shared padding and wrapping."""

    def eventFilter(self, obj, e):
        if e.type() != QEvent.Type.ToolTip or not isinstance(obj, QWidget):
            return False
        view = obj.parent()
        if isinstance(view, QAbstractItemView) and obj is view.viewport():  # a list or tree item
            idx = view.indexAt(e.pos())
            text, rect = (idx.data(Qt.ItemDataRole.ToolTipRole) if idx.isValid() else None), (view.visualRect(idx) if idx.isValid() else QRect())
        else:
            text, rect = obj.toolTip(), QRect()
        if not text:
            return False  # nothing to say: let Qt do whatever it normally does (e.g. show a truncated item in full)
        if not Qt.mightBeRichText(text):
            text = tip(None, text)
        QToolTip.showText(e.globalPos(), text, obj, rect)
        return True
