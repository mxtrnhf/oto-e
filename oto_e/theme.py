"""Look of the whole program: Fusion style, a dark palette with one accent colour, and a stylesheet for the details.

Qt draws with the platform's native style unless told otherwise, which is why an unthemed Qt program looks "default". Here the
palette gives every widget consistent colours, and the stylesheet adds what a palette cannot: rounded corners, flat buttons,
slim sliders, quiet scrollbars and generous spacing. Sizes are written in `em` so they follow the text size (View > Text size).
"""
from __future__ import annotations

from PyQt6.QtGui import QColor, QPalette
from PyQt6.QtWidgets import QApplication

# Surfaces, darkest to lightest. The image / waveform canvas (views.BG) sits at the bottom of this stack.
BG0, BG1, BG2, BG3, BORDER = "#16171a", "#1e1f22", "#26282c", "#2f3237", "#3a3d43"
TEXT, TEXT_DIM, ACCENT, ACCENT_HI = "#e6e8eb", "#8b9098", "#4f9dff", "#7ab6ff"


def _palette() -> QPalette:
    p = QPalette()
    R, G = QPalette.ColorRole, QPalette.ColorGroup
    for role, col in [(R.Window, BG1), (R.WindowText, TEXT), (R.Base, BG0), (R.AlternateBase, BG2), (R.Text, TEXT),
                      (R.Button, BG3), (R.ButtonText, TEXT), (R.ToolTipBase, BG3), (R.ToolTipText, TEXT),
                      (R.Highlight, ACCENT), (R.HighlightedText, "#ffffff"), (R.Link, ACCENT_HI), (R.LinkVisited, ACCENT_HI),
                      (R.PlaceholderText, TEXT_DIM), (R.Mid, BORDER), (R.Dark, BG0), (R.Light, BG3), (R.Midlight, BG3), (R.Shadow, "#000000")]:
        p.setColor(role, QColor(col))
    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(G.Disabled, role, QColor("#5c6068"))
    return p


STYLE = f"""
* {{ outline: 0; }}
QMainWindow, QDialog {{ background: {BG1}; }}
QMenuBar {{ background: {BG1}; padding: 0.15em 0.3em; }}
QMenuBar::item {{ padding: 0.3em 0.7em; border-radius: 0.3em; background: transparent; }}
QMenuBar::item:selected {{ background: {BG3}; }}
QMenu {{ background: {BG2}; border: 1px solid {BORDER}; border-radius: 0.4em; padding: 0.3em; }}
QMenu::item {{ padding: 0.35em 1.6em 0.35em 1em; border-radius: 0.3em; }}
QMenu::item:selected {{ background: {ACCENT}; color: white; }}
QMenu::item:disabled {{ color: #5c6068; }}
QMenu::separator {{ height: 1px; background: {BORDER}; margin: 0.3em 0.5em; }}
QStatusBar {{ background: {BG0}; color: {TEXT_DIM}; }}
QStatusBar::item {{ border: 0; }}
QToolTip {{ background: {BG3}; color: {TEXT}; border: 1px solid {BORDER}; padding: 0.4em; }}

QPushButton, QToolButton {{ background: {BG3}; border: 1px solid {BORDER}; border-radius: 0.4em; padding: 0.3em 0.4em; }}
QPushButton:hover, QToolButton:hover {{ background: #393c42; border-color: #4a4e55; }}
QPushButton:pressed, QToolButton:pressed {{ background: {BG2}; }}
QPushButton:default {{ border-color: {ACCENT}; }}
QPushButton:disabled, QToolButton:disabled {{ background: {BG2}; color: #5c6068; border-color: {BG3}; }}

QLineEdit, QPlainTextEdit, QTextBrowser, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {BG0}; border: 1px solid {BORDER}; border-radius: 0.4em; padding: 0.3em 0.5em;
    selection-background-color: {ACCENT}; }}
QLineEdit:focus, QPlainTextEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{ border: 0; width: 1.6em; }}
QComboBox QAbstractItemView {{ background: {BG2}; border: 1px solid {BORDER}; selection-background-color: {ACCENT}; outline: 0; }}
QSpinBox::up-button, QSpinBox::down-button, QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{ width: 1.4em; border: 0; background: transparent; }}

QTreeWidget, QListWidget, QTreeView {{ background: {BG0}; border: 1px solid {BORDER}; border-radius: 0.4em; alternate-background-color: {BG0}; }}
QTreeView::item {{ padding: 0.2em 0; border-radius: 0.25em; }}
QTreeView::item:hover {{ background: {BG2}; }}
QTreeView::item:selected {{ background: {ACCENT}; color: white; }}
QHeaderView::section {{ background: {BG2}; border: 0; padding: 0.3em 0.5em; }}

QSlider::groove:horizontal {{ height: 0.3em; background: {BG3}; border-radius: 0.15em; }}
QSlider::sub-page:horizontal {{ background: {ACCENT}; border-radius: 0.15em; }}
QSlider::handle:horizontal {{ background: {TEXT}; width: 1em; margin: -0.35em 0; border-radius: 0.5em; }}
QSlider::handle:horizontal:hover {{ background: white; }}

QCheckBox {{ spacing: 0.5em; }}
QCheckBox::indicator {{ width: 1em; height: 1em; border: 1px solid #5a5e66; border-radius: 0.25em; background: {BG0}; }}
QCheckBox::indicator:checked {{ background: {ACCENT}; border-color: {ACCENT}; }}

QScrollBar:vertical {{ background: transparent; width: 0.8em; margin: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 0.8em; margin: 0; }}
QScrollBar::handle {{ background: #3f434a; border-radius: 0.3em; min-height: 2em; min-width: 2em; margin: 0.1em; }}
QScrollBar::handle:hover {{ background: #565b64; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ background: none; border: 0; width: 0; height: 0; }}

QSplitter::handle {{ background: {BG1}; }}
QSplitter::handle:hover {{ background: {ACCENT}; }}
QSplitter::handle:horizontal {{ width: 0.35em; }}
QSplitter::handle:vertical {{ height: 0.35em; }}
QScrollArea {{ border: 0; background: transparent; }}
QGroupBox {{ border: 1px solid {BORDER}; border-radius: 0.5em; margin-top: 1em; padding-top: 0.6em; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 0.8em; padding: 0 0.3em; color: {TEXT_DIM}; }}
QProgressBar {{ background: {BG0}; border: 0; border-radius: 0.3em; text-align: center; }}
QProgressBar::chunk {{ background: {ACCENT}; border-radius: 0.3em; }}
"""


def apply(app: QApplication) -> None:
    """Install the style, palette and stylesheet. Call once, before the first window is made."""
    app.setStyle("Fusion")  # the only built-in style that follows a custom palette on every platform
    app.setPalette(_palette())
    app.setStyleSheet(STYLE)
