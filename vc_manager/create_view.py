"""部屋作成ボタンと設定モーダル。再起動後も custom_id から復元する。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import discord

from logging_config import get_logger
from replies import send_ephemeral
from vc_manager import messages as msg
from vc_manager.config import (
    CREATE_COOLDOWN_SECONDS,
    DEFAULT_OCCUPANCY,
    EMPTY_GRACE_SECONDS,
    ROOM_DETAILS_MAX,
    ROOM_TITLE_MAX,
    ROOM_UNTIL_MAX,
    VACANT_TIMEOUT_SECONDS,
)
from vc_manager.rooms import clip_plain, parse_occupancy

if TYPE_CHECKING:
    from cogs.vc_manager import VcManagerCog

logger = get_logger(__name__)
CREATE_BUTTON_CUSTOM_ID = "vc:create"


class VcCreateButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:create",
):
    """パネルから部屋作成モーダルを開く。"""

    def __init__(self) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_CREATE_BUTTON,
                style=discord.ButtonStyle.success,
                emoji=msg.MSG_CREATE_BUTTON_EMOJI,
                custom_id=CREATE_BUTTON_CUSTOM_ID,
            )
        )

    @classmethod
    async def from_custom_id(
        cls,
        interaction: discord.Interaction,
        item: discord.ui.Button,
        match: re.Match[str],
        /,
    ) -> VcCreateButton:
        return cls()

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            cog = _vc_cog(interaction)
            if cog is None:
                await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
                return
            if cog.resolve_member(interaction) is None:
                await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
                return
            await interaction.response.send_modal(CreateRoomModal())
        except discord.HTTPException:
            logger.warning("部屋作成モーダルの表示に失敗しました")
        except Exception:
            logger.exception("部屋作成ボタンの処理に失敗しました")
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)


class CreateRoomModal(discord.ui.Modal, title=msg.MSG_MODAL_TITLE):
    """種類・部屋名・何時まで・詳細・人数。"""

    def __init__(self) -> None:
        super().__init__(timeout=300)
        self.kind_select = discord.ui.Select(
            placeholder=msg.MSG_MODAL_KIND_PLACEHOLDER,
            min_values=1,
            max_values=1,
            required=True,
            options=[
                discord.SelectOption(label=label, value=key) for key, label in msg.MSG_ROOM_KINDS
            ],
        )
        self.name_input = discord.ui.TextInput(
            required=False,
            max_length=ROOM_TITLE_MAX,
            placeholder=msg.MSG_MODAL_NAME_PLACEHOLDER,
        )
        self.until_input = discord.ui.TextInput(
            required=False,
            max_length=ROOM_UNTIL_MAX,
            placeholder=msg.MSG_MODAL_UNTIL_PLACEHOLDER,
        )
        self.details_input = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=ROOM_DETAILS_MAX,
            placeholder=msg.MSG_MODAL_DETAILS_PLACEHOLDER,
        )
        self.occupancy_input = discord.ui.TextInput(
            required=False,
            max_length=2,
            default=str(DEFAULT_OCCUPANCY),
            placeholder=msg.MSG_MODAL_OCCUPANCY_PLACEHOLDER,
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_KIND,
                description=msg.MSG_MODAL_KIND_DESC,
                component=self.kind_select,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_NAME,
                description=msg.MSG_MODAL_NAME_DESC,
                component=self.name_input,
            )
        )
        self.add_item(
            discord.ui.Label(
                text=msg.MSG_MODAL_UNTIL,
                description=msg.MSG_MODAL_UNTIL_DESC,
                component=self.until_input,
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
                text=msg.MSG_MODAL_OCCUPANCY,
                description=msg.MSG_MODAL_OCCUPANCY_DESC,
                component=self.occupancy_input,
            )
        )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cog = _vc_cog(interaction)
        if cog is None:
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
            return
        picked = self.kind_select.values
        kind_key = picked[0] if picked else ""
        kind_label = msg.ROOM_KIND_LABELS.get(kind_key)
        if kind_label is None:
            await send_ephemeral(interaction, msg.MSG_KIND_INVALID)
            return
        occupancy = parse_occupancy(str(self.occupancy_input.value or ""))
        if occupancy is None:
            await send_ephemeral(interaction, msg.MSG_OCCUPANCY_INVALID, persist=True)
            return
        title = clip_plain(str(self.name_input.value or ""), ROOM_TITLE_MAX)
        details = clip_plain(str(self.details_input.value or ""), ROOM_DETAILS_MAX, keep_newlines=True)
        until = clip_plain(str(self.until_input.value or ""), ROOM_UNTIL_MAX)
        await cog.complete_create_room(
            interaction,
            kind_label=kind_label,
            title=title,
            details=details,
            until=until,
            occupancy=occupancy,
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("部屋作成モーダルの処理に失敗しました")
        await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)


def create_room_view() -> discord.ui.View:
    """パネルに載せる作成ボタン。"""
    view = discord.ui.View(timeout=None)
    view.add_item(VcCreateButton())
    return view


def recruit_embed(
    *,
    name: str,
    mention: str,
    details: str,
    until: str,
    kind_label: str,
    occupied: int,
    occupancy: int,
    room_mention: str,
    invite_url: str,
) -> discord.Embed:
    """募集チャンネルに出す埋め込み。"""
    description = msg.MSG_EMBED_DESCRIPTION.format(mention=mention)
    if details:
        description = f"{description}\n\n{details}"
    embed = discord.Embed(title=name, description=description, color=0x5865F2)
    embed.add_field(name=msg.MSG_EMBED_KIND, value=kind_label, inline=True)
    embed.add_field(name=msg.MSG_EMBED_CAPACITY, value=f"{occupied}/{occupancy}", inline=True)
    if until:
        embed.add_field(name=msg.MSG_EMBED_UNTIL, value=until, inline=True)
    embed.add_field(name=msg.MSG_EMBED_ROOM, value=room_mention, inline=True)
    embed.add_field(name=msg.MSG_JOIN_BUTTON, value=invite_url, inline=False)
    return embed


def format_duration_ja(seconds: int) -> str:
    """パネル用の待ち時間。60の倍数は分、それ以外は秒。"""
    if seconds <= 0:
        return "すぐ"
    if seconds % 60 == 0:
        return f"{seconds // 60}分"
    return f"{seconds}秒"


def panel_embed() -> discord.Embed:
    embed = discord.Embed(
        title=msg.MSG_PANEL_TITLE,
        description=msg.MSG_PANEL_DESCRIPTION,
        color=0x5865F2,
    )
    embed.add_field(name=msg.MSG_PANEL_FIELD_HOW, value=msg.MSG_PANEL_HOW, inline=False)
    embed.add_field(
        name=msg.MSG_PANEL_FIELD_NOTE,
        value=msg.MSG_PANEL_NOTE.format(
            vacant=format_duration_ja(VACANT_TIMEOUT_SECONDS),
            empty=format_duration_ja(EMPTY_GRACE_SECONDS),
            cooldown=format_duration_ja(CREATE_COOLDOWN_SECONDS),
        ),
        inline=False,
    )
    embed.set_footer(text=msg.MSG_PANEL_FOOTER)
    return embed


def is_panel_message(message: discord.Message, bot_id: int) -> bool:
    if message.author.id != bot_id:
        return False
    for row in message.components:
        children = getattr(row, "children", None) or []
        for child in children:
            if getattr(child, "custom_id", None) == CREATE_BUTTON_CUSTOM_ID:
                return True
    return False


def _vc_cog(interaction: discord.Interaction) -> VcManagerCog | None:
    cog = interaction.client.get_cog("VcManagerCog")
    if cog is None:
        return None
    return cast("VcManagerCog", cog)
