"""ユーザー操作への返信。失敗しても例外を外に出さない。"""

from __future__ import annotations

import asyncio

import discord

from config import EPHEMERAL_DELETE_SECONDS, MSG_WORKING
from logging_config import get_logger

logger = get_logger(__name__)

# defer の「考え中」を使わず、操作中メッセージを出した interaction.token
_working_tokens: set[str] = set()
_delete_tasks: dict[str, asyncio.Task[None]] = {}


def _edit_kwargs(content: str | None, kwargs: dict[str, object]) -> dict[str, object]:
    """followup.send 向けの引数を edit_original_response 向けに直す。"""
    out = dict(kwargs)
    out.pop("ephemeral", None)
    file = out.pop("file", None)
    files = out.pop("files", None)
    if file is not None or files is not None:
        attachments = list(files or [])
        if file is not None:
            attachments.insert(0, file)
        out["attachments"] = attachments
    return {"content": content, **out}


_AUTO_DELETE_TYPES = (
    discord.InteractionType.application_command,
    discord.InteractionType.modal_submit,
    discord.InteractionType.component,
)


def _keeps_ephemeral(
    interaction: discord.Interaction,
    content: str | None,
    persist: bool,
    kwargs: dict[str, object],
) -> bool:
    """数秒で消さず残す返信なら True。"""
    if persist or EPHEMERAL_DELETE_SECONDS <= 0:
        return True
    if interaction.type not in _AUTO_DELETE_TYPES:
        return True
    if content == MSG_WORKING:
        return True
    if kwargs.get("view") is not None:
        return True
    if kwargs.get("file") is not None or kwargs.get("files") is not None:
        return True
    if kwargs.get("attachments") is not None:
        return True
    if kwargs.get("embed") is not None or kwargs.get("embeds") is not None:
        return True
    return False


def _cancel_delete(key: str) -> None:
    task = _delete_tasks.pop(key, None)
    if task is not None:
        task.cancel()


def _schedule_original_delete(
    interaction: discord.Interaction,
    content: str | None,
    persist: bool,
    kwargs: dict[str, object],
) -> None:
    key = interaction.token
    _cancel_delete(key)
    if _keeps_ephemeral(interaction, content, persist, kwargs):
        return

    async def _delete_later() -> None:
        try:
            await asyncio.sleep(EPHEMERAL_DELETE_SECONDS)
            await interaction.delete_original_response()
        except asyncio.CancelledError:
            raise
        except discord.HTTPException:
            logger.debug("エフェメラルの削除をスキップしました")
        finally:
            _delete_tasks.pop(key, None)

    _delete_tasks[key] = asyncio.create_task(_delete_later())


def _schedule_message_delete(message: discord.Message) -> None:
    key = f"m:{message.id}"
    _cancel_delete(key)

    async def _delete_later() -> None:
        try:
            await asyncio.sleep(EPHEMERAL_DELETE_SECONDS)
            await message.delete()
        except asyncio.CancelledError:
            raise
        except discord.HTTPException:
            logger.debug("エフェメラルの削除をスキップしました")
        finally:
            _delete_tasks.pop(key, None)

    _delete_tasks[key] = asyncio.create_task(_delete_later())


async def send_ephemeral(
    interaction: discord.Interaction,
    content: str | None = None,
    *,
    persist: bool = False,
    **kwargs: object,
) -> None:
    """エフェメラルで返す。操作中ならそのメッセージを上書きする。"""
    try:
        if interaction.response.is_done():
            if interaction.token in _working_tokens:
                _working_tokens.discard(interaction.token)
                await interaction.edit_original_response(**_edit_kwargs(content, kwargs))
                _schedule_original_delete(interaction, content, persist, kwargs)
                return
            kwargs.setdefault("ephemeral", True)
            if _keeps_ephemeral(interaction, content, persist, kwargs):
                await interaction.followup.send(content, **kwargs)
                return
            message = await interaction.followup.send(content, wait=True, **kwargs)
            _schedule_message_delete(message)
            return
        kwargs.setdefault("ephemeral", True)
        await interaction.response.send_message(content, **kwargs)
        _schedule_original_delete(interaction, content, persist, kwargs)
    except discord.HTTPException:
        logger.warning("エフェメラル返信に失敗しました")


async def defer_ephemeral(interaction: discord.Interaction) -> bool:
    """時間のかかる処理の前に「操作中」を出す。既に応答済みなら成功扱い。"""
    if interaction.response.is_done():
        return True
    try:
        await interaction.response.send_message(MSG_WORKING, ephemeral=True)
        _working_tokens.add(interaction.token)
        return True
    except discord.HTTPException:
        logger.warning("応答予約に失敗しました")
        return False


async def edit_original(
    interaction: discord.Interaction,
    *,
    persist: bool = False,
    **kwargs: object,
) -> None:
    _working_tokens.discard(interaction.token)
    try:
        await interaction.edit_original_response(**kwargs)
        content = kwargs.get("content")
        content_text = content if isinstance(content, str) else None
        _schedule_original_delete(interaction, content_text, persist, kwargs)
    except discord.HTTPException:
        logger.warning("元メッセージの更新に失敗しました")


async def delete_ephemeral(interaction: discord.Interaction) -> None:
    """操作の元エフェメラルを消す。既に無いなら無視する。"""
    _cancel_delete(interaction.token)
    _working_tokens.discard(interaction.token)
    try:
        await interaction.delete_original_response()
    except discord.HTTPException:
        logger.debug("エフェメラルの削除をスキップしました")
