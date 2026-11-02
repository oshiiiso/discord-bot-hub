"""募集埋め込みの参加ボタン。再起動後も custom_id から復元する。"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, cast

import discord

from logging_config import get_logger
from replies import send_ephemeral
from vc_manager import messages as msg

if TYPE_CHECKING:
    from cogs.vc_manager import VcManagerCog

logger = get_logger(__name__)


class VcJoinButton(
    discord.ui.DynamicItem[discord.ui.Button],
    template=r"vc:join:(?P<channel_id>[0-9]+)",
):
    """緑の参加ボタン。リンクボタンは Discord が灰色固定なので使わない。"""

    def __init__(self, channel_id: int) -> None:
        super().__init__(
            discord.ui.Button(
                label=msg.MSG_JOIN_BUTTON,
                style=discord.ButtonStyle.success,
                emoji=msg.MSG_JOIN_BUTTON_EMOJI,
                custom_id=f"vc:join:{channel_id}",
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
    ) -> VcJoinButton:
        return cls(int(match["channel_id"]))

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            cog = interaction.client.get_cog("VcManagerCog")
            if cog is None:
                await send_ephemeral(interaction, msg.MSG_ROOM_GONE)
                return
            await cast("VcManagerCog", cog).join_managed_room(interaction, self.channel_id)
        except Exception:
            logger.exception("参加ボタンの処理に失敗しました channel_id=%s", self.channel_id)
            await send_ephemeral(interaction, msg.MSG_INVITE_FAILED)
