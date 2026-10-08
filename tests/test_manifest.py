"""Cohérence des métadonnées du dépôt (sans dépendre de Home Assistant)."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMPONENT = ROOT / "custom_components" / "eero"


def _const_domain() -> str:
    match = re.search(r'^DOMAIN(?:: str)? = "([^"]+)"', (COMPONENT / "const.py").read_text(encoding="utf-8"), re.M)
    assert match, "DOMAIN introuvable dans const.py"
    return match.group(1)


def test_manifest_domain_matches_const():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["domain"] == _const_domain() == COMPONENT.name


def test_domain_is_unchanged():
    # Le domaine reste celui de schmittx/home-assistant-eero : les installations
    # existantes gardent leur entrée de configuration, leurs appareils et leurs entités.
    assert _const_domain() == "eero"


def test_manifest_points_to_this_repository():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["codeowners"] == ["@Xaoimoon"]
    assert manifest["documentation"] == "https://github.com/Xaoimoon/ha-eero"
    assert manifest["issue_tracker"] == "https://github.com/Xaoimoon/ha-eero/issues"


def test_manifest_version_is_semver():
    manifest = json.loads((COMPONENT / "manifest.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d+\.\d+\.\d+", manifest["version"])


def test_hacs_json_is_valid():
    hacs = json.loads((ROOT / "hacs.json").read_text(encoding="utf-8"))
    assert hacs["name"] and hacs["homeassistant"]


def test_brand_images():
    # Servies par Home Assistant (≥ 2026.6) depuis le dossier `brand/` de l'intégration.
    brand = COMPONENT / "brand"
    expected = {
        "icon.png": (256, 256),
        "icon@2x.png": (512, 512),
        "logo.png": None,
        "logo@2x.png": None,
    }
    expected |= {f"dark_{name}": size for name, size in expected.items()}
    assert {p.name for p in brand.iterdir()} == set(expected)
    for name, size in expected.items():
        header = (brand / name).read_bytes()[:24]
        assert header[:8] == b"\x89PNG\r\n\x1a\n"
        if size:
            assert (int.from_bytes(header[16:20], "big"), int.from_bytes(header[20:24], "big")) == size
