"""追加コード通知メッセージの期限削除（再起動後も継続）。"""
import asyncio
from datetime import datetime, timedelta, timezone

import discord

from .config import ADDITION_NOTICE_LIFETIME_SECONDS
from .logger_setup import debug_log, info_log
from .storage import (
    add_pending_addition_notice,
    load_pending_addition_notices,
    remove_pending_addition_notice,
)

# 同じメッセージに対する削除タスクの重複起動を防ぐ
_scheduled_message_ids: set[int] = set()


def _parse_delete_at(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        delete_at = datetime.fromisoformat(value)
    except ValueError:
        return None
    if delete_at.tzinfo is None:
        delete_at = delete_at.replace(tzinfo=timezone.utc)
    return delete_at


async def _try_delete_notice(bot: discord.Client, channel_id: int, message_id: int) -> bool:
    """通知メッセージを削除する。記録を消してよい場合は True。"""
    try:
        channel = bot.get_channel(channel_id)
        if channel is None:
            channel = await bot.fetch_channel(channel_id)
        message = await channel.fetch_message(message_id)
        await message.delete()
        debug_log(f"追加コード通知メッセージを削除しました (id={message_id})。")
        return True
    except discord.NotFound:
        return True
    except discord.Forbidden:
        info_log(f"[警告] 追加コード通知メッセージの削除権限がありません (id={message_id})。")
        return True
    except Exception as e:
        info_log(f"[エラー] 追加コード通知メッセージの削除に失敗しました (id={message_id}): {e}")
        return False


async def _run_notice_delete(bot: discord.Client, channel_id: int, message_id: int, delete_at: datetime) -> None:
    try:
        delay = (delete_at - datetime.now(timezone.utc)).total_seconds()
        if delay > 0:
            await asyncio.sleep(delay)
        should_drop = await _try_delete_notice(bot, channel_id, message_id)
        if should_drop:
            remove_pending_addition_notice(message_id)
    except asyncio.CancelledError:
        raise
    finally:
        _scheduled_message_ids.discard(message_id)


def _schedule_notice_delete(bot: discord.Client, channel_id: int, message_id: int, delete_at: datetime) -> None:
    if message_id in _scheduled_message_ids:
        return
    _scheduled_message_ids.add(message_id)
    try:
        asyncio.get_running_loop().create_task(
            _run_notice_delete(bot, channel_id, message_id, delete_at)
        )
    except RuntimeError:
        _scheduled_message_ids.discard(message_id)
        info_log(f"[警告] 追加コード通知の削除タスクを組めませんでした (id={message_id})。")


def register_addition_notice(bot: discord.Client, message: discord.Message) -> None:
    """投稿した追加通知を、期限後に削除するよう登録する。"""
    delete_at = datetime.now(timezone.utc) + timedelta(seconds=ADDITION_NOTICE_LIFETIME_SECONDS)
    add_pending_addition_notice(message.channel.id, message.id, delete_at)
    _schedule_notice_delete(bot, message.channel.id, message.id, delete_at)


def resume_pending_addition_notices(bot: discord.Client) -> None:
    """保存済みの削除予定を読み込み、期限到来分から削除を再開する。"""
    for entry in load_pending_addition_notices():
        channel_id = entry.get("channel_id")
        message_id = entry.get("message_id")
        delete_at = _parse_delete_at(entry.get("delete_at"))
        if not isinstance(channel_id, int) or not isinstance(message_id, int) or delete_at is None:
            if isinstance(message_id, int):
                remove_pending_addition_notice(message_id)
            continue
        _schedule_notice_delete(bot, channel_id, message_id, delete_at)
