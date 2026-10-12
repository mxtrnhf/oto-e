"""A recipe: one effect and its settings as a line of JSON, to share by pasting.

Unlike steptext.py this is read back in. It holds no selection, reading mode or format; those come from the document you paste it into.
Choice settings are stored by their text, not their index, so reordering an effect's choices later does not change old recipes.
"""
from __future__ import annotations

import json

from . import effects

VERSION = 1


class RecipeError(ValueError):
    pass


def to_text(info: dict) -> str:
    """The recipe for one history step's `info`."""
    eff = effects.by_name(info["name"])
    spec = {p.key: p for p in eff.params}
    params = {k: (spec[k].choices[int(v)] if k in spec and spec[k].choices else v) for k, v in (info.get("params") or {}).items()}
    return json.dumps({"v": VERSION, "effect": eff.name, "params": params}, ensure_ascii=False)


def from_text(text: str) -> tuple[effects.Effect, dict, list[str]]:
    """(effect, complete parameter dict, notes about anything that was ignored or adjusted). Raises RecipeError."""
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        raise RecipeError("This is not a recipe") from None
    if not isinstance(data, dict) or "effect" not in data:
        raise RecipeError("This is not a recipe")
    if not isinstance(data.get("v"), int) or data["v"] > VERSION:
        raise RecipeError("This recipe comes from a newer version of Oto-e")
    try:
        eff = effects.by_name(data["effect"])
    except (StopIteration, TypeError):
        raise RecipeError(f"Unknown effect: {data['effect']}") from None
    given = data.get("params") or {}
    if not isinstance(given, dict):
        raise RecipeError("The recipe's settings are malformed")
    notes = [f"ignored unknown setting “{k}”" for k in given if k not in {p.key for p in eff.params}]
    params = {}
    for p in eff.params:
        if p.key not in given:
            params[p.key] = p.default; continue
        v = given[p.key]
        if p.choices:
            if v not in p.choices:
                notes.append(f"{p.label}: unknown choice “{v}”, used the default"); params[p.key] = p.default; continue
            params[p.key] = p.choices.index(v)
        else:
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                notes.append(f"{p.label}: not a number, used the default"); params[p.key] = p.default; continue
            c = min(max(v, p.min), p.max)
            if c != v:
                notes.append(f"{p.label}: {v} is out of range, used {c}")
            params[p.key] = int(round(c)) if p.integer else c
    return eff, params, notes
