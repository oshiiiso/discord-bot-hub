"""操作中メッセージの上書き用引数。"""

from types import SimpleNamespace

import discord

from config import MSG_WORKING
from replies import _edit_kwargs, _keeps_ephemeral


def test_edit_kwargs_drops_ephemeral_and_maps_file() -> None:
    file = object()
    out = _edit_kwargs("完了", {"ephemeral": True, "file": file})
    assert out["content"] == "完了"
    assert "ephemeral" not in out
    assert "file" not in out
    assert out["attachments"] == [file]


def test_keeps_command_receipt_is_deleted() -> None:
    interaction = SimpleNamespace(type=discord.InteractionType.application_command)
    assert _keeps_ephemeral(interaction, "Pong! 12ms", False, {}) is False


def test_keeps_modal_receipt_is_deleted() -> None:
    interaction = SimpleNamespace(type=discord.InteractionType.modal_submit)
    assert _keeps_ephemeral(interaction, "部屋を作ったよ。そちらに移したよ", False, {}) is False


def test_keeps_embed_and_view_and_working() -> None:
    interaction = SimpleNamespace(type=discord.InteractionType.application_command)
    assert _keeps_ephemeral(interaction, "一覧", False, {"embed": object()}) is True
    assert _keeps_ephemeral(interaction, "選んでね", False, {"view": object()}) is True
    assert _keeps_ephemeral(interaction, MSG_WORKING, False, {}) is True
    modal = SimpleNamespace(type=discord.InteractionType.modal_submit)
    assert _keeps_ephemeral(modal, "リンクから入ってね", True, {"view": object()}) is True


def test_keeps_component_receipt_is_deleted() -> None:
    interaction = SimpleNamespace(type=discord.InteractionType.component)
    assert _keeps_ephemeral(interaction, "部屋に入ったよ", False, {}) is False
    assert _keeps_ephemeral(interaction, "このリンクから", True, {}) is True
