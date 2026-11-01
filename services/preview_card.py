"""UID なしで、表にあるキャラのカード見本を組む。"""

from __future__ import annotations

import aiohttp

from games.base import CharacterBuild, CharacterInfo, ParsedPiece, ParsedStat
from games.genshin.catalog import load_characters, load_sets, relic_icon_name
from games.genshin.stats import ENKA_PROP_TO_KEY, GENERIC_WEIGHTS, PERCENT_KEYS
from logging_config import get_logger
from services.character_check import avatar_ids
from services.character_learn import fetch_guide, fetch_guides, fetch_weapons, preferred_weapon_item
from services.enka_client import EnkaAvatar, EnkaClient, EnkaWeapon

logger = get_logger(__name__)

_SLOTS = ("flower", "feather", "sands", "goblet", "circlet")
_ELEM_KEYS = ("pyro", "hydro", "cryo", "electro", "anemo", "geo", "dendro")
_MAIN_VALUES: dict[str, float] = {
    "hp_flat": 4780,
    "atk_flat": 311,
    "def_flat": 185,
    "hp_pct": 46.6,
    "atk_pct": 46.6,
    "def_pct": 46.6,
    "em": 187,
    "er": 51.8,
    "crit_rate": 31.1,
    "crit_dmg": 62.2,
    "healing": 35.9,
    "physical": 58.3,
    **{key: 46.6 for key in _ELEM_KEYS},
}
_SUB_ROLLS = (3, 2, 2, 2)
_SUB_VALUES: dict[str, dict[int, float]] = {
    "crit_rate": {1: 3.9, 2: 7.0, 3: 10.1, 4: 13.2},
    "crit_dmg": {1: 7.8, 2: 14.0, 3: 19.4, 4: 25.6},
    "atk_pct": {1: 4.7, 2: 9.3, 3: 14.0, 4: 18.7},
    "hp_pct": {1: 4.7, 2: 9.3, 3: 14.0, 4: 18.7},
    "def_pct": {1: 5.8, 2: 11.7, 3: 17.5, 4: 23.3},
    "er": {1: 5.2, 2: 9.1, 3: 13.0, 4: 16.8},
    "em": {1: 19, 2: 37, 3: 56, 4: 75},
    "atk_flat": {1: 16, 2: 31, 3: 47, 4: 63},
    "hp_flat": {1: 239, 2: 478, 3: 717, 4: 956},
    "def_flat": {1: 19, 2: 37, 3: 56, 4: 75},
}
_SUB_AT_90: dict[int, dict[str, float]] = {
    5: {
        "crit_rate": 33.1,
        "crit_dmg": 66.2,
        "atk_pct": 49.6,
        "hp_pct": 49.6,
        "def_pct": 82.7,
        "em": 265.0,
        "er": 55.1,
        "physical": 41.3,
    },
    4: {
        "crit_rate": 27.6,
        "crit_dmg": 36.8,
        "atk_pct": 41.3,
        "hp_pct": 41.3,
        "def_pct": 69.0,
        "em": 165.0,
        "er": 45.9,
        "physical": 34.5,
    },
}
_BASE_ATK = {5: 608.0, 4: 510.0, 3: 354.0}
_WeaponSpec = tuple[str, str, float, str, float]
_WEAPONS_BY_SCALE: dict[str, _WeaponSpec] = {
    "atk": ("和璞鳶", "UI_EquipIcon_Pole_Morax", 674, "crit_rate", 22.1),
    "hp": ("護摩の杖", "UI_EquipIcon_Pole_Homa", 608, "crit_dmg", 66.2),
    "def": ("赤角の石得物", "UI_EquipIcon_Claymore_Itadorimaru", 542, "crit_dmg", 88.2),
    "em": ("千夜に浮かぶ夢", "UI_EquipIcon_Catalyst_Ayus", 542, "em", 265.0),
    "er": ("草薙の稲光", "UI_EquipIcon_Pole_Narukami", 608, "er", 55.1),
}
_WEAPONS_BY_TYPE: dict[str, dict[str, _WeaponSpec]] = {
    "WEAPON_SWORD_ONE_HAND": {
        "atk": ("霧切の廻光", "UI_EquipIcon_Sword_Narukami", 674, "crit_dmg", 44.1),
        "hp": ("磐岩結緑", "UI_EquipIcon_Sword_Morax", 542, "hp_pct", 44.1),
        "def": ("静水の誓い", "UI_EquipIcon_Sword_Psalmus", 542, "def_pct", 82.7),
        "em": ("蒼古なる自由への誓い", "UI_EquipIcon_Sword_Widsith", 608, "em", 198.0),
        "er": ("西風剣", "UI_EquipIcon_Sword_Zephyrus", 454, "er", 61.3),
    },
    "WEAPON_CLAYMORE": {
        "atk": ("狼の末裔", "UI_EquipIcon_Claymore_Wolfmound", 608, "atk_pct", 49.6),
        "hp": ("狼の末裔", "UI_EquipIcon_Claymore_Wolfmound", 608, "atk_pct", 49.6),
        "def": ("赤角の石得物", "UI_EquipIcon_Claymore_Itadorimaru", 542, "crit_dmg", 88.2),
        "em": ("雨裁", "UI_EquipIcon_Claymore_Perdue", 510, "em", 165.0),
        "er": ("西風大剣", "UI_EquipIcon_Claymore_Zephyrus", 454, "er", 61.3),
    },
    "WEAPON_POLE": {
        "atk": ("和璞鳶", "UI_EquipIcon_Pole_Morax", 674, "crit_rate", 22.1),
        "hp": ("護摩の杖", "UI_EquipIcon_Pole_Homa", 608, "crit_dmg", 66.2),
        "def": ("護摩の杖", "UI_EquipIcon_Pole_Homa", 608, "crit_dmg", 66.2),
        "em": ("和璞鳶", "UI_EquipIcon_Pole_Morax", 674, "crit_rate", 22.1),
        "er": ("草薙の稲光", "UI_EquipIcon_Pole_Narukami", 608, "er", 55.1),
    },
    "WEAPON_BOW": {
        "atk": ("飛雷の鳴弦", "UI_EquipIcon_Bow_Narukami", 608, "crit_dmg", 66.2),
        "hp": ("若水", "UI_EquipIcon_Bow_Maria", 542, "crit_dmg", 88.2),
        "def": ("飛雷の鳴弦", "UI_EquipIcon_Bow_Narukami", 608, "crit_dmg", 66.2),
        "em": ("狩人の道", "UI_EquipIcon_Bow_Ayus", 542, "crit_rate", 44.1),
        "er": ("終焉を嘆く詩", "UI_EquipIcon_Bow_Worldbane", 608, "er", 55.1),
    },
    "WEAPON_CATALYST": {
        "atk": ("四風原典", "UI_EquipIcon_Catalyst_Fourwinds", 608, "crit_rate", 33.1),
        "hp": ("不滅月華", "UI_EquipIcon_Catalyst_Kgo", 608, "hp_pct", 49.6),
        "def": ("四風原典", "UI_EquipIcon_Catalyst_Fourwinds", 608, "crit_rate", 33.1),
        "em": ("千夜に浮かぶ夢", "UI_EquipIcon_Catalyst_Ayus", 542, "em", 265.0),
        "er": ("祭礼の断片", "UI_EquipIcon_Catalyst_Favonius", 454, "er", 61.3),
    },
}


