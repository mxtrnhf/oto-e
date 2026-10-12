import threading
import time
import unittest

from tests import helpers
from PyQt6.QtWidgets import QApplication

from oto_e import app, effects

QT = QApplication.instance() or QApplication([])


def wait(cond, timeout=60):
    t = time.time()
    while not cond() and time.time() - t < timeout:
        QT.processEvents(); time.sleep(0.003)
    assert cond(), "timed out"


class DialogTests(unittest.TestCase):
    def test_display_precision_never_changes_a_default_or_preset(self):
        for e in effects.EFFECTS:
            for p in e.params:
                if p.integer or p.choices:
                    continue
                dec = app.ParamRow._decimals(p)
                for v in [p.default] + [pr[p.key] for pr in e.presets.values() if p.key in pr]:
                    self.assertAlmostEqual(round(v, dec), v, msg=f"{e.name}/{p.key}")

    def test_tape_dialog_folds_advanced_settings_and_starts_from_its_preset(self):
        e = effects.by_name("Tape Recording (record → age → playback)")
        d = app.EffectDialog(e, {}, lambda v: None)
        self.assertEqual(d.preset_cb.currentText(), e.default_preset)
        self.assertFalse(d.adv_toggle.isChecked()); self.assertEqual(d.adv_toggle.text(), "Advanced settings (15)")
        d.rows["azimuth"].set_value(40); d._update_adv_label()
        self.assertIn("1 changed", d.adv_toggle.text())
        d2 = app.EffectDialog(e, {**d.values()}, lambda v: None)  # opened with your own values: Advanced opens by itself
        self.assertTrue(d2.adv_toggle.isChecked())

    def test_slow_warning_follows_generations(self):
        e = effects.by_name("Tape Recording (record → age → playback)")
        d = app.EffectDialog(e, {}, lambda v: None); d.show(); QT.processEvents()
        d.rows["gens"].w.setValue(2); self.assertFalse(d.rows["gens"].slow.isVisible())
        d.rows["gens"].w.setValue(5); self.assertTrue(d.rows["gens"].slow.isVisible())


class WindowTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        from pathlib import Path
        self.tmp = tempfile.TemporaryDirectory(); self.img = Path(self.tmp.name) / "a.png"; helpers.make_image(self.img)
        self.w = app.MainWindow(); self.w.open_path(str(self.img), confirmed=True); wait(lambda: self.w.doc.loaded)

    def tearDown(self):
        w = self.w
        w._autosave_timer.stop(); w._job_pool.waitForDone(); w._save_pool.waitForDone(); w._pv_pool.waitForDone()
        QT.processEvents()
        QApplication.instance().removeEventFilter(w)  # the window installs itself as an application-wide filter (for the C key)
        QApplication.instance().removeEventFilter(w._tooltips)
        w.hide(); w.deleteLater(); QT.processEvents()
        self.tmp.cleanup()

    def test_opening_is_refused_while_an_effect_dialog_is_open(self):
        self.w.run_effect(effects.by_name("Echo")); doc = self.w.doc
        self.w.open_path(str(self.img), confirmed=True)
        self.assertIn("Finish or cancel", self.w.statusBar().currentMessage()); self.assertIs(self.w.doc, doc)
        self.w._dlg.reject()

    def test_a_failing_callback_does_not_crash(self):
        import sys
        seen = []; old = sys.excepthook; sys.excepthook = lambda *x: seen.append(x[1])
        try:
            self.w._run_job(lambda: 1, lambda r: 1 / 0); wait(lambda: seen)
        finally:
            sys.excepthook = old
        self.assertIsInstance(seen[0], ZeroDivisionError)

    def test_given_up_jobs_are_capped(self):
        gate = threading.Event()
        for _ in range(self.w.MAX_ABANDONED):
            self.w._run_job(lambda: gate.wait(20), lambda r: None, lock="slow"); self.w._cancel_busy()
        self.assertIsNone(self.w._run_job(lambda: 1, lambda r: None, lock="x"))
        gate.set(); wait(lambda: not self.w._abandoned)
        self.assertIsNotNone(self.w._run_job(lambda: 1, lambda r: None, lock="x")); wait(lambda: self.w._busy is None)

    def test_export_again_numbers_files(self):
        from pathlib import Path
        out = Path(self.tmp.name) / "pic.png"
        self.w._write_image(str(out), {}); wait(lambda: not self.w._jobs)
        self.w.export_again(); wait(lambda: not self.w._jobs); self.w.export_again(); wait(lambda: not self.w._jobs)
        self.assertEqual(sorted(p.name for p in out.parent.glob("pic*.png")), ["pic.png", "pic_2.png", "pic_3.png"])

    def test_recovery_file_round_trip(self):
        e = effects.by_name("Echo"); self.w._apply(e, {q.key: q.default for q in e.params}); wait(lambda: self.w._busy is None and len(self.w.doc.nodes) == 2)
        self.w._autosave(); wait(lambda: not self.w._autosaving)
        self.assertTrue(self.w._recovery_path().exists())
        w2 = app.MainWindow(); w2._autosave_timer.stop()
        w2.open_path(str(self.w._recovery_path()), confirmed=True, recovered=True); wait(lambda: w2.doc.loaded)
        self.assertEqual(len(w2.doc.nodes), 2); self.assertTrue(w2.doc.dirty); self.assertIsNone(w2.doc.path)
        self.w._clear_recovery()

    def test_paste_recipe_reads_the_clipboard(self):
        QApplication.clipboard().setText("junk"); self.assertIsNone(self.w._clipboard_recipe())
        QApplication.clipboard().setText('{"v":1,"effect":"Echo","params":{}}'); self.assertEqual(self.w._clipboard_recipe(), "Echo")


if __name__ == "__main__":
    unittest.main()
