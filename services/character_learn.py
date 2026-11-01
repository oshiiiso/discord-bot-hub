"""公開図鑑から、まだ表に無いキャラ・セットを覚える。"""

from __future__ import annotations

import asyncio
import re
import time

import aiohttp

from games.genshin import GenshinGame
from games.genshin.catalog import character_by_enka_key, upsert_learned, upsert_set, valid_set_id
from logging_config import get_logger

logger = get_logger(__name__)

YATTA_AVATAR_URL = "https://gi.yatta.moe/api/v2/jp/avatar"
YATTA_RELIQUARY_URL = "https://gi.yatta.moe/api/v2/jp/reliquary"
YATTA_WEAPON_URL = "https://gi.yatta.moe/api/v2/jp/weapon"
YATTA_GUIDE_URL = "https://gi.yatta.moe/api/v2/static/advanced/avatarGuides/{id}"
_INDEX_TTL = 6 * 60 * 60
_SKIP_IDS = {"10000005", "10000007"}
_GUIDE_CONCURRENCY = 4
_PREF_MIN_SHARE = 0.1
_ELEM = {
    "Fire": "pyro",
    "Water": "hydro",
    "Ice": "cryo",
    "Electric": "electro",
    "Wind": "anemo",
    "Rock": "geo",
    "Grass": "dendro",
}

_index: dict[str, dict] | None = None
_index_expire = 0.0
_relics: dict[str, dict] | None = None
_relics_expire = 0.0
_weapons: dict[str, dict] | None = None
_weapons_expire = 0.0
_guides: dict[str, dict] = {}
_guides_expire = 0.0


def scale_from_special(prop: str) -> str:
    """突破ステから、点数の目安を決める。"""
    if prop in {"FIGHT_PROP_HP_PERCENT", "FIGHT_PROP_HP"}:
        return "hp"
    if prop in {"FIGHT_PROP_DEFENSE_PERCENT", "FIGHT_PROP_DEFENSE"}:
        return "def"
    if prop == "FIGHT_PROP_ELEMENT_MASTERY":
        return "em"
    if prop == "FIGHT_PROP_CHARGE_EFFICIENCY":
        return "er"
    return "atk"


def set_id_from_route(route: str) -> str:
    """英語名からセット ID を作る。"""
    slug = re.sub(r"[^a-z0-9]+", "_", route.lower()).strip("_")
    return slug if valid_set_id(slug) else ""


def _name_id(item: dict) -> str:
    route = str(item.get("route") or "")
    compact = route.replace("_", "")
    if compact.isascii() and compact.isalnum() and route[:1].isalpha():
        return route
    icon = str(item.get("icon") or "")
    if icon.startswith("UI_AvatarIcon_"):
        return icon.removeprefix("UI_AvatarIcon_")
    return ""


def _usable_id(enka_id: str) -> bool:
    if enka_id in _SKIP_IDS:
        return False
    try:
        numeric = int(enka_id)
    except ValueError:
        return False
    return 10000000 <= numeric < 10000900


def _items_from_payload(payload: object) -> dict[str, dict]:
    raw = ((payload.get("data") or {}).get("items") or {}) if isinstance(payload, dict) else {}
    return {str(key): value for key, value in dict(raw).items() if isinstance(value, dict)}


def row_from_item(item: dict) -> dict | None:
    """図鑑の1件を extras と同じ形にする。足りなければ None。"""
    enka_id = str(item.get("id") or "")
    if not _usable_id(enka_id):
        return None
    name_ja = str(item.get("name") or "").strip()
    element = _ELEM.get(str(item.get("element") or ""), "")
    name_id = _name_id(item)
    if not name_ja or not element or not name_id:
        return None
    aliases = [name_id]
    if name_ja not in aliases:
        aliases.append(name_ja)
    return {
        "enka_id": enka_id,
        "name_ja": name_ja,
        "element": element,
        "scale": scale_from_special(str(item.get("specialProp") or "")),
        "aliases": aliases,
    }


def map_reliquary_to_set_id(reliquary_id: str, relics: dict[str, dict]) -> str | None:
    """図鑑の聖遺物番号を、Bot のセット ID にする。"""
    item = relics.get(str(reliquary_id)) or {}
    name_ja = str(item.get("name") or "").strip()
    if not name_ja:
        return None
    return GenshinGame().find_set(name_ja)


def preferred_set_ids(guide: dict, relics: dict[str, dict]) -> list[str]:
    """使用率の高い4セットを定番にする。"""
    rows = ((guide.get("azaData") or {}).get("bestReliquaryList") or [])
    found: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        set_list = row.get("setList") or {}
        if not isinstance(set_list, dict) or len(set_list) != 1:
            continue
        raw_id, pieces = next(iter(set_list.items()))
        try:
            piece_count = int(pieces)
            share = float(row.get("value") or 0)
        except (TypeError, ValueError):
            continue
        if piece_count != 4:
            continue
        if found and share < _PREF_MIN_SHARE:
            continue
        set_id = map_reliquary_to_set_id(str(raw_id), relics)
        if set_id and set_id not in found:
            found.append(set_id)
        if len(found) >= 3:
            break
    return found