def _build_scale(build: CharacterBuild) -> str:
    if build.id in GENERIC_WEIGHTS:
        return build.id
    ranked = sorted(
        ((key, value) for key, value in build.weights.items() if key not in ("crit_rate", "crit_dmg")),
        key=lambda item: item[1],
        reverse=True,
    )
    if not ranked:
        return "atk"
    key = ranked[0][0]
    return {
        "atk_pct": "atk",
        "atk_flat": "atk",
        "hp_pct": "hp",
        "hp_flat": "hp",
        "def_pct": "def",
        "def_flat": "def",
    }.get(key, key if key in ("em", "er") else "atk")


def _stat(key: str, value: float, rolls: int = 0) -> ParsedStat:
    return ParsedStat(key=key, value=value, is_percent=key in PERCENT_KEYS, rolls=rolls)


def _dummy_subs(build: CharacterBuild) -> list[ParsedStat]:
    """初期4本 + 伸び5回（表示の合計が ×5）。"""
    keys: list[str] = []
    for key, _weight in sorted(build.weights.items(), key=lambda item: item[1], reverse=True):
        if key not in keys:
            keys.append(key)
    for extra in ("crit_rate", "crit_dmg", "atk_pct", "er", "em", "hp_pct"):
        if extra not in keys:
            keys.append(extra)
        if len(keys) >= 4:
            break
    subs: list[ParsedStat] = []
    for key, rolls in zip(keys[:4], _SUB_ROLLS):
        by_rolls = _SUB_VALUES.get(key) or {1: 5.8, 2: 9.3, 3: 14.0, 4: 18.7}
        subs.append(_stat(key, by_rolls.get(rolls, 5.8), rolls))
    return subs


