"""ビルドカードの最近履歴。Discord ユーザー単位で UID／キャラを覚える。"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from config import STORAGE_DIR
from logging_config import get_logger

logger = get_logger(__name__)

HISTORY_PATH = STORAGE_DIR / "buildcard_history.json"
HISTORY_MAX = 5


@dataclass
class HistoryEntry:
    """最近出したカード1件。自分以外の UID もあり得る。"""

    uid: str
    nickname: str
    avatar_id: int
    skill_depot_id: int
    character_name_ja: str
    build_id: str | None = None
    build_name_ja: str = ""
    updated_at: float = 0.0

    @property
    def key(self) -> str:
        build = self.build_id or ""
        return f"{self.uid}:{self.avatar_id}:{self.skill_depot_id}:{build}"


class CardHistoryStore:
    """ユーザー ID → 履歴（新しい順、最大 HISTORY_MAX）。"""

    def __init__(self, path: Path = HISTORY_PATH, *, max_entries: int = HISTORY_MAX) -> None:
        self._path = path
        self._max_entries = max_entries
        self._by_user: dict[str, list[HistoryEntry]] = {}
        self._load()

    def list_for(self, user_id: int) -> list[HistoryEntry]:
        return list(self._by_user.get(str(user_id), []))

    def remember(
        self,
        user_id: int,
        *,
        uid: str,
        nickname: str,
        avatar_id: int,
        skill_depot_id: int,
        character_name_ja: str,
        build_id: str | None,
        build_name_ja: str = "",
    ) -> None:
        """成功した出しを先頭に足す。同じ組み合わせは更新して繰り上げ。"""
        entry = HistoryEntry(
            uid=uid,
            nickname=nickname,
            avatar_id=avatar_id,
            skill_depot_id=skill_depot_id,
            character_name_ja=character_name_ja,
            build_id=build_id,
            build_name_ja=build_name_ja,
            updated_at=time.time(),
        )
        key = str(user_id)
        rows = [row for row in self._by_user.get(key, []) if row.key != entry.key]
        rows.insert(0, entry)
        self._by_user[key] = rows[: self._max_entries]
        self._save()

    def clear(self, user_id: int) -> None:
        key = str(user_id)
        if key not in self._by_user:
            return
        self._by_user.pop(key, None)
        self._save()

    def _load(self) -> None:
        if not self._path.exists():
            self._by_user = {}
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.warning("ビルドカード履歴の読み込みに失敗しました path=%s", self._path)
            self._by_user = {}
            return
        if not isinstance(raw, dict):
            self._by_user = {}
            return
        loaded: dict[str, list[HistoryEntry]] = {}
        for user_key, items in raw.items():
            if not isinstance(items, list):
                continue
            rows: list[HistoryEntry] = []
            for item in items:
                entry = _entry_from_dict(item)
                if entry is not None:
                    rows.append(entry)
            if rows:
                loaded[str(user_key)] = rows[: self._max_entries]
        self._by_user = loaded

    def _save(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {
                user_id: [asdict(entry) for entry in rows]
                for user_id, rows in self._by_user.items()
            }
            tmp = self._path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(self._path)
        except OSError:
            logger.exception("ビルドカード履歴の保存に失敗しました path=%s", self._path)


def _entry_from_dict(item: object) -> HistoryEntry | None:
    if not isinstance(item, dict):
        return None
    try:
        uid = str(item.get("uid") or "")
        avatar_id = int(item.get("avatar_id") or 0)
        if not uid or avatar_id <= 0:
            return None
        build_raw = item.get("build_id")
        build_id = str(build_raw) if build_raw else None
        return HistoryEntry(
            uid=uid,
            nickname=str(item.get("nickname") or ""),
            avatar_id=avatar_id,
            skill_depot_id=int(item.get("skill_depot_id") or 0),
            character_name_ja=str(item.get("character_name_ja") or ""),
            build_id=build_id,
            build_name_ja=str(item.get("build_name_ja") or ""),
            updated_at=float(item.get("updated_at") or 0.0),
        )
    except (TypeError, ValueError):
        return None
