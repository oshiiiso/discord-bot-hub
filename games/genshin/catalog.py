"""原神のキャラ・セット JSON 読み込み。"""

from __future__ import annotations

import json
import re
from functools import lru_cache

from config import DATA_DIR, STORAGE_DIR
from games.base import CharacterBuild, CharacterInfo
from games.genshin.defaults import SCALES, build_rows

_GENSHIN_DATA = DATA_DIR / "genshin"
_EXTRAS_PATH = _GENSHIN_DATA / "extras.json"
_LEARNED_PATH = STORAGE_DIR / "learned_characters.json"
_SET_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _load_json(name: str) -> object:
    path = _GENSHIN_DATA / name
    return json.loads(path.read_text(encoding="utf-8"))


def _builds_from_rows(rows: list[dict]) -> list[CharacterBuild]:
    return [
        CharacterBuild(
            id=str(b["id"]),
            name_ja=str(b["name_ja"]),
            weights={k: float(v) for k, v in dict(b.get("weights") or {}).items()},
            sets_preferred=list(b.get("sets_preferred") or []),
            sets_ok=list(b.get("sets_ok") or []),
            main_sands=list(b.get("main_sands") or []),
            main_goblet=list(b.get("main_goblet") or []),
            main_circlet=list(b.get("main_circlet") or []),
        )
        for b in rows
    ]


def _character_from_row(row: dict) -> CharacterInfo:
    return CharacterInfo(
        id=str(row["id"]),
        name_ja=str(row["name_ja"]),
        aliases=list(row.get("aliases") or []),
        element=str(row["element"]),
        builds=_builds_from_rows(list(row.get("builds") or [])),
        enka_keys=[str(x) for x in row.get("enka_keys") or []],
    )


def load_extras() -> dict:
    if not _EXTRAS_PATH.exists():
        return {"characters": [], "sets": []}
    raw = json.loads(_EXTRAS_PATH.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"characters": [], "sets": []}
    characters = raw.get("characters") or []
    sets = raw.get("sets") or []
    return {
        "characters": list(characters) if isinstance(characters, list) else [],
        "sets": list(sets) if isinstance(sets, list) else [],
    }


def _save_extras(data: dict) -> None:
    _EXTRAS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _EXTRAS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    refresh_catalog()


def _id_from_aliases(enka_id: str, aliases: list[str]) -> str:
    for alias in aliases:
        compact = alias.replace("_", "")
        if compact.isascii() and compact.isalnum() and alias[:1].isalpha():
            return alias.lower()
    return f"c{enka_id}"


def parse_aliases(raw: str) -> list[str]:
    parts = [p.strip() for p in raw.replace("、", ",").split(",")]
    return [p for p in parts if p]


def _character_rows(path, *, fallback: dict | None = None) -> list[dict]:
    if not path.exists():
        return list((fallback or {}).get("characters") or [])
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return []
    characters = raw.get("characters") or []
    return list(characters) if isinstance(characters, list) else []


def extra_character_to_info(row: dict) -> CharacterInfo:
    enka_id = str(row["enka_id"])
    aliases = [str(a) for a in row.get("aliases") or [] if str(a).strip()]
    cid = str(row.get("id") or "") or _id_from_aliases(enka_id, aliases)
    scale = str(row.get("scale") or "atk")
    if scale not in SCALES:
        scale = "atk"
    element = str(row.get("element") or "")
    preferred = [str(s) for s in row.get("sets_preferred") or [] if str(s).strip()]
    return CharacterInfo(
        id=cid,
        name_ja=str(row["name_ja"]),
        aliases=aliases,
        element=element,
        builds=_builds_from_rows(build_rows(scale, element, preferred=preferred or None)),
        enka_keys=[enka_id],
    )


def upsert_character(
    *,
    name_ja: str,
    enka_id: str,
    element: str,
    scale: str,
    aliases: list[str],
) -> CharacterInfo:
    data = load_extras()
    row = {
        "id": _id_from_aliases(enka_id, aliases),
        "enka_id": enka_id,
        "name_ja": name_ja,
        "element": element,
        "scale": scale,
        "aliases": aliases,
    }
    characters = [c for c in data["characters"] if str(c.get("enka_id")) != enka_id]
    characters.append(row)
    data["characters"] = characters
    _save_extras(data)
    return extra_character_to_info(row)


def load_learned() -> list[dict]:
    return [row for row in _character_rows(_LEARNED_PATH) if row.get("enka_id")]