def _usable_weapon(weapon_id: str, weapons: dict[str, dict]) -> dict | None:
    item = weapons.get(str(weapon_id))
    if not isinstance(item, dict) or item.get("isWeaponSkin"):
        return None
    try:
        rank = int(item.get("rank") or 0)
    except (TypeError, ValueError):
        return None
    if rank < 3:
        return None
    return item


def _guide_best_weapon_ids(guide: dict) -> list[str]:
    """ガイドの Best Weapon に並んだ順。持ち武器が先頭の ★5 に来やすい。"""
    builds = ((guide.get("gwData") or {}).get("builds") or [])
    if not isinstance(builds, list):
        return []
    for build in builds:
        if not isinstance(build, dict):
            continue
        for info in build.get("info") or []:
            if not isinstance(info, dict):
                continue
            if "Best Weapon" not in str(info.get("name") or ""):
                continue
            weapon_list = info.get("weaponList") or {}
            if isinstance(weapon_list, dict):
                return [str(key) for key in weapon_list]
    return []


def _weapon_share_rows(guide: dict) -> list[tuple[str, float]]:
    raw = ((guide.get("azaData") or {}).get("bestWeaponList") or {})
    if not isinstance(raw, dict):
        return []
    rows: list[tuple[str, float]] = []
    for key, value in raw.items():
        weapon_id = str(key)
        share = 0.0
        if isinstance(value, dict):
            weapon_id = str(value.get("id") or key)
            try:
                share = float(value.get("value") or 0)
            except (TypeError, ValueError):
                share = 0.0
        else:
            try:
                share = float(value)
            except (TypeError, ValueError):
                continue
        rows.append((weapon_id, share))
    return rows


def preferred_weapon_item(guide: dict, weapons: dict[str, dict]) -> dict | None:
    """持ち武器（ガイド先頭の ★5）。無ければ使用率の高い ★5、それも無ければ次点。"""
    listed = [item for item in (_usable_weapon(wid, weapons) for wid in _guide_best_weapon_ids(guide)) if item]
    fives = [item for item in listed if int(item.get("rank") or 0) >= 5]
    if fives:
        return fives[0]
    if listed:
        return listed[0]
    ranked: list[tuple[float, int, dict]] = []
    for weapon_id, share in _weapon_share_rows(guide):
        item = _usable_weapon(weapon_id, weapons)
        if item is None:
            continue
        ranked.append((share, int(item.get("rank") or 0), item))
    if not ranked:
        return None
    fives_usage = [row for row in ranked if row[1] >= 5]
    pool = fives_usage or ranked
    pool.sort(key=lambda row: row[0], reverse=True)
    return pool[0][2]


def apply_sets(relics: dict[str, dict]) -> list[str]:
    """表に無い聖遺物セットを覚える。"""
    learned: list[str] = []
    game = GenshinGame()
    for item in relics.values():
        name_ja = str(item.get("name") or "").strip()
        if not name_ja or game.find_set(name_ja):
            continue
        set_id = set_id_from_route(str(item.get("route") or ""))
        if not set_id:
            continue
        upsert_set(set_id=set_id, name_ja=name_ja, aliases=[str(item.get("route") or "")])
        learned.append(name_ja)
    return learned


def apply_index(items: dict, *, only_ids: set[str] | None = None) -> list[str]:
    """表に無い番号だけ覚える。すでに extras / 本表にある子は触らない。"""
    learned: list[str] = []
    for row in pending_rows(items, only_ids=only_ids):
        info = upsert_learned(
            name_ja=row["name_ja"],
            enka_id=row["enka_id"],
            element=row["element"],
            scale=row["scale"],
            aliases=row["aliases"],
            sets_preferred=row.get("sets_preferred") or [],
        )
        learned.append(info.name_ja)
    return learned


def pending_rows(items: dict, *, only_ids: set[str] | None = None) -> list[dict]:
    rows: list[dict] = []
    for key, item in items.items():
        if not isinstance(item, dict):
            continue
        enka_id = str(item.get("id") or key)
        if only_ids is not None and enka_id not in only_ids:
            continue
        if character_by_enka_key(enka_id) is not None:
            continue
        row = row_from_item(item)
        if row is not None:
            rows.append(row)
    return rows


