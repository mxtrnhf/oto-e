import unittest

from tests import helpers  # noqa: F401  (sets up the environment)
from oto_e import effects, recipe


class RecipeTests(unittest.TestCase):
    def test_every_effect_round_trips(self):
        for e in effects.EFFECTS:
            params = {q.key: q.default for q in e.params}
            eff, back, notes = recipe.from_text(recipe.to_text({"name": e.name, "params": params}))
            self.assertIs(eff, e); self.assertEqual(back, params, e.name); self.assertEqual(notes, [])

    def test_choices_are_stored_by_text(self):
        e, q = next((e, q) for e in effects.EFFECTS for q in e.params if q.choices)
        text = recipe.to_text({"name": e.name, "params": {q.key: 1}})
        self.assertIn(q.choices[1], text)

    def test_bad_input(self):
        for bad in ["hi", "{}", '{"v":1,"effect":"No such effect"}', '{"v":99,"effect":"Echo"}', "[1,2]"]:
            with self.assertRaises(recipe.RecipeError, msg=bad):
                recipe.from_text(bad)

    def test_unknown_and_out_of_range_settings_are_reported(self):
        e = effects.by_name("Echo"); q = e.params[0]
        _, params, notes = recipe.from_text('{"v":1,"effect":"Echo","params":{"zzz":1,"%s":%s}}' % (q.key, q.max * 10))
        self.assertEqual(params[q.key], q.max); self.assertEqual(len(notes), 2)

    def test_old_steps_use_their_legacy_value(self):
        e = effects.by_name("Tape Recording (record → age → playback)")
        old = {q.key: q.default for q in e.params if q.key != "deck_wf"}
        self.assertEqual(effects.complete_params(e, old)["deck_wf"], 1)  # saved before the switch existed: the machines' wobble was on
        self.assertEqual(effects.complete_params(e, {**old, "deck_wf": 0})["deck_wf"], 0)
        self.assertIn("Include", recipe.to_text({"name": e.name, "params": old}))


if __name__ == "__main__":
    unittest.main()