def upsert_learned(
    *,
    name_ja: str,
    enka_id: str,
    element: str,
    scale: str,
    aliases: list[str],
    sets_preferred: list[str] | None = None,
) -> CharacterInfo:
    """図鑑から覚えた子。/addchar の extras より下、本表より上。"""
    rows = [c for c in load_learned() if str(c.get("enka_id")) != enka_id]
    row = {
        "id": _id_from_aliases(enka_id, aliases),
        "enka_id": enka_id,
        "name_ja": name_ja,
        "element": element,
        "scale": scale,
        "aliases": aliases,
        "sets_preferred": list(sets_preferred or []),
    }
    rows.append(row)
    _LEARNED_PATH.parent.mkdir(parents=True, exist_ok=True)
    _LEARNED_PATH.write_text(
        json.dumps({"characters": rows}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    refresh_catalog()
    return extra_character_to_info(row)


def upsert_set(*, set_id: str, name_ja: str, aliases: list[str]) -> dict:
    data = load_extras()
    row = {"id": set_id, "name_ja": name_ja, "aliases": aliases}
    sets = [s for s in data["sets"] if str(s.get("id")) != set_id]
    sets.append(row)
    data["sets"] = sets
    _save_extras(data)
    return row


def valid_set_id(set_id: str) -> bool:
    return bool(_SET_ID_RE.match(set_id))


@lru_cache(maxsize=1)
def load_relic_icons() -> dict[str, dict]:
    """UI_RelicIcon_番号 → セット名。"""
    raw = _load_json("relic_icons.json")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, dict] = {}
    for key, row in raw.items():
        if not isinstance(row, dict):
            continue
        out[str(key)] = {
            "set_id": str(row.get("set_id") or ""),
            "name_ja": str(row.get("name_ja") or ""),
        }
    return out


def set_from_icon(icon: str | None) -> dict | None:
    """聖遺物アイコン名からセット行を返す。"""
    if not icon:
        return None
    text = icon.replace("UI_RelicIcon_", "", 1)
    num = text.split("_", 1)[0]
    row = load_relic_icons().get(num)
    if not row or not row.get("name_ja"):
        return None
    return row


_SLOT_ICON_INDEX = {
    "flower": "1",
    "feather": "2",
    "sands": "3",
    "goblet": "4",
    "circlet": "5",
}


def relic_icon_name(set_id: str | None, slot: str | None) -> str:
    """セット ID と部位から UI_RelicIcon_番号_部位 を返す。"""
    if not set_id or not slot:
        return ""
    index = _SLOT_ICON_INDEX.get(slot)
    if not index:
        return ""
    for num, row in load_relic_icons().items():
        if row.get("set_id") == set_id:
            return f"UI_RelicIcon_{num}_{index}"
    return ""


@lru_cache(maxsize=1)
def load_sets() -> dict[str, dict]:
    """artifact_sets.json を id キーで返す。extras のセットを重ねる。"""
    raw = _load_json("artifact_sets.json")
    if not isinstance(raw, list):
        raise RuntimeError("artifact_sets.json は配列である必要があります")
    sets: dict[str, dict] = {}
    for row in raw:
        set_id = str(row["id"])
        sets[set_id] = row
    for row in load_extras()["sets"]:
        set_id = str(row.get("id") or "")
        if not set_id:
            continue
        sets[set_id] = {
            "id": set_id,
            "name_ja": str(row.get("name_ja") or set_id),
            "aliases": list(row.get("aliases") or []),
        }
    return sets


def _overlay(base: list[CharacterInfo], overlay: list[CharacterInfo]) -> list[CharacterInfo]:
    if not overlay:
        return base
    keys = {key for character in overlay for key in character.enka_keys}
    kept = [character for character in base if not keys.intersection(character.enka_keys)]
    return kept + overlay


@lru_cache(maxsize=1)
def load_characters() -> list[CharacterInfo]:
    """characters.json を CharacterInfo のリストにする。図鑑の覚えと extras を重ねる。"""
    raw = _load_json("characters.json")
    if not isinstance(raw, list):
        raise RuntimeError("characters.json は配列である必要があります")
    characters = [_character_from_row(row) for row in raw]
    learned = [extra_character_to_info(row) for row in load_learned()]
    extras = [extra_character_to_info(row) for row in load_extras()["characters"] if row.get("enka_id")]
    return _overlay(_overlay(characters, learned), extras)


def character_by_enka_key(key: str) -> CharacterInfo | None:
    """Enka の avatarId または avatarId-skillDepotId で探す。"""
    for character in load_characters():
        if key in character.enka_keys:
            return character
    return None


def refresh_catalog() -> None:
    """characters.json / artifact_sets.json のメモリキャッシュを捨てる。"""
    load_sets.cache_clear()
    load_relic_icons.cache_clear()
    load_characters.cache_clear()
