"""Enka.Network から原神の紹介キャラを取る。"""

from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

import aiohttp

import messages as msg
from config import BASE_DIR, ENKA_ASSET_RETENTION_DAYS, ENKA_CACHE_SECONDS_FALLBACK, STORAGE_DIR
from games.base import CharacterInfo, ParsedPiece, ParsedStat
from games.genshin import GenshinGame
from games.genshin.catalog import load_sets, set_from_icon
from games.genshin.stats import ENKA_PROP_TO_KEY, PERCENT_KEYS, SLOT_FROM_ENKA, affix_stat_key
from logging_config import get_logger
from services.copy import t

logger = get_logger(__name__)

ENKA_UID_URL = "https://enka.network/api/uid/{uid}"
ENKA_UI_URL = "https://enka.network/ui/{icon}.png"
STORE_CHARACTERS = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/characters.json"
STORE_LOC = "https://raw.githubusercontent.com/EnkaNetwork/API-docs/master/store/loc.json"
USER_AGENT = "discord-bot-buildcard/0.1 (oshiiiso)"
_ICON_NAME_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _as_dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _as_list(value: object) -> list:
    return value if isinstance(value, list) else []


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value)))
    except (TypeError, ValueError):
        return default

_STORE_TTL = 24 * 60 * 60
_ASSET_CLEAN_INTERVAL = 24 * 60 * 60
_SIDE_ICON_MAP: dict[str, str] | None = None


def _local_side_icons() -> dict[str, str]:
    """リポジトリの enka_index から SideIcon を引く。store が空でも立ち絵名を組み立てる。"""
    global _SIDE_ICON_MAP
    if _SIDE_ICON_MAP is not None:
        return _SIDE_ICON_MAP
    mapping: dict[str, str] = {}
    path = BASE_DIR / "tools" / "enka_index.tsv"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) < 5:
                continue
            mapping[parts[0].strip()] = parts[4].strip()
    _SIDE_ICON_MAP = mapping
    return mapping


def cleanup_enka_assets(
    cache_dir: Path,
    retention_days: int,
    *,
    now: float | None = None,
) -> int:
    """最終利用から retention_days を過ぎた png と、0 バイトのファイルを消す。"""
    if retention_days <= 0 or not cache_dir.is_dir():
        return 0
    cutoff = (now if now is not None else time.time()) - retention_days * 24 * 60 * 60
    removed = 0
    for path in cache_dir.glob("*.png"):
        try:
            stat = path.stat()
            if stat.st_size == 0 or stat.st_mtime < cutoff:
                path.unlink()
                removed += 1
        except OSError as e:
            logger.warning("画像キャッシュの削除に失敗しました: %s (%s)", path, e)
    return removed


def _as_percent(value: float, *, energy: bool = False) -> float:
    """fightProp の割合を百分率にする。"""
    if energy:
        return value * 100.0 if value < 20 else value
    return value * 100.0 if value <= 10 else value


_DMG_PROPS = (
    (40, "pyro"),
    (41, "electro"),
    (42, "hydro"),
    (43, "dendro"),
    (44, "anemo"),
    (45, "geo"),
    (46, "cryo"),
    (30, "physical"),
)


def _best_dmg_bonus(fp) -> tuple[str, float]:
    """元素・物理ダメージバフのうち最大のものを返す。"""
    best_key = ""
    best_val = 0.0
    for prop_id, key in _DMG_PROPS:
        value = _as_percent(fp(prop_id))
        if value > best_val:
            best_key = key
            best_val = value
    return best_key, best_val


