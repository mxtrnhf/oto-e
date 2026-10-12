"""Edits made while a project is being saved must not leak into the file, and must keep the document marked unsaved. Usage: stress_races.py IMAGE"""
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication  # noqa: E402

a = QApplication([])
from oto_e import app, effects, project  # noqa: E402
from oto_e.core import Document  # noqa: E402


def wait(cond, to=120):
    t = time.time()
    while not cond() and time.time() - t < to:
        a.processEvents(); time.sleep(0.002)
    assert cond(), "timed out"


w = app.MainWindow()
w.open_path(sys.argv[1], confirmed=True); wait(lambda: w.doc.loaded)
out = os.path.join(tempfile.mkdtemp(dir=os.environ.get("CLAUDE_JOB_DIR")), "r.otoe")
amp = effects.by_name("Amplify"); p = {q.key: q.default for q in amp.params}; p["gain"] = 0.5 if "gain" in p else None
p = {k: v for k, v in p.items() if v is not None}
for rnd in range(5):
    w.randomize(); wait(lambda: w._busy is None)
    before = w.doc.live.copy(); n_before = len(w.doc.nodes)
    w._write_project(out)                      # snapshot taken here
    w._apply(amp, p); w.undo(); w.randomize()   # edit, undo and re-edit while the write runs
    wait(lambda: not w._saving); wait(lambda: w._busy is None)
    d2 = Document(); project.load(d2, out)
    assert (d2.live == before).all() and len(d2.nodes) == n_before, "the saved file picked up edits made during the save"
    assert w.doc.dirty, "edits during the save must leave the document unsaved"
    print(f"round {rnd + 1}: ok ({n_before} steps saved, document now has {len(w.doc.nodes)})")
