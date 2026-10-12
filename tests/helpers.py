"""Shared set-up for the tests: a small picture, and a document with a few edits (including a branch)."""
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="oto-e-test-cfg-")  # the tests never touch the real settings
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np  # noqa: E402
from PIL import Image  # noqa: E402

from oto_e import effects  # noqa: E402
from oto_e.core import Document, Rect, norm_sel  # noqa: E402


def make_image(path, w=64, h=48, seed=3):
    rng = np.random.default_rng(seed)
    Image.fromarray(rng.integers(0, 255, (h, w, 3), dtype=np.uint8)).save(path)


def apply(doc: Document, name: str, params: dict | None = None, sel=None):
    e = effects.by_name(name)
    p = {q.key: q.default for q in e.params}; p.update(params or {})
    doc.commit(doc.compute(e, p, sel), {"name": name, "params": p, "sel": norm_sel(sel), "mode": doc.mode, "fmt": doc.fmt, "random": False})


def edited_document(tmpdir) -> Document:
    """Original -> Echo -> Bitcrusher, then back to Echo and a different branch (Amplify on a rectangle... or a run), with planar mode switched on."""
    img = Path(tmpdir) / "a.png"; make_image(img)
    d = Document(); d.open(str(img))
    apply(d, "Echo"); apply(d, "Bitcrusher"); d.undo()
    apply(d, "Amplify", sel=(100, 900))
    d.mode = 1
    apply(d, "Invert")
    return d
