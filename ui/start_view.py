"""カード開始ボタンと UID 入力 Modal。再起動後も同じ custom_id で動く。"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import discord

import messages as msg
from config import START_BUTTON_CUSTOM_ID
from logging_config import get_logger
from replies import send_ephemeral
from services.copy import t

logger = get_logger(__name__)

if TYPE_CHECKING:
    from cogs.buildcard import BuildCog


class StartCardView(discord.ui.View):
    """案内ピンと、カードの下に出す開始ボタン。"""

    def __init__(self) -> None:
        super().__init__(timeout=None)
        self.add_item(_StartButton())


class _StartButton(discord.ui.Button):
    def __init__(self) -> None:
        super().__init__(
            label=t(msg.MSG_01),
            style=discord.ButtonStyle.primary,
            custom_id=START_BUTTON_CUSTOM_ID,
        )

    async def callback(self, interaction: discord.Interaction) -> None:
        try:
            cog = _build_cog(interaction)
            if cog is None:
                await send_ephemeral(interaction, t(msg.ERR_12))
                return
            if not cog.in_bot_channel(interaction.channel):
                await send_ephemeral(interaction, t(msg.ERR_02))
                return
            await interaction.response.send_modal(UidModal())
        except discord.HTTPException:
            logger.warning("カード開始の応答に失敗しました")
        except Exception:
            logger.exception("カード開始ボタンの処理に失敗しました")
            await send_ephemeral(interaction, t(msg.ERR_12))


class UidModal(discord.ui.Modal):
    """UID 入力。"""

    def __init__(self) -> None:
        super().__init__(title=t(msg.MSG_24)[:45])
        self.uid_input = discord.ui.TextInput(
            label=t(msg.MSG_25)[:45],
            placeholder=t(msg.MSG_26),
            min_length=8,
            max_length=20,
            required=True,
        )
        self.add_item(self.uid_input)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        cog = _build_cog(interaction)
        if cog is None:
            await send_ephemeral(interaction, t(msg.ERR_12))
            return
        await cog.begin_uid(interaction, str(self.uid_input.value))

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        logger.exception("UID 入力の処理に失敗しました")
        await send_ephemeral(interaction, t(msg.ERR_12))


def _build_cog(interaction: discord.Interaction) -> BuildCog | None:
    cog = interaction.client.get_cog("BuildCog")
    if cog is None:
        return None
    return cast("BuildCog", cog)
