"""交換コード通知。スラッシュは /fancode グループ。"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta

import discord
from discord import app_commands
from discord.ext import commands, tasks

from config import MSG_COMMAND_ERROR
from fancode import messages as msg
from fancode.addition_notices import resume_pending_addition_notices
from fancode.checker import get_game_channel, run_check_all_games
from fancode.config import CHECK_INTERVAL_HOURS, GAME_CONFIG
from fancode.embeds import create_list_embed
from fancode.storage import (
    delete_game_files,
    load_codes_data,
    load_history,
    load_last_check,
    remove_pending_addition_notices_for_channel,
)
from logging_config import get_logger
from replies import defer_ephemeral, send_ephemeral

logger = get_logger(__name__)

GAME_CHOICES = [app_commands.Choice(name=msg.MSG_CHOICE_ALL, value="all")] + [
    app_commands.Choice(name=cfg["name"], value=key) for key, cfg in GAME_CONFIG.items()
]
GAME_ONLY_CHOICES = [
    app_commands.Choice(name=cfg["name"], value=key) for key, cfg in GAME_CONFIG.items()
]


class FanCodeCog(commands.Cog):
    """Wiki から交換コードを取り、固定メッセージを更新する。"""

    fancode = app_commands.Group(name="fancode", description=msg.MSG_GROUP_DESCRIPTION)

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def cog_load(self) -> None:
        if not self.check_all_games_loop.is_running():
            self.check_all_games_loop.start()

    async def cog_unload(self) -> None:
        if self.check_all_games_loop.is_running():
            self.check_all_games_loop.cancel()

    @tasks.loop(hours=CHECK_INTERVAL_HOURS)
    async def check_all_games_loop(self) -> None:
        try:
            await run_check_all_games(self.bot)
        except Exception:
            logger.exception("定期チェックに失敗しました")

    @check_all_games_loop.before_loop
    async def before_check_all_games_loop(self) -> None:
        """起動直後に1回チェックし、1時間間隔なら毎時00分に揃える。"""
        await self.bot.wait_until_ready()
        logger.info("起動直後の交換コードチェックを実行します")
        try:
            await run_check_all_games(self.bot)
        except Exception:
            logger.exception("起動直後の交換コードチェックに失敗しました")
        try:
            resume_pending_addition_notices(self.bot)
        except Exception:
            logger.exception("追加通知の再開に失敗しました")

        now = datetime.now()
        if CHECK_INTERVAL_HOURS == 1:
            next_run = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        else:
            next_run = now + timedelta(hours=CHECK_INTERVAL_HOURS)
        wait_seconds = max(0, (next_run - now).total_seconds())
        logger.debug("次回の交換コードチェックまで %s 秒待機します", int(wait_seconds))
        await asyncio.sleep(wait_seconds)

    @fancode.command(name="clear", description=msg.MSG_CMD_CLEAR)
    @app_commands.describe(target=msg.MSG_OPT_TARGET, amount=msg.MSG_OPT_AMOUNT)
    @app_commands.choices(target=GAME_CHOICES)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def clear_messages(
        self,
        interaction: discord.Interaction,
        target: str = "all",
        amount: int = 100,
    ) -> None:
        if not await defer_ephemeral(interaction):
            return
        amount = max(1, min(amount, 100))

        targets = GAME_CONFIG.items() if target == "all" else (
            [(target, GAME_CONFIG[target])] if target in GAME_CONFIG else []
        )
        if not targets:
            await send_ephemeral(interaction, msg.MSG_UNKNOWN_GAME.format(target=target))
            return

        for key, game_config in targets:
            channel = await get_game_channel(self.bot, game_config["channel_id"])
            if not channel:
                logger.warning("%s のチャンネルが見つかりません", game_config["name"])
                continue
            try:
                deleted = await channel.purge(limit=amount)
                logger.info("%s でメッセージを %s 件削除しました", channel.name, len(deleted))
            except Exception:
                logger.exception("%s の削除中に例外が発生しました", channel.name)

            for filename in delete_game_files(key):
                logger.debug("%s を削除しました", filename)
            remove_pending_addition_notices_for_channel(game_config["channel_id"])

        scope = msg.MSG_SCOPE_ALL if target == "all" else GAME_CONFIG[target]["name"]
        await send_ephemeral(interaction, msg.MSG_CLEAR_DONE.format(scope=scope))

    @fancode.command(name="check", description=msg.MSG_CMD_CHECK)
    @app_commands.checks.has_permissions(manage_messages=True)
    async def manual_check(self, interaction: discord.Interaction) -> None:
        if not await defer_ephemeral(interaction):
            return
        try:
            await run_check_all_games(self.bot)
        except Exception:
            logger.exception("手動チェックに失敗しました")
            await send_ephemeral(interaction, MSG_COMMAND_ERROR)
            return
        await send_ephemeral(interaction, msg.MSG_CHECK_DONE)

    @fancode.command(name="ping", description=msg.MSG_CMD_PING)
    async def ping(self, interaction: discord.Interaction) -> None:
        await send_ephemeral(
            interaction,
            msg.MSG_PING.format(ms=round(self.bot.latency * 1000)),
        )

    @fancode.command(name="status", description=msg.MSG_CMD_STATUS)
    async def status(self, interaction: discord.Interaction) -> None:
        try:
            await self._send_status(interaction)
        except Exception:
            logger.exception("稼働状況の表示に失敗しました")
            await send_ephemeral(interaction, MSG_COMMAND_ERROR)

    async def _send_status(self, interaction: discord.Interaction) -> None:
        now = datetime.now()
        lines: list[str] = []
        for key, cfg in GAME_CONFIG.items():
            last_check = load_last_check(key)
            codes_data = load_codes_data(key)
            count = len(codes_data)

            if last_check:
                next_check = last_check + timedelta(hours=CHECK_INTERVAL_HOURS)
                remaining = (next_check - now).total_seconds()
                last_str = last_check.strftime("%Y-%m-%d %H:%M")
                if remaining > 0:
                    remaining_min = int(remaining // 60)
                    next_str = f"あと約{remaining_min}分"
                else:
                    next_str = "まもなく実行"
            else:
                last_str = "未実行"
                next_str = "不明"

            lines.append(
                f"**【{cfg['name']}】** 有効コード {count}件 ｜ 最終確認: {last_str} ｜ 次回チェック: {next_str}"
            )

        embed = discord.Embed(
            title=msg.MSG_STATUS_TITLE,
            description="\n".join(lines),
            color=0x3498DB,
        )
        embed.timestamp = now
        await send_ephemeral(interaction, embed=embed)

    @fancode.command(name="codes", description=msg.MSG_CMD_CODES)
    @app_commands.describe(target=msg.MSG_OPT_TARGET_ONE)
    @app_commands.choices(target=GAME_ONLY_CHOICES)
    async def codes(self, interaction: discord.Interaction, target: str) -> None:
        try:
            cfg = GAME_CONFIG.get(target)
            if not cfg:
                await send_ephemeral(interaction, msg.MSG_UNKNOWN_GAME.format(target=target))
                return
            codes_data = load_codes_data(target)
            embed = create_list_embed(cfg["name"], codes_data, cfg)
            await send_ephemeral(interaction, embed=embed)
        except Exception:
            logger.exception("コード一覧の表示に失敗しました")
            await send_ephemeral(interaction, MSG_COMMAND_ERROR)

    @fancode.command(name="history", description=msg.MSG_CMD_HISTORY)
    @app_commands.describe(target=msg.MSG_OPT_TARGET_ONE, count=msg.MSG_OPT_COUNT)
    @app_commands.choices(target=GAME_ONLY_CHOICES)
    async def history(self, interaction: discord.Interaction, target: str, count: int = 10) -> None:
        try:
            await self._send_history(interaction, target, count)
        except Exception:
            logger.exception("履歴の表示に失敗しました")
            await send_ephemeral(interaction, MSG_COMMAND_ERROR)

    async def _send_history(self, interaction: discord.Interaction, target: str, count: int) -> None:
        cfg = GAME_CONFIG.get(target)
        if not cfg:
            await send_ephemeral(interaction, msg.MSG_UNKNOWN_GAME.format(target=target))
            return

        count = max(1, min(count, 20))
        entries = load_history(target)[-count:]
        if not entries:
            await send_ephemeral(interaction, msg.MSG_NO_HISTORY.format(name=cfg["name"]))
            return

        lines: list[str] = []
        for entry in reversed(entries):
            if not isinstance(entry, dict):
                continue
            try:
                ts = datetime.fromisoformat(str(entry["timestamp"])).strftime("%Y-%m-%d %H:%M")
            except (KeyError, TypeError, ValueError):
                ts = "不明"
            label = msg.MSG_HISTORY_ADDED if entry.get("type") == "added" else msg.MSG_HISTORY_REMOVED
            codes = entry.get("codes") or []
            if not isinstance(codes, list):
                continue
            code_str = ", ".join(f"`{c}`" for c in codes)
            lines.append(f"{ts} ｜ {label} ｜ {code_str}")
        if not lines:
            await send_ephemeral(interaction, msg.MSG_NO_HISTORY.format(name=cfg["name"]))
            return

        embed = discord.Embed(
            title=msg.MSG_HISTORY_TITLE.format(name=cfg["name"], count=len(lines)),
            description="\n".join(lines),
            color=cfg["color"],
        )
        await send_ephemeral(interaction, embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FanCodeCog(bot))
