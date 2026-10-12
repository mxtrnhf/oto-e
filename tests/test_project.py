import tempfile
import unittest
from pathlib import Path

import numpy as np

from tests import helpers
from oto_e import project
from oto_e.core import Document


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.dir = Path(self.tmp.name)
        self.doc = helpers.edited_document(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_round_trip_every_step(self):
        path = str(self.dir / "p.otoe"); project.save(self.doc, path)
        d2 = Document(); project.load(d2, path)
        self.assertEqual(d2.node.id, self.doc.node.id); self.assertEqual((d2.mode, d2.fmt), (self.doc.mode, self.doc.fmt))
        self.assertTrue((d2.live == self.doc.live).all()); self.assertTrue((d2.original == self.doc.original).all())
        self.assertEqual(d2.entries(), self.doc.entries())
        for nid in sorted(d2.nodes):
            d2.goto(nid); self.doc.goto(nid)
            self.assertTrue((d2.live == self.doc.live).all(), nid)

    def test_selection_types_survive(self):
        path = str(self.dir / "p.otoe"); project.save(self.doc, path)
        d2 = Document(); project.load(d2, path)
        sels = [n.info.get("sel") for n in d2.nodes.values()]
        self.assertIn((100, 900), sels)
        self.assertTrue(all(isinstance(s, tuple) for s in sels if s))

    def test_edits_after_the_snapshot_do_not_reach_the_file(self):
        before = self.doc.live.copy(); n = len(self.doc.nodes)
        snap = project.snapshot(self.doc)
        helpers.apply(self.doc, "Echo"); self.doc.undo(); self.doc.undo()  # edit, then move around the history
        path = str(self.dir / "s.otoe"); project.write(snap, path)
        d2 = Document(); project.load(d2, path)
        self.assertEqual(len(d2.nodes), n); self.assertTrue((d2.live == before).all())

    def test_bad_files_leave_the_document_alone(self):
        bad = self.dir / "bad.otoe"; bad.write_bytes(b"junk")
        d2 = Document(); helpers.make_image(self.dir / "b.png"); d2.open(str(self.dir / "b.png")); live = d2.live.copy()
        with self.assertRaises(project.ProjectError):
            project.load(d2, str(bad))
        self.assertTrue((d2.live == live).all())

    def test_history_memory_limit_trims_oldest_first(self):
        d = self.doc; d.max_history_bytes = 1
        helpers.apply(d, "Echo"); helpers.apply(d, "Echo")
        self.assertLessEqual(len(d.nodes), 3)
        self.assertEqual(d.root.info["name"], "(earlier steps trimmed)")
        path = str(self.dir / "t.otoe"); project.save(d, path)  # a trimmed history still saves and loads
        d2 = Document(); project.load(d2, path); self.assertTrue((d2.live == d.live).all())


if __name__ == "__main__":
    unittest.main()
