"""コマンド追加用の汎用ビルド。"""

from __future__ import annotations

CRIT_ATK = {"crit_rate": 2.0, "crit_dmg": 1.0, "atk_pct": 1.0}
CRIT_HP = {"crit_rate": 2.0, "crit_dmg": 1.0, "hp_pct": 1.0}
CRIT_DEF = {"crit_rate": 2.0, "crit_dmg": 1.0, "def_pct": 1.0}
CRIT_EM = {"crit_rate": 2.0, "crit_dmg": 1.0, "em": 0.25}
ER_CRIT = {"crit_rate": 2.0, "crit_dmg": 1.0, "er": 1.0, "atk_pct": 1.0}

DEFAULT_PREF = {
    "pyro": ["crimson", "shimenawa", "obsidian", "rising_winds"],
    "hydro": ["heart_of_depth", "nymph", "marechaussee", "dawnstar"],
    "cryo": ["blizzard", "deep_galleries", "furnace_heart", "marechaussee"],
    "electro": ["thundering", "emblem", "sky_unveiling", "obsidian"],
    "anemo": ["viridescent", "rising_winds", "crimson_oath", "obsidian"],
    "geo": ["husk", "cinder", "nighttime", "golden_troupe"],
    "dendro": ["deepwood", "gilded", "sky_unveiling", "paradise"],
}

SCALES = ("atk", "hp", "def", "em", "er")


def _row(
    bid: str,
    name: str,
    weights: dict[str, float],
    pref: list[str],
    ok: list[str],
    sands: list[str],
    goblet: list[str],
    circlet: list[str],
) -> dict:
    return {
        "id": bid,
        "name_ja": name,
        "weights": weights,
        "sets_preferred": pref,
        "sets_ok": ok,
        "main_sands": sands,
        "main_goblet": goblet,
        "main_circlet": circlet,
    }


def build_rows(scale: str, element: str, preferred: list[str] | None = None) -> list[dict]:
    pref = list(preferred) if preferred else list(DEFAULT_PREF.get(element, ["gladiator"]))
    if scale == "hp":
        return [
            _row(
                "hp",
                "HP火力",
                CRIT_HP,
                pref,
                ["gladiator", "tenacity"],
                ["hp_pct", "er"],
                [element, "hp_pct"],
                ["crit_rate", "crit_dmg", "hp_pct"],
            )
        ]
    if scale == "def":
        return [
            _row(
                "def",
                "防御",
                CRIT_DEF,
                ["husk", "archaic", "cinder"],
                ["noblesse", "gladiator"],
                ["def_pct", "er"],
                ["geo", "def_pct"],
                ["crit_rate", "crit_dmg", "def_pct"],
            )
        ]
    if scale == "em":
        return [
            _row(
                "em",
                "熟知",
                CRIT_EM,
                ["viridescent", "gilded", "instructor"],
                ["wanderer"],
                ["em", "er", "atk_pct"],
                ["em", element],
                ["em", "crit_rate", "crit_dmg"],
            )
        ]
    if scale == "er":
        return [
            _row(
                "support",
                "サポート",
                ER_CRIT,
                ["emblem", "noblesse"],
                pref,
                ["er", "atk_pct"],
                [element, "atk_pct"],
                ["crit_rate", "crit_dmg", "er"],
            )
        ]
    goblet = [element, "atk_pct"]
    return [
        _row(
            "dps",
            "火力",
            CRIT_ATK,
            pref,
            ["gladiator", "wanderer"],
            ["atk_pct"],
            goblet,
            ["crit_rate", "crit_dmg"],
        )
    ]
