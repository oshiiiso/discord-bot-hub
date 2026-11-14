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
    EMPTY_GRACE_SECONDS,
    ROOM_DETAILS_MAX,
    ROOM_TITLE_MAX,
    UNLIMITED_OCCUPANCY,
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
    """種類・部屋名・詳細・人数無制限・人数。"""

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
        self.details_input = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=ROOM_DETAILS_MAX,
            placeholder=msg.MSG_MODAL_DETAILS_PLACEHOLDER,
        )
        self.unlimited_checkbox = discord.ui.Checkbox(
            custom_id="vc:unlimited",
            default=True,
        )
        self.occupancy_input = discord.ui.TextInput(
            required=False,
            max_length=2,
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
            await send_ephemeral(interaction, msg.MSG_CREATE_FAILED)
            return
        picked = self.kind_select.values
        kind_key = picked[0] if picked else ""
        kind_label = msg.ROOM_KIND_LABELS.get(kind_key)
        if kind_label is None:
            await send_ephemeral(interaction, msg.MSG_KIND_INVALID)
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
        await cog.complete_create_room(
            interaction,
            kind_label=kind_label,
            title=title,
            details=details,
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


def _labeled_block(label: str, value: str) -> str:
    """項目名は太字、値は通常。項目同士は空行で区切る。"""
    return f"**{label}**\n{value}"


def format_capacity(occupied: int, occupancy: int) -> str:
    """募集埋め込み用の人数表示。0 以下は無制限。"""
    if occupancy <= UNLIMITED_OCCUPANCY:
        return f"{occupied}/{msg.MSG_OCCUPANCY_UNLIMITED}"
    return f"{occupied}/{occupancy}"


def recruit_embed(
    *,
    name: str,
    mention: str,
    details: str,
    kind_label: str,
    occupied: int,
    occupancy: int,
    room_mention: str,
    recruiting: bool = True,
) -> discord.Embed:
    """募集チャンネルに出す埋め込み。停止中は参加リンクを出さない。"""
    blocks = [msg.MSG_EMBED_DESCRIPTION.format(mention=mention)]
    if details:
        blocks.append(details)
    status = msg.MSG_EMBED_STATUS_OPEN if recruiting else msg.MSG_EMBED_STATUS_CLOSED
    items = [
        _labeled_block(msg.MSG_EMBED_STATUS, status),
        _labeled_block(msg.MSG_EMBED_KIND, kind_label),
        _labeled_block(msg.MSG_EMBED_CAPACITY, format_capacity(occupied, occupancy)),
    ]
    if recruiting:
        items.append(_labeled_block(msg.MSG_EMBED_ROOM, room_mention))
    blocks.append("\n\n".join(items))
    color = msg.MSG_EMBED_COLOR_OPEN if recruiting else msg.MSG_EMBED_COLOR_CLOSED
    return discord.Embed(title=name, description="\n\n".join(blocks), color=color)


def recruit_embed_for_room(
    room: object,
    *,
    channel_name: str,
    occupied: int,
    room_mention: str,
) -> discord.Embed | None:
    """保存済みメタから募集埋め込みを組み立てる。編集不可の古い部屋は None。"""
    from vc_manager.rooms import Room

    if not isinstance(room, Room) or not room.can_edit:
        return None
    return recruit_embed(
        name=channel_name,
        mention=f"<@{room.owner_id}>",
        details=room.details,
        kind_label=room.kind_label,
        occupied=occupied,
        occupancy=room.occupancy,
        room_mention=room_mention,
        recruiting=room.recruiting,
    )


_OCCUPANCY_IN_DESC = re.compile(
    rf"(\*\*(?:👥 )?人数\*\*|(?:👥 )?人数)\n(\d+)/(\d+|{re.escape(msg.MSG_OCCUPANCY_UNLIMITED)})"
)


def apply_occupied_count(embed: discord.Embed, occupied: int) -> bool:
    """募集埋め込みの現在人数を合わせる。変わったら True。"""
    changed = False
    description = embed.description or ""
    replaced, count = _OCCUPANCY_IN_DESC.subn(
        lambda m: f"{m.group(1)}\n{occupied}/{m.group(3)}",
        description,
        count=1,
    )
    if count and replaced != description:
        embed.description = replaced
        changed = True
    for i, field in enumerate(embed.fields):
        name = field.name or ""
        if name != msg.MSG_EMBED_CAPACITY and not name.endswith("人数"):
            continue
        value = field.value or ""
        if "/" not in value:
            break
        max_part = value.rsplit("/", 1)[-1].strip()
        if not max_part.isdigit() and max_part != msg.MSG_OCCUPANCY_UNLIMITED:
            break
        new_val = f"{occupied}/{max_part}"
        if new_val != value:
            embed.set_field_at(i, name=name, value=new_val, inline=field.inline)
            changed = True
        break
    return changed


def format_duration_ja(seconds: int) -> str:
    """パネル用の待ち時間。60の倍数は分、それ以外は秒。"""
    if seconds <= 0:
        return "すぐ"
    if seconds % 60 == 0:
        return f"{seconds // 60}分"
    return f"{seconds}秒"


def panel_embed() -> discord.Embed:
    note = msg.MSG_PANEL_NOTE.format(
        vacant=format_duration_ja(VACANT_TIMEOUT_SECONDS),
        empty=format_duration_ja(EMPTY_GRACE_SECONDS),
        cooldown=format_duration_ja(CREATE_COOLDOWN_SECONDS),
    )
    description = "\n\n".join(
        [
            msg.MSG_PANEL_DESCRIPTION,
            _labeled_block(msg.MSG_PANEL_FIELD_HOW, msg.MSG_PANEL_HOW),
            _labeled_block(msg.MSG_PANEL_FIELD_NOTE, note),
            _labeled_block(msg.MSG_PANEL_FIELD_EXAMPLE, msg.MSG_PANEL_FOOTER),
        ]
    )
    return discord.Embed(
        title=msg.MSG_PANEL_TITLE,
        description=description,
        color=0x5865F2,
    )


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
