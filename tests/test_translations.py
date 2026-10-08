"""Cohérence des traductions avec strings.json (sans dépendre de Home Assistant)."""

import json
import re
from pathlib import Path

import pytest

COMPONENT = Path(__file__).resolve().parent.parent / "custom_components" / "eero"
STRINGS = json.loads((COMPONENT / "strings.json").read_text(encoding="utf-8"))
LANGUAGES = sorted(p.stem for p in (COMPONENT / "translations").glob("*.json"))


def _flatten(node, prefix=""):
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _flatten(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), node


def _load(language: str) -> dict[str, str]:
    path = COMPONENT / "translations" / f"{language}.json"
    return dict(_flatten(json.loads(path.read_text(encoding="utf-8"))))


def test_french_translation_exists():
    assert "fr" in LANGUAGES


@pytest.mark.parametrize("language", LANGUAGES)
def test_same_keys_as_strings(language):
    assert set(_load(language)) == set(dict(_flatten(STRINGS)))


@pytest.mark.parametrize("language", LANGUAGES)
def test_placeholders_preserved(language):
    # Un {placeholder} manquant ou renommé fait échouer l'affichage du formulaire.
    reference = dict(_flatten(STRINGS))
    for key, text in _load(language).items():
        assert set(re.findall(r"\{\w+\}", text)) == set(re.findall(r"\{\w+\}", reference[key])), key
