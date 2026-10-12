"""Time every effect at its default settings on a big picture, with no UI. Usage: stress_effects.py PROJECT_OR_IMAGE [OUT.tsv] [--max]

--max sets every setting to its largest value instead of its default (usually the slowest case).

Prints one line per effect (seconds, peak memory so far) as it goes, slowest last in the summary.
"""
import resource
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from oto_e import effects, project  # noqa: E402
from oto_e.core import Document  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if a != "--max"]; heavy = "--max" in sys.argv
    src = args[0]
    d = Document()
    project.load(d, src) if src.endswith(project.EXT) else d.open(src)
    d.live = d.original.copy()
    print(f"{d.size[0]}x{d.size[1]}, {len(d.live) / 1e6:.1f} MB", flush=True)
    rows = []
    for e in effects.EFFECTS:
        p = {q.key: (q.max if heavy else q.default) for q in e.params}
        t = time.perf_counter()
        try:
            d.compute(e, p, None)
            err = ""
        except Exception as x:  # noqa: BLE001
            err = f"{type(x).__name__}: {x}"
        dt = time.perf_counter() - t
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        rows.append((dt, e.name, e.domain, rss, err))
        print(f"{dt:8.2f} s  {rss:7.0f} MB  {e.domain:5}  {e.name}  {err}", flush=True)
    print("\nSlowest:")
    for dt, name, dom, rss, err in sorted(rows, reverse=True)[:15]:
        print(f"{dt:8.2f} s  {name}")
    if len(args) > 1:
        Path(args[1]).write_text("".join(f"{dt:.3f}\t{name}\t{dom}\t{rss:.0f}\t{err}\n" for dt, name, dom, rss, err in rows))


main()
