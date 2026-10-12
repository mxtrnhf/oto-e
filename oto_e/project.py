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
    Image.fromarray(px.reshape(h, w, 3), "RGB").save(buf, "PNG", compress_level=1)
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


class Snapshot:
    """Everything a save writes, copied out of the live document so the (slow) writing can run on another thread
    while the document carries on changing."""

    def __init__(self, doc: Document):
        nodes = sorted(doc.nodes.values(), key=lambda n: n.id)
        manifest = {
            "app": "oto-e", "v": VERSION, "size": list(doc.size), "source_name": doc.source_name, "mode": doc.mode, "fmt": doc.fmt,
            "current": doc.node.id, "root": doc.root.id, "next_id": doc._next_id,
            "nodes": [{"id": n.id, "parent": n.parent.id if n.parent else None, "info": n.info,
                       "redo": n.redo_child.id if n.redo_child else None, "lo": n.step.lo if n.step else None} for n in nodes],
        }
        self.manifest = json.dumps(manifest, default=_jsonable, indent=1, ensure_ascii=False)
        self.size = doc.size
        self.original = doc.original  # never modified in place, so no copy is needed
        self.original_png = doc.original_png  # already encoded by an earlier save, if any
        self.live = doc.live.copy()
        self.steps = {n.id: n.step.data for n in nodes if n.step}  # no copy: Step.swap rebinds `data` and never writes into the old array


def snapshot(doc: Document) -> Snapshot:
    return Snapshot(doc)


def write(snap: Snapshot, path: str) -> bytes:
    """Write `snap` to `path` (replaced only once the whole file is written). Returns the encoded original picture,
    which the caller may keep on the document so the next save skips encoding it again."""
    original_png = snap.original_png or _png(snap.original, snap.size)
    tmp = f"{path}.tmp"
    try:
        # Light compression: the pictures are glitched noise that barely shrinks, and level 6 costs several times the time for a few percent.
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
            z.writestr("history.json", snap.manifest)
            z.writestr("original.png", original_png, zipfile.ZIP_STORED)
            z.writestr("current.png", _png(snap.live, snap.size), zipfile.ZIP_STORED)
            for nid, data in snap.steps.items():
                z.writestr(f"steps/{nid}.bin", data.tobytes())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return original_png


def save(doc: Document, path: str):
    doc.original_png = write(snapshot(doc), path)


def read(path: str) -> dict:
    """Parse the project at `path` into the state `install` puts on a document. Touches no document, so it can run on any thread."""
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
                    data = np.frombuffer(z.read(f"steps/{e['id']}.bin"), np.uint8)  # read-only is fine: a step is only ever read, then replaced
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
    return {"size": size, "original": original, "live": live, "nodes": nodes, "root": root, "node": cur, "next_id": next_id,
            "mode": mode, "fmt": fmt, "name": name, "path": Path(path)}


def install(doc: Document, s: dict):
    """Replace `doc`'s picture and history with a state from `read`."""
    doc.size, doc.original, doc.live = s["size"], s["original"], s["live"]
    doc.nodes, doc.root, doc.node, doc._next_id = s["nodes"], s["root"], s["node"], s["next_id"]
    doc.mode, doc.fmt, doc.source_name = s["mode"], s["fmt"], s["name"]
    doc.original_png = None
    doc.path = s["path"]; doc.dirty = False


def load(doc: Document, path: str):
    """read + install. `doc` is untouched if the file is bad."""
    install(doc, read(path))
