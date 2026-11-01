"""UID カードの一時セッション。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.enka_client import EnkaAvatar


@dataclass
class UidSession:
    user_id: int
    uid: str
    nickname: str
    avatars: list[EnkaAvatar]
    selected_index: int | None = None
    build_id: str | None = None

    def selected_avatar(self) -> EnkaAvatar | None:
        index = self.selected_index
        if index is None or not 0 <= index < len(self.avatars):
            return None
        return self.avatars[index]

    def reset_pick(self) -> None:
        self.selected_index = None
        self.build_id = None

    def apply_showcase(self, uid: str, nickname: str, avatars: list[EnkaAvatar]) -> None:
        self.uid = uid
        self.nickname = nickname
        self.avatars = list(avatars)
        self.reset_pick()


class SessionStore:
    """選択メッセージ ID をキーにするメモリ保存。"""

    def __init__(self) -> None:
        self._sessions: dict[int, UidSession] = {}

    def put(self, message_id: int, session: UidSession) -> None:
        self._sessions[message_id] = session

    def get(self, message_id: int) -> UidSession | None:
        return self._sessions.get(message_id)

    def drop(self, message_id: int) -> None:
        self._sessions.pop(message_id, None)