def _set_for_build(build: CharacterBuild) -> tuple[str, str]:
    catalog = load_sets()
    for set_id in list(build.sets_preferred or []) + ["gladiator"]:
        row = catalog.get(set_id)
        if row:
            return set_id, str(row.get("name_ja") or set_id)
    return "gladiator", "剣闘士のフィナーレ"


def _slot_main(slot: str, build: CharacterBuild) -> ParsedStat:
    if slot == "flower":
        key = "hp_flat"
    elif slot == "feather":
        key = "atk_flat"
    elif slot == "sands":
        key = (build.main_sands or ["atk_pct"])[0]
    elif slot == "goblet":
        key = (build.main_goblet or ["atk_pct"])[0]
    else:
        key = (build.main_circlet or ["crit_rate"])[0]
    return _stat(key, _MAIN_VALUES.get(key, 46.6))


def weapon_from_yatta(item: dict) -> EnkaWeapon:
    """図鑑の1件を、カードに載せる武器にする。"""
    try:
        rank = int(item.get("rank") or 5)
    except (TypeError, ValueError):
        rank = 5
    rarity = 5 if rank >= 5 else 4 if rank >= 4 else 3
    sub_key = ENKA_PROP_TO_KEY.get(str(item.get("specialProp") or ""), "")
    table = _SUB_AT_90.get(rarity) or _SUB_AT_90[5]
    return EnkaWeapon(
        name_ja=str(item.get("name") or "").strip(),
        level=90,
        refine=1,
        icon=str(item.get("icon") or ""),
        rarity=rarity,
        base_atk=_BASE_ATK.get(rarity, 608.0),
        sub_key=sub_key,
        sub_value=table.get(sub_key, 0.0),
    )


def dummy_weapon(build: CharacterBuild, weapon_type: str = "") -> EnkaWeapon:
    """ガイドが無いときの仮置き。武器種と点数の出し方で実在武器を当てる。"""
    scale = _build_scale(build)
    spec = (_WEAPONS_BY_TYPE.get(weapon_type) or {}).get(scale)
    if spec is None:
        spec = _WEAPONS_BY_SCALE.get(scale) or _WEAPONS_BY_SCALE["atk"]
    name_ja, icon, base_atk, sub_key, sub_value = spec
    return EnkaWeapon(
        name_ja=name_ja,
        level=90,
        refine=1,
        icon=icon,
        rarity=5,
        base_atk=base_atk,
        sub_key=sub_key,
        sub_value=sub_value,
    )


def preview_targets() -> list[CharacterInfo]:
    """見本用。旅人は属性が違うだけで立ち絵が同じなので1人だけ。"""
    picked: list[CharacterInfo] = []
    traveler: CharacterInfo | None = None
    for row in load_characters():
        if not row.enka_keys or not row.builds:
            continue
        if row.id.startswith("traveler"):
            if traveler is None or row.id == "traveler_anemo":
                traveler = row
            continue
        picked.append(row)
    if traveler is not None:
        picked.append(traveler)
    return picked


