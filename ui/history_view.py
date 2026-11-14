"""最近出した UID／キャラからの即出しメニュー。自分にだけ見える。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

import messages as msg
from config import VIEW_TIMEOUT_SECONDS
from logging_config import get_logger
from replies import edit_original, send_ephemeral
from services.card_history import HistoryEntry
from services.copy import t

logger = get_logger(__name__)

if TYPE_CHECKING:
    from cogs.buildcard import BuildCog

_SELECT_LABEL_MAX = 100


def _option_label(entry: HistoryEntry) -> str:
    nick = (entry.nickname or "UID").strip() or "UID"
    char = (entry.character_name_ja or "?").strip() or "?"
    text = f"{nick} / {char}"
    return text[:_SELECT_LABEL_MAX]


def _option_desc(entry: HistoryEntry) -> str:
    uid_tail = entry.uid[-4:] if len(entry.uid) >= 4 else entry.uid
    parts = [f"UID …{uid_tail}"]
    if entry.build_name_ja:
        parts.append(entry.build_name_ja)
    return " / ".join(parts)[:100]


def _uid_option_label(entry: HistoryEntry) -> str:
    nick = (entry.nickname or "UID").strip() or "UID"
    return nick[:_SELECT_LABEL_MAX]


def _uid_option_desc(entry: HistoryEntry) -> str:
    uid_tail = entry.uid[-4:] if len(entry.uid) >= 4 else entry.uid
    return f"UID …{uid_tail} の紹介を開く"[:100]


def unique_uid_entries(entries: list[HistoryEntry]) -> list[HistoryEntry]:
    """同じ UID は新しい方だけ残す。"""
    seen: set[str] = set()
    out: list[HistoryEntry] = []
    for entry in entries:
        if entry.uid in seen:
            continue
        seen.add(entry.uid)
        out.append(entry)
    return out


class HistoryStartView(discord.ui.View):
    """即出し・UID紹介オープン・別 UID・履歴削除。"""

    def __init__(self, cog: BuildCog, user_id: int, entries: list[HistoryEntry]) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.cog = cog
        self.user_id = user_id
        self.entries = list(entries)
        if self.entries:
            char_options = [
                discord.SelectOption(
                    label=_option_label(entry),
                    value=str(index),
                    description=_option_desc(entry),
                )
                for index, entry in enumerate(self.entries)
            ]
            self.add_item(_HistorySelect(self, char_options))
            uid_entries = unique_uid_entries(self.entries)
            uid_options = [
                discord.SelectOption(
                    label=_uid_option_label(entry),
                    value=entry.uid,
                    description=_uid_option_desc(entry),
                )
                for entry in uid_entries
            ]
            self.add_item(_OpenUidSelect(self, uid_options))
        self.add_item(_OtherUidButton(self))
        self.add_item(_ClearHistoryButton(self))

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await send_ephemeral(interaction, t(msg.ERR_01))
            return False
        return True


class _HistorySelect(discord.ui.Select):
    def __init__(self, parent: HistoryStartView, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder=t(msg.MSG_90),
            options=options,
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        try:
            index = int(self.values[0])
        except ValueError:
            await send_ephemeral(interaction, t(msg.ERR_03))
            return
        if not 0 <= index < len(self.parent_view.entries):
            await send_ephemeral(interaction, t(msg.ERR_03))
            return
        entry = self.parent_view.entries[index]
        await self.parent_view.cog.publish_from_history(interaction, entry)


class _OpenUidSelect(discord.ui.Select):
    def __init__(self, parent: HistoryStartView, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder=t(msg.MSG_95),
            options=options,
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        uid = self.values[0]
        await self.parent_view.cog.begin_uid(interaction, uid, replace_message=True)


class _OtherUidButton(discord.ui.Button):
    def __init__(self, parent: HistoryStartView) -> None:
        super().__init__(label=t(msg.MSG_91), style=discord.ButtonStyle.secondary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        from ui.start_view import UidModal

        try:
            await interaction.response.send_modal(UidModal())
        except discord.HTTPException:
            logger.warning("履歴からの UID 入力モーダル表示に失敗しました")


class _ClearHistoryButton(discord.ui.Button):
    def __init__(self, parent: HistoryStartView) -> None:
        super().__init__(label=t(msg.MSG_92), style=discord.ButtonStyle.danger)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        self.parent_view.cog.history.clear(self.parent_view.user_id)
        try:
            await interaction.response.edit_message(content=t(msg.MSG_93), view=None)
        except discord.HTTPException:
            await edit_original(interaction, content=t(msg.MSG_93), view=None)
