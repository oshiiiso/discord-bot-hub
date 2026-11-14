"""募集埋め込みの編集ボタン。再起動後も custom_id から復元する。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import discord

from logging_config import get_logger
from replies import send_ephemeral
from vc_manager import messages as msg
from vc_manager.config import (
    ROOM_DETAILS_MAX,
    ROOM_TITLE_MAX,
    UNLIMITED_OCCUPANCY,
)
from vc_manager.manage_view import VcManageButton
from vc_manager.rooms import Room, clip_plain, parse_occupancy

if TYPE_CHECKING:
    from cogs.vc_manager import VcManagerCog

logger = get_logger(__name__)


class VcEditButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:edit:(?P<channel_id>[0-9]+)",
):
    """作成者だけが募集内容を直せる。"""

    def __init__(self, channel_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_EDIT_BUTTON,
                style=discord.ButtonStyle.secondary,
                emoji=msg.MSG_EDIT_BUTTON_EMOJI,
                custom_id=f"vc:edit:{channel_id}",
            )
        )
        self.channel_id = channel_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ) -> VcEditButton:
        return cls(int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            cog = _vc_cog(interaction)
            if cog is None:
                await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
                return
            room = cog.get_room(self.channel_id)
            if room is None:
                await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
                return
            if interaction.user.id != room.owner_id:
                await send_ephemeral(interaction, msg.MSG_EDIT_FORBIDDEN)
                return
            if not room.can_edit:
                await send_ephemeral(interaction, msg.MSG_EDIT_UNSUPPORTED, persist=True)
                return
            await interaction.response.send_modal(EditRoomModal(room))
        except discord.HTTPException:
            logger.warning("編集モーダルの表示に失敗しました channel_id=%s", self.channel_id)
        except Exception:
            logger.exception("編集ボタンの処理に失敗しました channel_id=%s", self.channel_id)
            await send_ephemeral(interaction, msg.MSG_EDIT_FAILED)


class EditRoomModal(discord.ui.Modal, title=msg.MSG_EDIT_MODAL_TITLE):
    """部屋名・詳細・人数を直す。"""

    def __init__(self, room: Room) -> None:
        super().__init__(timeout=300)
        self.channel_id = room.voice_channel_id
        name_kwargs: dict[str, object] = {
            "required": False,
            "max_length": ROOM_TITLE_MAX,
            "placeholder": msg.MSG_MODAL_NAME_PLACEHOLDER,
        }
        if room.title:
            name_kwargs["default"] = room.title[:ROOM_TITLE_MAX]
        self.name_input = discord.ui.TextInput(**name_kwargs)

        details_kwargs: dict[str, object] = {
            "style": discord.TextStyle.paragraph,
            "required": False,
            "max_length": ROOM_DETAILS_MAX,
            "placeholder": msg.MSG_MODAL_DETAILS_PLACEHOLDER,
        }
        if room.details:
            details_kwargs["default"] = room.details[:ROOM_DETAILS_MAX]
        self.details_input = discord.ui.TextInput(**details_kwargs)

        self.unlimited_checkbox = discord.ui.Checkbox(
            custom_id="vc:edit:unlimited",
            default=room.occupancy <= UNLIMITED_OCCUPANCY,
        )
        occupancy_kwargs: dict[str, object] = {
            "required": False,
            "max_length": 2,
            "placeholder": msg.MSG_MODAL_OCCUPANCY_PLACEHOLDER,
        }
        if room.occupancy > UNLIMITED_OCCUPANCY:
            occupancy_kwargs["default"] = str(room.occupancy)
        self.occupancy_input = discord.ui.TextInput(**occupancy_kwargs)
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_NAME,
                description=msg.MSG_MODAL_NAME_DESC,
                component=self.name_input,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_DETAILS,
                description=msg.MSG_MODAL_DETAILS_DESC,
                component=self.details_input,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_UNLIMITED,
                description=msg.MSG_MODAL_UNLIMITED_DESC,
                component=self.unlimited_checkbox,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_OCCUPANCY,
                description=msg.MSG_MODAL_OCCUPANCY_DESC,
                component=self.occupancy_input,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cog = _vc_cog(interaction)
        if cog is None:
            await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
            return
        if self.unlimited_checkbox.value:
            occupancy = UNLIMITED_OCCUPANCY
        else:
            occupancy = parse_occupancy(str(self.occupancy_input.value or ""))
            if occupancy is None:
                await send_ephemeral(interaction, msg.MSG_OCCUPANCY_INVALID, persist=True)
                return
        title = clip_plain(str(self.name_input.value or ""), ROOM_TITLE_MAX)
        details = clip_plain(str(self.details_input.value or ""), ROOM_DETAILS_MAX, keep_newlines=True)
        await cog.complete_edit_room(
            interaction,
            channel_id=self.channel_id,
            title=title,
            details=details,
            occupancy=occupancy,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("編集モーダルの処理に失敗しました channel_id=%s", self.channel_id)
        await send_ephemeral(interaction, msg.MSG_EDIT_FAILED)


class VcPauseButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:pause:(?P<channel_id>[0-9]+)",
):
    """募集を停止する。埋め込みは残し、参加リンクだけ消す。"""

    def __init__(self, channel_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_PAUSE_BUTTON,
                style=discord.ButtonStyle.danger,
                custom_id=f"vc:pause:{channel_id}",
            )
        )
        self.channel_id = channel_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ) -> VcPauseButton:
        return cls(int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        await _toggle_recruiting(interaction, self.channel_id, recruiting=False)


class VcResumeButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:resume:(?P<channel_id>[0-9]+)",
):
    """募集を再開する。参加リンクを戻す。"""

    def __init__(self, channel_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_RESUME_BUTTON,
                style=discord.ButtonStyle.success,
                custom_id=f"vc:resume:{channel_id}",
            )
        )
        self.channel_id = channel_id

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ) -> VcResumeButton:
        return cls(int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        await _toggle_recruiting(interaction, self.channel_id, recruiting=True)


def recruit_room_view(channel_id: int, *, recruiting: bool = True) -> discord.ui.View:
    """募集埋め込みに載せる編集・募集停止／再開・メンバー操作ボタン。"""
    view = discord.ui.View(timeout=None)
    view.add_item(VcEditButton(channel_id))
    view.add_item(VcManageButton(channel_id))
    if recruiting:
        view.add_item(VcPauseButton(channel_id))
    else:
        view.add_item(VcResumeButton(channel_id))
    return view


async def _toggle_recruiting(
    interaction: discord.Interaction,
    channel_id: int,
    *,
    recruiting: bool,
) -> None:
    try:
        cog = _vc_cog(interaction)
        if cog is None:
            await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
            return
        room = cog.get_room(channel_id)
        if room is None:
            await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
            return
        if interaction.user.id != room.owner_id:
            await send_ephemeral(interaction, msg.MSG_EDIT_FORBIDDEN)
            return
        if not room.can_edit:
            await send_ephemeral(interaction, msg.MSG_EDIT_UNSUPPORTED, persist=True)
            return
        await cog.complete_set_recruiting(
            interaction,
            channel_id=channel_id,
            recruiting=recruiting,
        )
    except Exception:
        logger.exception(
            "募集状態の切り替えに失敗しました channel_id=%s recruiting=%s",
            channel_id,
            recruiting,
        )
        await send_ephemeral(interaction, msg.MSG_RECRUIT_TOGGLE_FAILED)


def _vc_cog(interaction: discord.Interaction) -> VcManagerCog | None:
    cog = interaction.client.get_cog("VcManagerCog")
    if cog is None:
        return None
    return cast("VcManagerCog", cog)
