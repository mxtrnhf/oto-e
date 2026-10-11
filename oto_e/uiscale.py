"""Text size for the whole program: one scale factor, applied through the application font.

Everything that follows the application font (buttons, lists, menus, dialogs, the Help window, tooltips) simply grows with it.
Sizes that are written in pixels go through `px()` so they grow with it too. The scale is a percentage of the system's own
default font, remembered between sessions.
"""
from __future__ import annotations

from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication, QToolTip

PRESETS = [(85, "Small (85 %)"), (100, "Default (100 %)"), (115, "Large (115 %)"), (130, "Larger (130 %)"),
           (150, "Huge (150 %)"), (175, "Largest (175 %)")]

scale = 1.0
_base: QFont | None = None  # the system's font, captured once before any scaling


def px(n: float) -> int:
    """A size in pixels, grown with the text size."""
    return max(1, int(round(n * scale)))


def apply(percent: int) -> None:
    """Make `percent` of the system font size the application font (and the tooltip font)."""
    global scale, _base
    app = QApplication.instance()
    if _base is None:
        _base = QFont(app.font())
    scale = max(percent, 50) / 100
    f = QFont(_base)
    if _base.pointSizeF() > 0:
        f.setPointSizeF(_base.pointSizeF() * scale)
    else:  # fonts specified in pixels
        f.setPixelSize(max(1, round(_base.pixelSize() * scale)))
    app.setFont(f)
    QToolTip.setFont(f)
