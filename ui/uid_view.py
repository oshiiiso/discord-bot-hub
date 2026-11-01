"""紹介キャラを選ぶ View。自分にだけ見える。"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

import messages as msg
from config import VIEW_TIMEOUT_SECONDS
from logging_config import get_logger
from replies import send_ephemeral
from services.copy import t
from services.session_store import UidSession

logger = get_logger(__name__)

if TYPE_CHECKING:
    from cogs.buildcard import BuildCog

PAGE_SIZE = 25
_SELECT_LABEL_MAX = 100


def _select_label(text: str) -> str:
    """Discord のセレクトは label が 1〜100 文字必須。"""
    raw = (text or "").strip()[:_SELECT_LABEL_MAX]
    if raw:
        return raw
    return t(msg.MSG_57)[:_SELECT_LABEL_MAX]


class UidPickView(discord.ui.View):
    """紹介キャラ選択とビルド選択。チャンネルには出さない。"""

    def __init__(self, cog: BuildCog, session_key: int) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.cog = cog
        self.session_key = session_key
        self.rebuild()

    def session(self) -> UidSession | None:
        return self.cog.sessions.get(self.session_key)

    def rebuild(self) -> None:
        self.clear_items()
        session = self.session()
        if session is None:
            return
        selected = session.selected_index
        options = [
            discord.SelectOption(
                label=_select_label(a.name_ja),
                value=str(i),
                description=f"Lv.{a.level} C{a.constellations}"[:100],
                default=selected == i,
            )
            for i, a in enumerate(session.avatars[:PAGE_SIZE])
        ]
        if options:
            self.add_item(_AvatarSelect(self, options, t(msg.MSG_20)))
        avatar = session.selected_avatar()
        if avatar and len(avatar.character.builds) > 1:
            build_opts = [
                discord.SelectOption(
                    label=_select_label(b.name_ja),
                    value=b.id,
                    default=session.build_id == b.id,
                )
                for b in avatar.character.builds
            ]
            self.add_item(_UidBuildSelect(self, build_opts, t(msg.MSG_19)))
        self.add_item(_PublishButton(self))
        self.add_item(_RefreshButton(self))

    async def on_timeout(self) -> None:
        self.cog.sessions.drop(self.session_key)

    async def _ensure_owner(self, interaction: discord.Interaction) -> bool:
        session = self.session()
        if session is None:
            await send_ephemeral(interaction, t(msg.ERR_03))
            return False
        if interaction.user.id != session.user_id:
            await send_ephemeral(interaction, t(msg.ERR_01))
            return False
        return True


class _AvatarSelect(discord.ui.Select):
    def __init__(self, parent: UidPickView, options: list[discord.SelectOption], placeholder: str) -> None:
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        session = self.parent_view.session()
        if session is None:
            return
        session.selected_index = int(self.values[0])
        avatar = session.selected_avatar()
        if avatar is None:
            await send_ephemeral(interaction, t(msg.ERR_03))
            return
        session.build_id = avatar.character.builds[0].id if avatar.character.builds else None
        self.parent_view.rebuild()
        if len(avatar.character.builds) > 1:
            content = t(msg.MSG_76, nickname=session.nickname, character=avatar.name_ja)
        else:
            content = t(msg.MSG_32, nickname=session.nickname, character=avatar.name_ja)
        try:
            await interaction.response.edit_message(content=content, view=self.parent_view)
        except discord.HTTPException:
            logger.warning("キャラ選択の更新に失敗しました")


class _UidBuildSelect(discord.ui.Select):
    def __init__(self, parent: UidPickView, options: list[discord.SelectOption], placeholder: str) -> None:
        super().__init__(placeholder=placeholder, options=options, min_values=1, max_values=1)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        session = self.parent_view.session()
        if session is None:
            return
        session.build_id = self.values[0]
        avatar = session.selected_avatar()
        name = avatar.name_ja if avatar else ""
        try:
            await interaction.response.edit_message(
                content=t(msg.MSG_32, nickname=session.nickname, character=name),
                view=self.parent_view,
            )
        except discord.HTTPException:
            logger.warning("ビルド選択の更新に失敗しました")


class _PublishButton(discord.ui.Button):
    def __init__(self, parent: UidPickView) -> None:
        super().__init__(label=t(msg.MSG_74), style=discord.ButtonStyle.primary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        session = self.parent_view.session()
        if session is None or session.selected_avatar() is None:
            await send_ephemeral(interaction, t(msg.MSG_75))
            return
        try:
            await self.parent_view.cog.publish_card(interaction, self.parent_view)
        except Exception:
            logger.exception("カード投稿の処理に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_13))


class _RefreshButton(discord.ui.Button):
    def __init__(self, parent: UidPickView) -> None:
        super().__init__(label=t(msg.MSG_55), style=discord.ButtonStyle.secondary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_owner(interaction):
            return
        await self.parent_view.cog.refresh_uid_session(interaction, self.parent_view)
