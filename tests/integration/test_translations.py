"""Übersetzungen: drei Sprachen mit denselben Schlüsseln und Platzhaltern, erzeugt aus make_translations.py."""

import importlib.util
import json
from pathlib import Path
import re
import string

import pytest

from custom_components.tipsylab.texts import LANGS, TEXTS

ROOT = Path(__file__).parents[2]
BASE = ROOT / "custom_components" / "tipsylab"


def _load(name: str) -> dict:
    return json.loads((BASE / name).read_text())


def _flat(d: dict, prefix: str = "") -> dict[str, str]:
    out = {}
    for k, v in d.items():
        if isinstance(v, dict):
            out.update(_flat(v, f"{prefix}{k}."))
        else:
            out[f"{prefix}{k}"] = v
    return out


def _fields(text: str) -> set[str]:
    return {f for _, f, _, _ in string.Formatter().parse(text) if f}


@pytest.mark.parametrize("lang", ["de", "fr"])
def test_same_keys_and_placeholders_as_english(lang: str):
    en, other = _flat(_load("translations/en.json")), _flat(_load(f"translations/{lang}.json"))
    assert other.keys() == en.keys()
    for key, text in en.items():
        assert _fields(other[key]) == _fields(text), key


def test_generated_files_are_current():
    """strings.json und translations/ nie von Hand ändern: sie müssen dem Skript entsprechen."""
    spec = importlib.util.spec_from_file_location("make_translations", ROOT / "tools" / "make_translations.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert _load("strings.json") == module.tr("en")
    for lang in module.LANGS:
        assert _load(f"translations/{lang}.json") == module.tr(lang), lang


def test_server_texts_have_three_languages_with_the_same_placeholders():
    assert LANGS == ("de", "en", "fr")
    for key, texts in TEXTS.items():
        assert len(texts) == 3, key
        assert len({frozenset(_fields(t)) for t in texts}) == 1, key


def test_panel_texts_come_in_three_languages():
    """Jedes L(…) im Panel hat drei Texte; ein vergessener ergäbe „undefined“ in einer Sprache."""
    src = (BASE / "frontend" / "tipsylab-panel.js").read_text()
    calls = 0
    for m in re.finditer(r"(?<![\w.])L\(", src):
        depth, i, args, quote = 1, m.end(), 1, None
        while depth:
            c = src[i]
            if quote:
                if c == "\\":
                    i += 1
                elif c == quote:
                    quote = None
                elif quote == "`" and src.startswith("${", i):
                    # Ausdruck im Template-String: bis zur passenden Klammer überspringen
                    j, inner = i + 2, 1
                    while inner:
                        inner += {"{": 1, "}": -1}.get(src[j], 0)
                        j += 1
                    i = j - 1
            elif c in "\"'`":
                quote = c
            elif c in "([{":
                depth += 1
            elif c in ")]}":
                depth -= 1
            elif c == "," and depth == 1:
                args += 1
            i += 1
        if src[m.start() - 6 : m.start()] == "const ":
            continue  # die Definition selbst
        trailing = src[: i - 1].rstrip().endswith(",")
        assert args - trailing == 3, src[m.start() : m.start() + 120]
        calls += 1
    assert calls > 150
