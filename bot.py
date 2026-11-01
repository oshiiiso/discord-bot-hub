"""おしーそBot 本体。FanCode / BuildCard / VC マネージャを Cog で載せる。"""

from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from config import (
    BOT_DISPLAY_NAME,
    COG_EXTENSIONS,
    GUILD_ID,
    MSG_COMMAND_ERROR,
    MSG_MISSING_PERMISSIONS,
    MSG_NICK_FAILED,
)
from logging_config import get_logger
from replies import send_ephemeral

logger = get_logger(__name__)

intents = discord.Intents.default()
intents.voice_states = True


class HubBot(commands.Bot):
    """複数機能を1プロセスで動かす Bot。"""

    async def setup_hook(self) -> None:
        self.tree.interaction_check = self._restrict_to_configured_guild
        self.tree.on_error = self._on_app_command_error

        for extension in COG_EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("%s をロードしました", extension)
            except Exception:
                logger.exception("%s のロードに失敗しました", extension)

        try:
            if GUILD_ID is not None:
                guild = discord.Object(id=GUILD_ID)
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                logger.info("スラッシュコマンドをサーバー(ID: %s)に%d件同期しました", GUILD_ID, len(synced))
            else:
                synced = await self.tree.sync()
                logger.info("スラッシュコマンドをグローバルに%d件同期しました", len(synced))
        except discord.HTTPException:
            logger.exception("スラッシュコマンドの同期に失敗しました")

    async def _restrict_to_configured_guild(self, interaction: discord.Interaction) -> bool:
        if GUILD_ID is None:
            return True
        return interaction.guild is not None and interaction.guild.id == GUILD_ID

    async def _on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            await send_ephemeral(interaction, MSG_MISSING_PERMISSIONS)
            return
        if isinstance(error, app_commands.CheckFailure):
            return
        cause = error.__cause__ or error
        logger.error("コマンド実行中に例外が発生しました", exc_info=cause)
        await send_ephemeral(interaction, MSG_COMMAND_ERROR)


bot = HubBot(command_prefix=commands.when_mentioned, intents=intents)


@bot.event
async def on_ready() -> None:
    if bot.user is not None:
        logger.info("%s としてログインしました", bot.user)
    if GUILD_ID is None:
        return
    guild = bot.get_guild(GUILD_ID)
    if guild is None or guild.me is None:
        return
    if guild.me.nick == BOT_DISPLAY_NAME:
        return
    try:
        await guild.me.edit(nick=BOT_DISPLAY_NAME)
        logger.info("サーバーニックネームを %s にしました", BOT_DISPLAY_NAME)
    except discord.HTTPException:
        logger.warning(MSG_NICK_FAILED.format(name=BOT_DISPLAY_NAME))
