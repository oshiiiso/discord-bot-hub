"""一時 VC の状態を JSON に残す。"""

from __future__ import annotations

import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path

from logging_config import get_logger
from vc_manager.config import (
    CHANNEL_NAME_MAX,
    MAX_OCCUPANCY,
    ROOM_TITLE_MAX,
    ROOMS_PATH,
    VACANT_TIMEOUT_SECONDS,
)

logger = get_logger(__name__)
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")
_CONTROL_EXCEPT_NEWLINE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
_MULTI_SPACE = re.compile(r"[ \t]+")
_MULTI_NEWLINE = re.compile(r"\n{3,}")


@dataclass
class Room:
    """募集中の一時ボイスチャンネル。"""

    voice_channel_id: int
    guild_id: int
    message_id: int
    recruit_channel_id: int
    invite_url: str
    owner_id: int
    occupied_once: bool = False
    created_at: float = 0.0
    card_message_id: int = 0
    kind_label: str = ""
    title: str = ""
    details: str = ""
    occupancy: int = 0
    recruiting: bool = True

    @property
    def can_edit(self) -> bool:
        """作成時メタがある部屋だけ後から編集・募集停止できる。"""
        return bool(self.kind_label)


def load_rooms(path: Path = ROOMS_PATH) -> dict[int, Room]:
    """保存済みの部屋を voice_channel_id キーで返す。"""
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, list):
        return {}
    rooms: dict[int, Room] = {}
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            room = Room(
                voice_channel_id=int(item["voice_channel_id"]),
                guild_id=int(item["guild_id"]),
                message_id=int(item["message_id"]),
                recruit_channel_id=int(item["recruit_channel_id"]),
                invite_url=str(item["invite_url"]),
                owner_id=int(item["owner_id"]),
                occupied_once=bool(item.get("occupied_once", False)),
                created_at=float(item.get("created_at") or 0.0),
                card_message_id=int(item.get("card_message_id") or 0),
                kind_label=str(item.get("kind_label") or ""),
                title=str(item.get("title") or ""),
                details=str(item.get("details") or ""),
                occupancy=int(item.get("occupancy") or 0),
                recruiting=bool(item["recruiting"]) if "recruiting" in item else True,
            )
        except (KeyError, TypeError, ValueError):
            continue
        rooms[room.voice_channel_id] = room
    return rooms


def save_rooms(rooms: dict[int, Room], path: Path = ROOMS_PATH) -> None:
    """部屋一覧を原子的に書き出す。失敗しても呼び出し側は継続できる。"""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = [asdict(room) for room in rooms.values()]
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        logger.exception("部屋一覧の保存に失敗しました path=%s", path)


def vacant_remaining_seconds(
    created_at: float,
    *,
    now: float | None = None,
    timeout: float = VACANT_TIMEOUT_SECONDS,
) -> float:
    """未入室の部屋を消すまでの残り秒。created_at が無いなら timeout まるごと。"""
    if created_at <= 0:
        return timeout
    current = time.time() if now is None else now
    return timeout - (current - created_at)


def clip_plain(text: str, max_length: int, *, keep_newlines: bool = False) -> str:
    """埋め込み・部屋名向けに制御文字を落として切り詰める。"""
    if keep_newlines:
        body = _CONTROL_EXCEPT_NEWLINE.sub("", text)
        body = _MULTI_SPACE.sub(" ", body)
        body = _MULTI_NEWLINE.sub("\n\n", body)
    else:
        body = _CONTROL_CHARS.sub("", text)
        body = _MULTI_SPACE.sub(" ", body)
    return body.strip()[:max_length]


def sanitize_channel_name(name: str, fallback: str = "ゲスト") -> str:
    """VC 名。制御文字を除き、Discord の文字数制限に収める。"""
    body = clip_plain(name, CHANNEL_NAME_MAX) or fallback
    return body[:CHANNEL_NAME_MAX]


def composed_room_name(kind: str, title: str) -> str:
    """種類-部屋名。空の段は付けない。全体は 100 字以内。"""
    game_part = clip_plain(kind, CHANNEL_NAME_MAX) or "その他"
    title_part = clip_plain(title, ROOM_TITLE_MAX)
    leftover = CHANNEL_NAME_MAX - len(game_part)
    parts = [game_part]
    if title_part and leftover > 1:
        title_part = title_part[: leftover - 1]
        parts.append(title_part)
    return "-".join(parts)[:CHANNEL_NAME_MAX]


def unique_channel_name(base: str, taken: set[str]) -> str:
    """同名があれば末尾に -1, -2 と足す。"""
    name = clip_plain(base, CHANNEL_NAME_MAX) or "部屋"
    if name not in taken:
        return name
    n = 1
    while n < 1000:
        suffix = f"-{n}"
        candidate = f"{name[: CHANNEL_NAME_MAX - len(suffix)]}{suffix}"
        if candidate not in taken:
            return candidate
        n += 1
    return f"{name[: CHANNEL_NAME_MAX - 4]}-{n}"


def parse_occupancy(raw: str) -> int | None:
    """制限人数（1〜MAX）。全角数字は半角にする。空・不正は None。"""
    text = unicodedata.normalize("NFKC", raw).strip()
    if not text or not text.isdigit():
        return None
    value = int(text)
    if 1 <= value <= MAX_OCCUPANCY:
        return value
    return None
