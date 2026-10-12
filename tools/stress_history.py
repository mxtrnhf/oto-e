"""History memory, trimming and project save/load under load, with no UI. Usage: stress_history.py PROJECT_OR_IMAGE [STEPS]

Applies STEPS whole-picture edits (default 60), reporting memory and trimming, then saves, reloads and checks the result.
"""
import os
import resource
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from oto_e import effects, project  # noqa: E402
from oto_e.core import Document, norm_sel  # noqa: E402


def rss():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main():
    src, steps = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 60
    d = Document()
    project.load(d, src) if src.endswith(project.EXT) else d.open(src)
    print(f"{d.size}, start peak {rss():.0f} MB", flush=True)
    names = ["Add Noise", "Echo", "Bitcrusher", "Tremolo"]
    t0 = time.perf_counter()
    for i in range(steps):
        e = effects.by_name(names[i % len(names)]); p = {q.key: q.default for q in e.params}
        if "seed" in p: p["seed"] = i
        d.commit(d.compute(e, p, None), {"name": e.name, "params": p, "sel": None, "mode": d.mode, "fmt": d.fmt, "random": False})
        if i % 10 == 9:
            print(f"step {i + 1}: nodes {len(d.nodes)}, history {d.history_bytes() / 1e6:.0f} MB, peak {rss():.0f} MB, {time.perf_counter() - t0:.0f}s", flush=True)
    print(f"root is {d.root.info.get('name')!r}, trimmed: {d.root.info.get('name') == '(earlier steps trimmed)'}")
    out = os.path.join(tempfile.mkdtemp(dir=os.environ.get("CLAUDE_JOB_DIR")), "h.otoe")
    t = time.perf_counter(); snap = project.snapshot(d); print(f"snapshot {time.perf_counter() - t:.2f}s (this is the UI-thread part)")
    t = time.perf_counter(); project.write(snap, out); print(f"write {time.perf_counter() - t:.1f}s -> {os.path.getsize(out) / 1e6:.0f} MB, peak {rss():.0f} MB")
    d2 = Document()
    t = time.perf_counter(); project.load(d2, out); print(f"load {time.perf_counter() - t:.1f}s, peak {rss():.0f} MB")
    assert (d2.live == d.live).all() and (d2.original == d.original).all() and len(d2.nodes) == len(d.nodes)
    ids = sorted(d.nodes)[::7]
    for nid in ids:
        d.goto(nid); d2.goto(nid); assert (d.live == d2.live).all(), nid
    print(f"verified {len(ids)} sampled steps identical after reload")


main()