class EnkaError(RuntimeError):
    """Enka API の失敗。"""

    def __init__(self, code: str, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass
class EnkaWeapon:
    name_ja: str
    level: int
    refine: int
    icon: str
    rarity: int
    base_atk: float = 0.0
    sub_key: str = ""
    sub_value: float = 0.0


@dataclass
class EnkaAvatar:
    avatar_id: int
    skill_depot_id: int
    name_ja: str
    icon: str
    level: int
    constellations: int
    friendship: int
    character: CharacterInfo
    pieces: list[ParsedPiece]
    weapon: EnkaWeapon | None
    stats: dict[str, float] = field(default_factory=dict)
    element: str = ""
    splash_icon: str = ""
    skills: list[tuple[str, int]] = field(default_factory=list)
    constellation_icons: list[str] = field(default_factory=list)
    hp_base: float = 0.0
    atk_base: float = 0.0
    def_base: float = 0.0
    dmg_bonus_key: str = ""
    dmg_bonus: float = 0.0
    costume_id: int | None = None


@dataclass
class EnkaShowcase:
    uid: str
    nickname: str
    level: int
    avatars: list[EnkaAvatar]
    ttl: int


class EnkaClient:
    """UID 応答と store JSON をキャッシュする。"""

    def __init__(self) -> None:
        self._uid_cache: dict[str, tuple[float, EnkaShowcase]] = {}
        self._store: dict | None = None
        self._loc_ja: dict[str, str] | None = None
        self._store_expire = 0.0
        self._session: aiohttp.ClientSession | None = None
        self._asset_cleaned_at = 0.0
        self._missing_icons: set[str] = set()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers={"User-Agent": USER_AGENT})
        return self._session

    async def fetch_showcase(self, uid: str, *, force: bool = False) -> EnkaShowcase:
        """UID の紹介キャラを返す。ttl のあいだメモリキャッシュ。force で取り直す。"""
        now = time.monotonic()
        if not force:
            cached = self._uid_cache.get(uid)
            if cached and cached[0] > now:
                return cached[1]

        session = await self._http()
        url = ENKA_UID_URL.format(uid=uid)
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status == 404:
                    raise EnkaError("not_found", 404)
                if resp.status == 424:
                    raise EnkaError("private", 424)
                if resp.status == 429:
                    raise EnkaError("rate", 429)
                if resp.status >= 400:
                    raise EnkaError("error", resp.status)
                payload = await resp.json(content_type=None)
        except EnkaError:
            raise
        except aiohttp.ClientError as e:
            logger.warning("Enka への接続に失敗しました: %s", e)
            raise EnkaError("error") from e
        except (TypeError, ValueError) as e:
            logger.warning("Enka の応答が読めませんでした: %s", e)
            raise EnkaError("error") from e

        if not isinstance(payload, dict):
            raise EnkaError("error")
        showcase = await self._parse_showcase(uid, payload)
        ttl = max(_safe_int(payload.get("ttl"), ENKA_CACHE_SECONDS_FALLBACK), 30)
        self._uid_cache[uid] = (now + ttl, showcase)
        return showcase

    def _maybe_cleanup_assets(self) -> None:
        now = time.time()
        if now - self._asset_cleaned_at < _ASSET_CLEAN_INTERVAL:
            return
        self._asset_cleaned_at = now
        removed = cleanup_enka_assets(STORAGE_DIR / "enka_assets", ENKA_ASSET_RETENTION_DAYS, now=now)
        if removed:
            logger.info("期限切れの画像キャッシュを %s 件消した", removed)

    async def ensure_store(self) -> None:
        now = time.time()
        if self._store is not None and now < self._store_expire:
            return
        store_dir = STORAGE_DIR / "enka_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        characters = await self._load_store_file(store_dir / "characters.json", STORE_CHARACTERS)
        loc = await self._load_store_file(store_dir / "loc.json", STORE_LOC)
        self._apply_store(characters, loc, expire_at=now + _STORE_TTL)

    def _apply_store(self, characters: dict, loc: dict, *, expire_at: float) -> None:
        self._store = characters
        self._loc_ja = dict(loc.get("ja") or loc.get("jp") or {})
        self._store_expire = expire_at

    async def _load_store_file(self, path: Path, url: str, *, force: bool = False) -> dict:
        if not force and path.exists() and time.time() - path.stat().st_mtime < _STORE_TTL:
            return json.loads(path.read_text(encoding="utf-8"))
        session = await self._http()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            resp.raise_for_status()
            payload = await resp.json(content_type=None)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        return payload

    async def refresh_store(self) -> None:
        """キャラ名・立ち絵の辞書を Enka から取り直す。"""
        store_dir = STORAGE_DIR / "enka_store"
        store_dir.mkdir(parents=True, exist_ok=True)
        characters = await self._load_store_file(store_dir / "characters.json", STORE_CHARACTERS, force=True)
        loc = await self._load_store_file(store_dir / "loc.json", STORE_LOC, force=True)
        self._apply_store(characters, loc, expire_at=time.time() + _STORE_TTL)
        self._uid_cache.clear()
        logger.info("Enka のキャラ辞書を取り直しました")

    def _loc(self, hash_value: object) -> str:
        if self._loc_ja is None or hash_value is None:
            return ""
        text = self._loc_ja.get(str(hash_value), "")
        if text:
            return text
        try:
            return self._loc_ja.get(str(int(float(str(hash_value)))), "")
        except (TypeError, ValueError):
            return ""

    def _set_id_from_name(self, name_ja: str) -> str | None:
        if not name_ja:
            return None
        for set_id, row in load_sets().items():
            if row["name_ja"] == name_ja:
                return set_id
            if name_ja in list(row.get("aliases") or []):
                return set_id
        return None

    def _store_info(self, avatar_id: int, skill_depot_id: int) -> dict:
        store = self._store or {}
        base = dict(store.get(str(avatar_id)) or {})
        specific = store.get(f"{avatar_id}-{skill_depot_id}") or {}
        if specific:
            base.update(specific)
        return base

    def _name_id_for_avatar(self, avatar_id: int, skill_depot_id: int, costume_id: int | None) -> str:
        info = self._store_info(avatar_id, skill_depot_id)
        if costume_id:
            costume = (info.get("Costumes") or {}).get(str(costume_id)) or {}
            side = str(costume.get("sideIconName") or "")
            if side.startswith("UI_AvatarIcon_Side_"):
                return side.removeprefix("UI_AvatarIcon_Side_")
            icon = str(costume.get("icon") or "")
            if icon.startswith("UI_AvatarIcon_"):
                return icon.removeprefix("UI_AvatarIcon_")
        side = str(info.get("SideIconName") or "")
        if side.startswith("UI_AvatarIcon_Side_"):
            return side.removeprefix("UI_AvatarIcon_Side_")
        local = _local_side_icons().get(str(avatar_id), "")
        if local.startswith("UI_AvatarIcon_Side_"):
            return local.removeprefix("UI_AvatarIcon_Side_")
        return self._name_id_from_catalog(avatar_id)

    def _name_id_from_catalog(self, avatar_id: int) -> str:
        """Enka store に無い子は、ローカルキャラ表の英名から画像名を当てる。"""
        character = GenshinGame().character_by_enka_key(str(avatar_id))
        if character is None:
            return ""
        for alias in character.aliases:
            if alias.isascii() and alias.isalpha() and alias[:1].isupper():
                return alias
        return ""

    def _icon_for_avatar(self, avatar_id: int, skill_depot_id: int, costume_id: int | None) -> str:
        info = self._store_info(avatar_id, skill_depot_id)
        if costume_id:
            costume = (info.get("Costumes") or {}).get(str(costume_id)) or {}
            if costume.get("icon"):
                return str(costume["icon"])
        name_id = self._name_id_for_avatar(avatar_id, skill_depot_id, costume_id)
        return f"UI_AvatarIcon_{name_id}" if name_id else ""

    def _splash_for_avatar(self, avatar_id: int, skill_depot_id: int, costume_id: int | None) -> str:
        names = self.portrait_names(avatar_id, skill_depot_id, costume_id)
        return names[0] if names else self._icon_for_avatar(avatar_id, skill_depot_id, costume_id)

    def portrait_names(self, avatar_id: int, skill_depot_id: int, costume_id: int | None = None) -> list[str]:
        """カード用立ち絵の候補。ガチャ絵 → 縦スライス → 顔アイコン。"""
        names: list[str] = []
        info = self._store_info(avatar_id, skill_depot_id)
        if costume_id:
            costume = (info.get("Costumes") or {}).get(str(costume_id)) or {}
            for key in ("art", "icon"):
                value = str(costume.get(key) or "")
                if value:
                    names.append(value)
            name_id = self._name_id_for_avatar(avatar_id, skill_depot_id, costume_id)
            if name_id:
                names.append(f"UI_AvatarIcon_{name_id}")
            return list(dict.fromkeys(n for n in names if n))
        name_id = self._name_id_for_avatar(avatar_id, skill_depot_id, costume_id)
        if name_id in {"PlayerBoy", "PlayerGirl"}:
            return [f"UI_AvatarIcon_{name_id}"]
        if name_id:
            names.extend(
                [
                    f"UI_Gacha_AvatarImg_{name_id}",
                    f"UI_Gacha_AvatarIcon_{name_id}",
                    f"UI_AvatarIcon_{name_id}",
                ]
            )
        return list(dict.fromkeys(n for n in names if n))

    def _skills_for_avatar(self, info: dict, skill_map: dict, name_id: str) -> list[tuple[str, int]]:
        """天賦。store が空なら英名からアイコン名を当てる。"""
        skills: list[tuple[str, int]] = []
        order = list(info.get("SkillOrder") or [])
        icons = info.get("Skills") or {}
        if order:
            for skill_id in order[:3]:
                icon = str(icons.get(str(skill_id)) or "")
                level = int(skill_map.get(str(skill_id), skill_map.get(skill_id, 1)) or 1)
                skills.append((icon, level))
            return skills
        ids: list[int] = []
        for key in skill_map:
            try:
                ids.append(int(key))
            except (TypeError, ValueError):
                continue
        ids.sort()
        guessed = ["Skill_A_01"]
        if name_id:
            guessed.extend([f"Skill_S_{name_id}_01", f"Skill_E_{name_id}_01"])
        else:
            guessed.extend(["", ""])
        for skill_id, icon in zip(ids[:3], guessed):
            level = int(skill_map.get(str(skill_id), skill_map.get(skill_id, 1)) or 1)
            skills.append((icon, level))
        return skills

    def _const_icons(self, info: dict, name_id: str) -> list[str]:
        existing = [str(x) for x in info.get("Consts") or [] if x]
        if existing:
            return existing
        if not name_id:
            return []
        return [
            f"UI_Talent_S_{name_id}_01",
            f"UI_Talent_S_{name_id}_03",
            f"UI_Talent_U_{name_id}_01",
            f"UI_Talent_S_{name_id}_02",
            f"UI_Talent_U_{name_id}_02",
            f"UI_Talent_S_{name_id}_04",
        ]

    def _element_for_avatar(self, avatar_id: int, skill_depot_id: int) -> str:
        raw = str(self._store_info(avatar_id, skill_depot_id).get("Element") or "")
        return {
            "Fire": "pyro",
            "Water": "hydro",
            "Ice": "cryo",
            "Electric": "electro",
            "Wind": "anemo",
            "Rock": "geo",
            "Grass": "dendro",
        }.get(raw, "")

    def _name_for_avatar(self, avatar_id: int, skill_depot_id: int) -> str:
        return self._loc(self._store_info(avatar_id, skill_depot_id).get("NameTextMapHash"))

    async def _parse_showcase(self, uid: str, payload: dict) -> EnkaShowcase:
        await self.ensure_store()
        game = GenshinGame()
        raw_avatars = [item for item in _as_list(payload.get("avatarInfoList")) if isinstance(item, dict)]
        unknown: list[str] = []
        for item in raw_avatars:
            avatar_id = str(_safe_int(item.get("avatarId")))
            if avatar_id != "0" and game.character_by_enka_key(avatar_id) is None:
                unknown.append(avatar_id)
        if unknown:
            from services.character_learn import learn_ids

            try:
                names = await learn_ids(await self._http(), unknown)
            except Exception:
                logger.exception("未知のキャラの図鑑取得に失敗しました ids=%s", unknown)
            else:
                if names:
                    logger.info("図鑑からキャラを覚えた: %s", "、".join(names))
        player = _as_dict(payload.get("playerInfo"))
        avatars: list[EnkaAvatar] = []
        for item in raw_avatars:
            try:
                avatars.append(self._parse_avatar(game, item))
            except Exception:
                logger.exception("紹介キャラの読み取りに失敗しました avatarId=%s", item.get("avatarId"))
        return EnkaShowcase(
            uid=str(payload.get("uid") or uid),
            nickname=str(player.get("nickname") or "？"),
            level=_safe_int(player.get("level")),
            avatars=avatars,
            ttl=_safe_int(payload.get("ttl"), ENKA_CACHE_SECONDS_FALLBACK),
        )

    def _parse_avatar(self, game: GenshinGame, raw: dict) -> EnkaAvatar:
        avatar_id = _safe_int(raw.get("avatarId"))
        skill_depot_id = _safe_int(raw.get("skillDepotId"))
        costume_id = _safe_int(raw.get("costumeId")) or None
        prop_map = _as_dict(raw.get("propMap"))
        level = max(1, _safe_int(_as_dict(prop_map.get("4001")).get("val"), 1))
        fight = _as_dict(raw.get("fightPropMap"))

        def fp(key: int) -> float:
            value = fight.get(str(key), fight.get(key, 0)) or 0
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        pieces: list[ParsedPiece] = []
        weapon: EnkaWeapon | None = None
        for equip in _as_list(raw.get("equipList")):
            if not isinstance(equip, dict):
                continue
            flat = _as_dict(equip.get("flat"))
            item_type = flat.get("itemType")
            if item_type == "ITEM_WEAPON" or equip.get("weapon"):
                weapon_raw = _as_dict(equip.get("weapon"))
                affix = _as_dict(weapon_raw.get("affixMap"))
                refine = 1
                if affix:
                    refine = _safe_int(next(iter(affix.values()))) + 1
                base_atk = 0.0
                sub_key = ""
                sub_value = 0.0
                for row in _as_list(flat.get("weaponStats")):
                    if not isinstance(row, dict):
                        continue
                    prop = str(row.get("appendPropId") or "")
                    value = 0.0
                    try:
                        value = float(row.get("statValue") or 0)
                    except (TypeError, ValueError):
                        pass
                    if prop == "FIGHT_PROP_BASE_ATTACK":
                        base_atk = value
                    else:
                        sub_key = ENKA_PROP_TO_KEY.get(prop, "")
                        sub_value = value
                name_hash = flat.get("nameTextMapHash")
                if name_hash is None:
                    name_hash = flat.get("nameTextHashMap")
                if name_hash is None:
                    name_hash = equip.get("nameTextMapHash")
                weapon = EnkaWeapon(
                    name_ja=self._loc(name_hash),
                    level=_safe_int(weapon_raw.get("level"), 1) or 1,
                    refine=refine,
                    icon=str(flat.get("icon") or ""),
                    rarity=_safe_int(flat.get("rankLevel"), 1) or 1,
                    base_atk=base_atk,
                    sub_key=sub_key,
                    sub_value=sub_value,
                )
                continue
            slot = SLOT_FROM_ENKA.get(str(flat.get("equipType") or ""), None)
            icon = str(flat.get("icon") or "")
            set_name = self._loc(flat.get("setNameTextMapHash") or flat.get("setNameTextHashMap"))
            icon_row = set_from_icon(icon)
            if not set_name and icon_row:
                set_name = str(icon_row.get("name_ja") or "")
            set_id = self._set_id_from_name(set_name) or (str(icon_row.get("set_id") or "") if icon_row else "")
            main_raw = _as_dict(flat.get("reliquaryMainstat"))
            main_key = ENKA_PROP_TO_KEY.get(str(main_raw.get("mainPropId") or ""), "")
            main = None
            if main_key:
                try:
                    main_val = float(main_raw.get("statValue") or 0)
                except (TypeError, ValueError):
                    main_val = 0.0
                main = ParsedStat(
                    key=main_key,
                    value=main_val,
                    is_percent=main_key in PERCENT_KEYS,
                )
            reliquary = _as_dict(equip.get("reliquary"))
            roll_counts: dict[str, int] = {}
            for affix in _as_list(reliquary.get("appendPropIdList")):
                roll_key = affix_stat_key(_safe_int(affix))
                if roll_key:
                    roll_counts[roll_key] = roll_counts.get(roll_key, 0) + 1
            subs: list[ParsedStat] = []
            for sub in _as_list(flat.get("reliquarySubstats")):
                if not isinstance(sub, dict):
                    continue
                sub_key = ENKA_PROP_TO_KEY.get(str(sub.get("appendPropId") or ""), "")
                if not sub_key:
                    continue
                try:
                    sub_val = float(sub.get("statValue") or 0)
                except (TypeError, ValueError):
                    sub_val = 0.0
                subs.append(
                    ParsedStat(
                        key=sub_key,
                        value=sub_val,
                        is_percent=sub_key in PERCENT_KEYS,
                        rolls=roll_counts.get(sub_key, 0),
                    )
                )
            pieces.append(
                ParsedPiece(
                    slot=slot,
                    set_id=set_id or None,
                    set_name_ja=set_name or None,
                    main=main,
                    subs=subs,
                    rarity=_safe_int(flat.get("rankLevel")) or None,
                    level=max(0, _safe_int(reliquary.get("level"), 1) - 1),
                    icon=icon or None,
                )
            )

        key_full = f"{avatar_id}-{skill_depot_id}"
        character = game.character_by_enka_key(key_full) or game.character_by_enka_key(str(avatar_id))
        name_ja = self._name_for_avatar(avatar_id, skill_depot_id)
        element = self._element_for_avatar(avatar_id, skill_depot_id)
        if character is None:
            character = game.fallback_character(avatar_id, name_ja or t(msg.MSG_57), element)
        else:
            name_ja = character.name_ja
            element = character.element or element
        name_ja = (name_ja or character.name_ja or t(msg.MSG_57)).strip()
        info = self._store_info(avatar_id, skill_depot_id)
        skill_map = _as_dict(raw.get("skillLevelMap"))
        name_id = self._name_id_for_avatar(avatar_id, skill_depot_id, costume_id)
        skills = self._skills_for_avatar(info, skill_map, name_id)
        dmg_key, dmg_val = _best_dmg_bonus(fp)
        return EnkaAvatar(
            avatar_id=avatar_id,
            skill_depot_id=skill_depot_id,
            name_ja=name_ja,
            icon=self._icon_for_avatar(avatar_id, skill_depot_id, costume_id),
            splash_icon=self._splash_for_avatar(avatar_id, skill_depot_id, costume_id),
            costume_id=costume_id,
            level=level,
            constellations=len(_as_list(raw.get("talentIdList"))),
            friendship=_safe_int(_as_dict(raw.get("fetterInfo")).get("expLevel"), 1) or 1,
            character=character,
            pieces=pieces,
            weapon=weapon,
            stats={
                "hp": fp(2000),
                "atk": fp(2001),
                "def": fp(2002),
                "em": fp(28),
                "er": _as_percent(fp(23), energy=True),
                "crit_rate": _as_percent(fp(20)),
                "crit_dmg": _as_percent(fp(22)),
            },
            element=element,
            skills=skills,
            constellation_icons=self._const_icons(info, name_id),
            hp_base=fp(1),
            atk_base=fp(4),
            def_base=fp(7),
            dmg_bonus_key=dmg_key,
            dmg_bonus=dmg_val,
        )

    async def download_icon(self, icon: str) -> bytes | None:
        """Enka の ui アイコンを取る。失敗したら None。"""
        if not icon or ".." in icon or not _ICON_NAME_RE.fullmatch(icon):
            return None
        if icon in self._missing_icons:
            return None
        cache_dir = (STORAGE_DIR / "enka_assets").resolve()
        cache_dir.mkdir(parents=True, exist_ok=True)
        path = (cache_dir / f"{icon}.png").resolve()
        if path.parent != cache_dir:
            return None
        if path.exists() and path.stat().st_size > 0:
            try:
                path.touch()
            except OSError:
                pass
            data = path.read_bytes()
            self._maybe_cleanup_assets()
            return data
        self._maybe_cleanup_assets()
        session = await self._http()
        url = ENKA_UI_URL.format(icon=icon)
        data: bytes | None = None
        for attempt in range(2):
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 404:
                        self._missing_icons.add(icon)
                        logger.warning("アイコンを取得できませんでした(%s): HTTP 404", icon)
                        return None
                    if resp.status != 200:
                        logger.warning(
                            "アイコンを取得できませんでした(%s): HTTP %s", icon, resp.status
                        )
                    else:
                        data = await resp.read()
                        break
            except aiohttp.ClientError as e:
                logger.warning("アイコンの取得に失敗しました(%s): %s", icon, e)
            if attempt == 0:
                await asyncio.sleep(0.4)
        if not data:
            return None
        path.write_bytes(data)
        return data

    async def download_icons(self, names: list[str]) -> dict[str, bytes]:
        """複数アイコンを取る。失敗した名前は載せない。"""
        unique = list(dict.fromkeys(n for n in names if n))
        out: dict[str, bytes] = {}
        for name in unique:
            data = await self.download_icon(name)
            if data:
                out[name] = data
        return out
