"""The Help window: a section tree on the left, the whole guide as one scrolling page on the right.

Click a section to jump to it, or just scroll: the tree follows along and opens the section you are reading.
Tables get borders from the current theme's colours, so they stay visible in light and dark themes.
"""
from __future__ import annotations

import html

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QTextCursor
from PyQt6.QtWidgets import (QDialog, QDialogButtonBox, QLineEdit, QSplitter, QTextBrowser, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from . import uiscale
from .helpdoc import Colors, Section


def theme_colors(pal: QPalette) -> Colors:
    base, alt = pal.color(QPalette.ColorRole.Base), pal.color(QPalette.ColorRole.AlternateBase)
    if alt == base:  # some themes use the same colour for both
        alt = pal.color(QPalette.ColorRole.Window)
    return Colors(border=pal.color(QPalette.ColorRole.Mid).name(), head=alt.name(), cell=base.name())


def _plain(fragment: str) -> str:
    """Searchable text of an HTML fragment."""
    probe = QTextBrowser(); probe.setHtml(fragment)
    return probe.toPlainText().lower()


class HelpDialog(QDialog):
    """`build(colors)` returns the list of Section to show. `start` is the id of the section to open on."""

    def __init__(self, title: str, build, parent=None, start: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(title); self.resize(uiscale.px(1040), uiscale.px(720))
        self.sections: list[Section] = build(theme_colors(self.palette()))
        self.items: dict[str, QTreeWidgetItem] = {}
        self.text: dict[str, str] = {}
        self._syncing = False
        self._searching = False
        self._positions: list[tuple[float, str]] = []
        self._start = start or (self.sections[0].id if self.sections else None)

        self.search = QLineEdit(placeholderText="Search this guide", clearButtonEnabled=True)
        self.tree = QTreeWidget(); self.tree.setHeaderHidden(True); self.tree.setIndentation(14)
        self.tree.setMinimumWidth(uiscale.px(190))
        self.view = QTextBrowser(); self.view.setOpenExternalLinks(True)
        parts = []
        for sec in self.sections:
            top = QTreeWidgetItem(self.tree, [sec.title]); top.setData(0, Qt.ItemDataRole.UserRole, sec.id)
            f = QFont(top.font(0)); f.setBold(True); top.setFont(0, f)
            self.items[sec.id] = top; self.text[sec.id] = sec.title.lower() + " " + _plain(sec.html)
            parts.append(f'<h2><a name="{sec.id}">{html.escape(sec.title)}</a></h2>{sec.html}')
            for ch in sec.children:
                it = QTreeWidgetItem(top, [ch.title]); it.setData(0, Qt.ItemDataRole.UserRole, ch.id)
                self.items[ch.id] = it; self.text[ch.id] = ch.title.lower() + " " + _plain(ch.html)
                parts.append(f'<h3><a name="{ch.id}">{html.escape(ch.title)}</a></h3>{ch.html}')
            parts.append("<hr>")
        self.view.setHtml("".join(parts))

        left = QWidget(); ll = QVBoxLayout(left); ll.setContentsMargins(0, 0, 0, 0)
        ll.addWidget(self.search); ll.addWidget(self.tree)
        split = QSplitter(); split.addWidget(left); split.addWidget(self.view); split.setSizes([250, 790]); split.setStretchFactor(1, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close); bb.rejected.connect(self.close)
        lay = QVBoxLayout(self); lay.addWidget(split, 1); lay.addWidget(bb)

        self.tree.currentItemChanged.connect(self._tree_moved)
        self.view.verticalScrollBar().valueChanged.connect(self._scrolled)
        self.search.textChanged.connect(self._filter)
        self.search.returnPressed.connect(lambda: self._find(self.search.text()))
        self.view.document().documentLayout().documentSizeChanged.connect(lambda _: self._positions.clear())

    def showEvent(self, e):
        super().showEvent(e)
        if self._start:  # jump once the page has been laid out, or the anchor position is not known yet
            start, self._start = self._start, None
            QTimer.singleShot(0, lambda: self._go(start))

    # ---- navigation
    def _go(self, sid: str):
        item = self.items.get(sid)
        if item is None:
            return
        self._syncing = True
        self.tree.setCurrentItem(item)
        self._open_only(item)
        self._syncing = False
        self.view.scrollToAnchor(sid)

    def _tree_moved(self, item, _prev):
        if item is not None and not self._syncing:
            self._go(item.data(0, Qt.ItemDataRole.UserRole))

    def _open_only(self, item):
        """Accordion: keep the section being read open and fold the others (unless a search is showing matches)."""
        top = item.parent() or item
        if not self._searching:
            for i in range(self.tree.topLevelItemCount()):
                t = self.tree.topLevelItem(i)
                t.setExpanded(t is top)
        else:
            top.setExpanded(True)

    def _anchor_positions(self) -> list[tuple[float, str]]:
        if not self._positions:
            doc = self.view.document(); lay = doc.documentLayout(); out = []; block = doc.begin()
            while block.isValid():
                it = block.begin()
                while not it.atEnd():
                    frag = it.fragment()
                    if frag.isValid():
                        out += [(lay.blockBoundingRect(block).top(), n) for n in frag.charFormat().anchorNames() if n in self.items]
                    it += 1
                block = block.next()
            self._positions = sorted(out)
        return self._positions

    def _scrolled(self, value: int):
        """Follow the page: highlight the section whose heading was scrolled past last."""
        pos = self._anchor_positions()
        if not pos or self._start:
            return
        bar = self.view.verticalScrollBar()
        y = value + 8
        sid = pos[-1][1] if value >= bar.maximum() else next((n for yy, n in reversed(pos) if yy <= y), pos[0][1])
        item = self.items[sid]
        if item is not self.tree.currentItem():
            self._syncing = True
            self.tree.setCurrentItem(item)
            self._open_only(item)
            self._syncing = False

    # ---- search
    def _filter(self, text: str):
        q = text.strip().lower()
        self._searching = bool(q)
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i); any_child = False
            for j in range(top.childCount()):
                ch = top.child(j); hit = not q or q in self.text[ch.data(0, Qt.ItemDataRole.UserRole)]
                ch.setHidden(not hit); any_child = any_child or hit
            top_hit = not q or q in self.text[top.data(0, Qt.ItemDataRole.UserRole)]
            top.setHidden(not (top_hit or any_child))
            if q:
                top.setExpanded(any_child)
        if not q:
            cur = self.tree.currentItem()
            if cur is not None:
                self._open_only(cur)

    def _find(self, text: str):
        """Enter in the search box: highlight the next occurrence on the page, wrapping at the end."""
        if text and not self.view.find(text):
            self.view.moveCursor(QTextCursor.MoveOperation.Start)
            self.view.find(text)
