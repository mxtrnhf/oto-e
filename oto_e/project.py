"""The .otoe project file: the original picture plus the whole edit history, so a session can be closed and picked up again.

It is a zip, so any archive tool can open it:
  history.json   every history step (name, settings, selection...), how the steps connect, and which one is current
  original.png  the picture as it was opened (what Revert and Compare use)
  current.png   the picture as it stands now
  steps/N.bin   the raw bytes step N overwrote, exactly as the history holds them in memory

Nothing is recomputed on opening, so a project looks the same on any machine and any version of the libraries behind the effects. Qt-free on purpose.
"""
from __future__ import annotations

import io
import json
import os
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

from .core import Document, Node, Rect, Step

VERSION = 1
EXT = ".otoe"


class ProjectError(ValueError):
    pass


def _png(px: np.ndarray, size) -> bytes:
    w, h = size
    buf = io.BytesIO()
    Image.fromarray(px.reshape(h, w, 3), "RGB").save(buf, "PNG", compress_level=6)
    return buf.getvalue()


def _unpng(data: bytes, size) -> np.ndarray:
    with Image.open(io.BytesIO(data)) as im:
        if im.size != tuple(size):
            raise ProjectError("The picture inside the project has the wrong size")
        return np.asarray(im.convert("RGB"), dtype=np.uint8).reshape(-1).copy()


def _jsonable(o):
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    raise TypeError(f"cannot store {type(o).__name__}")


def _info_from_json(info: dict) -> dict:
    sel = info.get("sel")
    if sel:
        info = {**info, "sel": Rect(*sel) if len(sel) == 4 else tuple(sel)}
    return info


def save(doc: Document, path: str):
    """Write `doc` to `path` (replaced only once the whole file is written)."""
    nodes = sorted(doc.nodes.values(), key=lambda n: n.id)
    manifest = {
        "app": "oto-e", "v": VERSION, "size": list(doc.size), "source_name": doc.source_name, "mode": doc.mode, "fmt": doc.fmt,
        "current": doc.node.id, "root": doc.root.id, "next_id": doc._next_id,
        "nodes": [{"id": n.id, "parent": n.parent.id if n.parent else None, "info": n.info,
                   "redo": n.redo_child.id if n.redo_child else None, "lo": n.step.lo if n.step else None} for n in nodes],
    }
    tmp = f"{path}.tmp"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
            z.writestr("history.json", json.dumps(manifest, default=_jsonable, indent=1, ensure_ascii=False))
            z.writestr("original.png", _png(doc.original, doc.size), zipfile.ZIP_STORED)
            z.writestr("current.png", _png(doc.live, doc.size), zipfile.ZIP_STORED)
            for n in nodes:
                if n.step:
                    z.writestr(f"steps/{n.id}.bin", n.step.data.tobytes())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


def load(doc: Document, path: str):
    """Replace `doc`'s picture and history with the project at `path`. `doc` is untouched if the file is bad."""
    try:
        with zipfile.ZipFile(path) as z:
            m = json.loads(z.read("history.json"))
            if m.get("app") != "oto-e" or not isinstance(m.get("v"), int):
                raise ProjectError("This is not an Oto-e project")
            if m["v"] > VERSION:
                raise ProjectError("This project was saved by a newer version of Oto-e")
            size = tuple(m["size"]); total = size[0] * size[1] * 3
            original, live = _unpng(z.read("original.png"), size), _unpng(z.read("current.png"), size)
            nodes: dict[int, Node] = {}
            for e in m["nodes"]:  # parents always have smaller ids than their children
                step = None
                if e["lo"] is not None:
                    data = np.frombuffer(z.read(f"steps/{e['id']}.bin"), np.uint8).copy()
                    if e["lo"] < 0 or e["lo"] + len(data) > total:
                        raise ProjectError("A history step does not fit the picture")
                    step = Step(e["lo"], data)
                parent = nodes[e["parent"]] if e["parent"] is not None else None
                n = Node(e["id"], parent, _info_from_json(e["info"]), step)
                if parent:
                    parent.children.append(n)
                nodes[n.id] = n
            for e in m["nodes"]:
                nodes[e["id"]].redo_child = nodes[e["redo"]] if e["redo"] is not None else None
            root, cur = nodes[m["root"]], nodes[m["current"]]
            mode, fmt = int(m["mode"]), int(m["fmt"])
            next_id, name = int(m["next_id"]), str(m["source_name"])
    except ProjectError:
        raise
    except (OSError, KeyError, IndexError, TypeError, ValueError, zipfile.BadZipFile, Image.UnidentifiedImageError) as e:
        raise ProjectError(f"This is not a readable Oto-e project ({e})") from None
    doc.size, doc.original, doc.live = size, original, live
    doc.nodes, doc.root, doc.node, doc._next_id = nodes, root, cur, next_id
    doc.mode, doc.fmt, doc.source_name = mode, fmt, name
    doc.path = Path(path); doc.dirty = False