async def fetch_index(session: aiohttp.ClientSession, *, force: bool = False) -> dict[str, dict]:
    """キャラ図鑑の一覧。TTL のあいだメモリに置く。"""
    global _index, _index_expire
    now = time.time()
    if not force and _index is not None and now < _index_expire:
        return _index
    async with session.get(YATTA_AVATAR_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        resp.raise_for_status()
        payload = await resp.json()
    items = _items_from_payload(payload)
    _index = items
    _index_expire = now + _INDEX_TTL
    return items


async def fetch_reliquary(session: aiohttp.ClientSession, *, force: bool = False) -> dict[str, dict]:
    """聖遺物セットの一覧。"""
    global _relics, _relics_expire
    now = time.time()
    if not force and _relics is not None and now < _relics_expire:
        return _relics
    async with session.get(YATTA_RELIQUARY_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        resp.raise_for_status()
        payload = await resp.json()
    items = _items_from_payload(payload)
    _relics = items
    _relics_expire = now + _INDEX_TTL
    return items


async def fetch_weapons(session: aiohttp.ClientSession, *, force: bool = False) -> dict[str, dict]:
    """武器図鑑。名前とアイコンを引く。"""
    global _weapons, _weapons_expire
    now = time.time()
    if not force and _weapons is not None and now < _weapons_expire:
        return _weapons
    async with session.get(YATTA_WEAPON_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        resp.raise_for_status()
        payload = await resp.json()
    items = _items_from_payload(payload)
    _weapons = items
    _weapons_expire = now + _INDEX_TTL
    return items


def _reset_guide_cache_if_stale(now: float, *, force: bool = False) -> None:
    global _guides, _guides_expire
    if force or now >= _guides_expire:
        _guides = {}
        _guides_expire = now + _INDEX_TTL


async def fetch_guide(session: aiohttp.ClientSession, enka_id: str, *, force: bool = False) -> dict:
    """使用率付きのビルド目安。無いときは空。"""
    _reset_guide_cache_if_stale(time.time())
    if not force and enka_id in _guides:
        return _guides[enka_id]
    url = YATTA_GUIDE_URL.format(id=enka_id)
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status == 404:
            _guides[enka_id] = {}
            return {}
        resp.raise_for_status()
        payload = await resp.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    parsed = data if isinstance(data, dict) else {}
    _guides[enka_id] = parsed
    return parsed


async def fetch_guides(session: aiohttp.ClientSession, enka_ids: list[str], *, force: bool = False) -> dict[str, dict]:
    """複数キャラのガイドをまとめて取る。"""
    now = time.time()
    _reset_guide_cache_if_stale(now, force=force)
    wanted = [str(eid) for eid in enka_ids if eid]
    missing = [eid for eid in dict.fromkeys(wanted) if force or eid not in _guides]
    sem = asyncio.Semaphore(_GUIDE_CONCURRENCY)

    async def one(eid: str) -> None:
        async with sem:
            try:
                await fetch_guide(session, eid, force=force)
            except Exception:
                logger.warning("ビルド目安の取得に失敗しました enka_id=%s", eid)
                _guides[eid] = {}

    if missing:
        await asyncio.gather(*(one(eid) for eid in missing))
    return {eid: _guides.get(eid) or {} for eid in wanted}


async def _fill_preferred(session: aiohttp.ClientSession, rows: list[dict], relics: dict[str, dict]) -> None:
    sem = asyncio.Semaphore(_GUIDE_CONCURRENCY)

    async def one(row: dict) -> None:
        async with sem:
            try:
                guide = await fetch_guide(session, row["enka_id"])
            except Exception:
                logger.warning("定番セットの取得に失敗しました enka_id=%s", row["enka_id"])
                return
            row["sets_preferred"] = preferred_set_ids(guide, relics)

    if rows:
        await asyncio.gather(*(one(row) for row in rows))


async def learn_new_characters(session: aiohttp.ClientSession, *, force: bool = False) -> tuple[list[str], list[str]]:
    """図鑑全体から、まだ表に無い子とセットを覚える。"""
    items = await fetch_index(session, force=force)
    relics = await fetch_reliquary(session, force=force)
    set_names = apply_sets(relics)
    rows = pending_rows(items)
    await _fill_preferred(session, rows, relics)
    return _upsert_rows(rows), set_names


def _upsert_rows(rows: list[dict]) -> list[str]:
    learned: list[str] = []
    for row in rows:
        info = upsert_learned(
            name_ja=row["name_ja"],
            enka_id=row["enka_id"],
            element=row["element"],
            scale=row["scale"],
            aliases=row["aliases"],
            sets_preferred=row.get("sets_preferred") or [],
        )
        learned.append(info.name_ja)
    return learned


async def learn_ids(session: aiohttp.ClientSession, avatar_ids: list[str]) -> list[str]:
    """UID で出てきた未知の番号だけ覚える。"""
    wanted = {aid for aid in avatar_ids if _usable_id(aid) and character_by_enka_key(aid) is None}
    if not wanted:
        return []
    items = await fetch_index(session)
    missing = {aid for aid in wanted if aid not in items}
    if missing:
        items = await fetch_index(session, force=True)
    relics = await fetch_reliquary(session)
    apply_sets(relics)
    rows = pending_rows(items, only_ids=wanted)
    await _fill_preferred(session, rows, relics)
    return _upsert_rows(rows)
