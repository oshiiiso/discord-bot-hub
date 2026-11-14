"""募集部屋のメンバー操作。作成者または移動権限者が Bot 経由で退出／移動する。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, TypeVar, cast

import discord

from config import VIEW_TIMEOUT_SECONDS
from logging_config import get_logger
from replies import send_ephemeral
from vc_manager import messages as msg
from vc_manager.rooms import Room

if TYPE_CHECKING:
    from cogs.vc_manager import VcManagerCog

logger = get_logger(__name__)

PAGE_SIZE = 25
_LABEL_MAX = 100
_T = TypeVar("_T")


def page_count(total: int, size: int = PAGE_SIZE) -> int:
    """0 件でも 1 ページとして扱う。"""
    if total <= 0:
        return 1
    return (total + size - 1) // size


def clamp_page(page: int, total: int, size: int = PAGE_SIZE) -> int:
    last = page_count(total, size) - 1
    return max(0, min(page, last))


def slice_page(items: list[_T], page: int, size: int = PAGE_SIZE) -> list[_T]:
    start = clamp_page(page, len(items), size) * size
    return items[start : start + size]


def can_manage_members(
    actor: discord.Member,
    room: Room,
    channel: discord.VoiceChannel,
) -> bool:
    """作成者、またはその VC でメンバー移動できる人。"""
    if actor.id == room.owner_id:
        return True
    perms = channel.permissions_for(actor)
    return bool(perms.administrator or perms.move_members)


def bot_can_move(channel: discord.abc.GuildChannel, me: discord.Member | None) -> bool:
    if me is None:
        return False
    perms = channel.permissions_for(me)
    return bool(perms.administrator or perms.move_members)


def list_operable_members(
    channel: discord.VoiceChannel,
    actor_id: int,
) -> list[discord.Member]:
    """操作対象。Bot と操作者本人は除外。"""
    members = [
        member
        for member in channel.members
        if not member.bot and member.id != actor_id
    ]
    members.sort(key=lambda m: (m.display_name.lower(), m.id))
    return members


def list_move_destinations(
    guild: discord.Guild,
    source_id: int,
) -> list[discord.VoiceChannel]:
    """同一ギルドの VoiceChannel。今の部屋と Stage は除外。"""
    channels = [
        channel
        for channel in guild.voice_channels
        if channel.id != source_id and isinstance(channel, discord.VoiceChannel)
    ]
    channels.sort(
        key=lambda c: (
            c.category.position if c.category is not None else -1,
            c.position,
            c.name.lower(),
            c.id,
        )
    )
    return channels


def _member_label(member: discord.Member) -> str:
    return (member.display_name or member.name or str(member.id))[:_LABEL_MAX]


def _member_desc(member: discord.Member) -> str:
    name = member.name or str(member.id)
    return f"@{name}"[:100]


def _channel_label(channel: discord.VoiceChannel) -> str:
    return channel.name[:_LABEL_MAX]


def _channel_desc(channel: discord.VoiceChannel) -> str:
    if channel.category is not None:
        return channel.category.name[:100]
    return "カテゴリなし"


def _page_text(page: int, total_items: int) -> str:
    total_pages = page_count(total_items)
    return msg.MSG_MANAGE_PAGE.format(current=page + 1, total=total_pages)


class VcManageButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:manage:(?P<channel_id>[0-9]+)",
):
    """作成者／移動権限者がメンバーを退出・移動できる。"""

    def __init__(self, channel_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_MANAGE_BUTTON,
                style=discord.ButtonStyle.secondary,
                emoji=msg.MSG_MANAGE_BUTTON_EMOJI,
                custom_id=f"vc:manage:{channel_id}",
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
    ) -> VcManageButton:
        return cls(int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            cog = _vc_cog(interaction)
            if cog is None:
                await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
                return
            await cog.open_member_manage(interaction, self.channel_id)
        except Exception:
            logger.exception("メンバー操作ボタンの処理に失敗しました channel_id=%s", self.channel_id)
            await send_ephemeral(interaction, msg.MSG_MANAGE_FAILED)


class MemberPickView(discord.ui.View):
    """部屋内メンバーの選択。25 人超はページ切替。"""

    def __init__(
        self,
        cog: VcManagerCog,
        *,
        channel_id: int,
        actor_id: int,
        members: list[discord.Member],
        page: int = 0,
    ) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.cog = cog
        self.channel_id = channel_id
        self.actor_id = actor_id
        self.members = list(members)
        self.page = clamp_page(page, len(self.members))
        options = [
            discord.SelectOption(
                label=_member_label(member),
                value=str(member.id),
                description=_member_desc(member),
            )
            for member in slice_page(self.members, self.page)
        ]
        if options:
            self.add_item(_MemberSelect(self, options))
        total_pages = page_count(len(self.members))
        if total_pages > 1:
            self.add_item(_PageButton(self, direction=-1, disabled=self.page <= 0))
            self.add_item(_PageButton(self, direction=1, disabled=self.page >= total_pages - 1))

    def content(self) -> str:
        if not self.members:
            return msg.MSG_MANAGE_EMPTY
        return f"{msg.MSG_MANAGE_PICK_MEMBER}\n{_page_text(self.page, len(self.members))}"

    async def _ensure_actor(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await send_ephemeral(interaction, msg.MSG_MANAGE_FORBIDDEN)
            return False
        return True


class ActionPickView(discord.ui.View):
    """退出／移動の選択。"""

    def __init__(
        self,
        cog: VcManagerCog,
        *,
        channel_id: int,
        actor_id: int,
        target: discord.Member,
        members: list[discord.Member],
        page: int,
    ) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.cog = cog
        self.channel_id = channel_id
        self.actor_id = actor_id
        self.target = target
        self.members = list(members)
        self.page = page
        self.add_item(_KickButton(self))
        self.add_item(_MoveButton(self))
        self.add_item(_BackToMembersButton(self))

    def content(self) -> str:
        return msg.MSG_MANAGE_PICK_ACTION.format(name=_member_label(self.target))

    async def _ensure_actor(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await send_ephemeral(interaction, msg.MSG_MANAGE_FORBIDDEN)
            return False
        return True


class DestPickView(discord.ui.View):
    """移動先 VoiceChannel の選択。"""

    def __init__(
        self,
        cog: VcManagerCog,
        *,
        channel_id: int,
        actor_id: int,
        target: discord.Member,
        destinations: list[discord.VoiceChannel],
        members: list[discord.Member],
        member_page: int,
        page: int = 0,
    ) -> None:
        super().__init__(timeout=VIEW_TIMEOUT_SECONDS)
        self.cog = cog
        self.channel_id = channel_id
        self.actor_id = actor_id
        self.target = target
        self.destinations = list(destinations)
        self.members = list(members)
        self.member_page = member_page
        self.page = clamp_page(page, len(self.destinations))
        options = [
            discord.SelectOption(
                label=_channel_label(channel),
                value=str(channel.id),
                description=_channel_desc(channel),
            )
            for channel in slice_page(self.destinations, self.page)
        ]
        if options:
            self.add_item(_DestSelect(self, options))
        total_pages = page_count(len(self.destinations))
        if total_pages > 1:
            self.add_item(_DestPageButton(self, direction=-1, disabled=self.page <= 0))
            self.add_item(_DestPageButton(self, direction=1, disabled=self.page >= total_pages - 1))
        self.add_item(_BackToActionButton(self))

    def content(self) -> str:
        return (
            f"{msg.MSG_MANAGE_PICK_DEST.format(name=_member_label(self.target))}\n"
            f"{_page_text(self.page, len(self.destinations))}"
        )

    async def _ensure_actor(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.actor_id:
            await send_ephemeral(interaction, msg.MSG_MANAGE_FORBIDDEN)
            return False
        return True


class _MemberSelect(discord.ui.Select):
    def __init__(self, parent: MemberPickView, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder=msg.MSG_MANAGE_SELECT_MEMBER,
            options=options,
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        try:
            user_id = int(self.values[0])
        except ValueError:
            await send_ephemeral(interaction, msg.MSG_MANAGE_FAILED)
            return
        target = next((m for m in self.parent_view.members if m.id == user_id), None)
        if target is None:
            await send_ephemeral(interaction, msg.MSG_MANAGE_TARGET_GONE)
            return
        view = ActionPickView(
            self.parent_view.cog,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            target=target,
            members=self.parent_view.members,
            page=self.parent_view.page,
        )
        try:
            await interaction.response.edit_message(content=view.content(), view=view)
        except discord.HTTPException:
            logger.warning("メンバー操作の操作選択表示に失敗しました")


class _PageButton(discord.ui.Button):
    def __init__(self, parent: MemberPickView, *, direction: int, disabled: bool) -> None:
        label = msg.MSG_MANAGE_PREV if direction < 0 else msg.MSG_MANAGE_NEXT
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )
        self.parent_view = parent
        self.direction = direction

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        view = MemberPickView(
            self.parent_view.cog,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            members=self.parent_view.members,
            page=self.parent_view.page + self.direction,
        )
        try:
            await interaction.response.edit_message(content=view.content(), view=view)
        except discord.HTTPException:
            logger.warning("メンバー操作のページ切替に失敗しました")


class _KickButton(discord.ui.Button):
    def __init__(self, parent: ActionPickView) -> None:
        super().__init__(label=msg.MSG_MANAGE_KICK, style=discord.ButtonStyle.danger)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        await self.parent_view.cog.manage_eject_member(
            interaction,
            channel_id=self.parent_view.channel_id,
            user_id=self.parent_view.target.id,
        )


class _MoveButton(discord.ui.Button):
    def __init__(self, parent: ActionPickView) -> None:
        super().__init__(label=msg.MSG_MANAGE_MOVE, style=discord.ButtonStyle.primary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        channel = await self.parent_view.cog.resolve_voice_channel(self.parent_view.channel_id)
        if channel is None:
            await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
            return
        destinations = list_move_destinations(channel.guild, channel.id)
        if not destinations:
            await send_ephemeral(interaction, msg.MSG_MANAGE_NO_DEST)
            return
        view = DestPickView(
            self.parent_view.cog,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            target=self.parent_view.target,
            destinations=destinations,
            members=self.parent_view.members,
            member_page=self.parent_view.page,
        )
        try:
            await interaction.response.edit_message(content=view.content(), view=view)
        except discord.HTTPException:
            logger.warning("メンバー操作の移動先表示に失敗しました")


class _BackToMembersButton(discord.ui.Button):
    def __init__(self, parent: ActionPickView) -> None:
        super().__init__(label=msg.MSG_MANAGE_BACK, style=discord.ButtonStyle.secondary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        await self.parent_view.cog.refresh_member_pick(
            interaction,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            page=self.parent_view.page,
        )


class _DestSelect(discord.ui.Select):
    def __init__(self, parent: DestPickView, options: list[discord.SelectOption]) -> None:
        super().__init__(
            placeholder=msg.MSG_MANAGE_SELECT_DEST,
            options=options,
            min_values=1,
            max_values=1,
        )
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        try:
            dest_id = int(self.values[0])
        except ValueError:
            await send_ephemeral(interaction, msg.MSG_MANAGE_FAILED)
            return
        await self.parent_view.cog.manage_move_member(
            interaction,
            channel_id=self.parent_view.channel_id,
            user_id=self.parent_view.target.id,
            dest_id=dest_id,
        )


class _DestPageButton(discord.ui.Button):
    def __init__(self, parent: DestPickView, *, direction: int, disabled: bool) -> None:
        label = msg.MSG_MANAGE_PREV if direction < 0 else msg.MSG_MANAGE_NEXT
        super().__init__(
            label=label,
            style=discord.ButtonStyle.secondary,
            disabled=disabled,
        )
        self.parent_view = parent
        self.direction = direction

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        view = DestPickView(
            self.parent_view.cog,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            target=self.parent_view.target,
            destinations=self.parent_view.destinations,
            members=self.parent_view.members,
            member_page=self.parent_view.member_page,
            page=self.parent_view.page + self.direction,
        )
        try:
            await interaction.response.edit_message(content=view.content(), view=view)
        except discord.HTTPException:
            logger.warning("移動先のページ切替に失敗しました")


class _BackToActionButton(discord.ui.Button):
    def __init__(self, parent: DestPickView) -> None:
        super().__init__(label=msg.MSG_MANAGE_BACK, style=discord.ButtonStyle.secondary)
        self.parent_view = parent

    async def callback(self, interaction: discord.Interaction) -> None:
        if not await self.parent_view._ensure_actor(interaction):
            return
        view = ActionPickView(
            self.parent_view.cog,
            channel_id=self.parent_view.channel_id,
            actor_id=self.parent_view.actor_id,
            target=self.parent_view.target,
            members=self.parent_view.members,
            page=self.parent_view.member_page,
        )
        try:
            await interaction.response.edit_message(content=view.content(), view=view)
        except discord.HTTPException:
            logger.warning("メンバー操作への戻りに失敗しました")


def _vc_cog(interaction: discord.Interaction) -> VcManagerCog | None:
    cog = interaction.client.get_cog("VcManagerCog")
    if cog is None:
        return None
    return cast("VcManagerCog", cog)