def _fallback_weapon(client: EnkaClient, character: CharacterInfo) -> EnkaWeapon | None:
    if not character.enka_keys or not character.builds:
        return None
    avatar_id, depot = avatar_ids(character.enka_keys[0])
    weapon_type = str(client._store_info(avatar_id, depot).get("WeaponType") or "")
    return dummy_weapon(character.builds[0], weapon_type)


async def dummy_weapons_for(
    session: aiohttp.ClientSession,
    client: EnkaClient,
    characters: list[CharacterInfo],
) -> dict[str, EnkaWeapon]:
    """持ち武器をまとめて取る。ガイドが無い子は仮置き。"""
    ids: list[str] = []
    for character in characters:
        if character.enka_keys:
            ids.append(str(avatar_ids(character.enka_keys[0])[0]))
    weapons: dict[str, dict] = {}
    guides: dict[str, dict] = {}
    try:
        weapons = await fetch_weapons(session)
        unique_ids = list(dict.fromkeys(ids))
        if len(unique_ids) == 1:
            guides = {unique_ids[0]: await fetch_guide(session, unique_ids[0])}
        elif unique_ids:
            guides = await fetch_guides(session, unique_ids)
    except Exception:
        logger.warning("持ち武器の図鑑取得に失敗しました")
    out: dict[str, EnkaWeapon] = {}
    for character in characters:
        fallback = _fallback_weapon(client, character)
        if fallback is None:
            continue
        enka_id = str(avatar_ids(character.enka_keys[0])[0])
        item = preferred_weapon_item(guides.get(enka_id) or {}, weapons)
        out[character.id] = weapon_from_yatta(item) if item else fallback
    return out


def dummy_avatar(
    client: EnkaClient,
    character: CharacterInfo,
    *,
    weapon: EnkaWeapon | None = None,
) -> EnkaAvatar | None:
    """立ち絵確認用の仮データ。定番セットと持ち武器。"""
    if not character.enka_keys:
        return None
    avatar_id, depot = avatar_ids(character.enka_keys[0])
    build = character.builds[0] if character.builds else None
    if build is None:
        return None
    set_id, set_name = _set_for_build(build)
    subs = _dummy_subs(build)
    pieces = [
        ParsedPiece(
            slot=slot,
            set_id=set_id,
            set_name_ja=set_name,
            main=_slot_main(slot, build),
            subs=list(subs),
            rarity=5,
            level=20,
            icon=relic_icon_name(set_id, slot) or None,
        )
        for slot in _SLOTS
    ]
    goblet_key = pieces[3].main.key if pieces[3].main else ""
    scale = _build_scale(build)
    name_id = client._name_id_for_avatar(avatar_id, depot, None)
    info = client._store_info(avatar_id, depot)
    weapon_type = str(info.get("WeaponType") or "")
    dummy_levels = {str(i): 8 for i in (info.get("SkillOrder") or [1, 2, 3])}
    skills = client._skills_for_avatar(info, dummy_levels, name_id)
    stats = {
        "hp": 38000 if scale == "hp" else 20000,
        "atk": 2500 if scale == "atk" else 1600,
        "def": 2500 if scale == "def" else 800,
        "em": 800 if scale == "em" else 120,
        "er": 220 if scale == "er" else 120,
        "crit_rate": 70,
        "crit_dmg": 150,
    }
    return EnkaAvatar(
        avatar_id=avatar_id,
        skill_depot_id=depot,
        name_ja=character.name_ja,
        icon=client._icon_for_avatar(avatar_id, depot, None),
        splash_icon=client._splash_for_avatar(avatar_id, depot, None),
        level=90,
        constellations=6,
        friendship=10,
        character=character,
        pieces=pieces,
        weapon=weapon or dummy_weapon(build, weapon_type),
        stats=stats,
        element=character.element,
        skills=skills,
        constellation_icons=client._const_icons(info, name_id),
        dmg_bonus_key=goblet_key if goblet_key in _ELEM_KEYS else "",
        dmg_bonus=46.6 if goblet_key in _ELEM_KEYS else 0.0,
    )
