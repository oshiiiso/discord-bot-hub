"""/setup のピン留め案内と /formula。"""

from __future__ import annotations

import discord

import messages as msg
from services.copy import t

_LEGACY_GUIDE_FOOTERS = frozenset(
    {"buildcard:guide:genshin", "genshinbuild:guide:genshin", "BuildCard-Bot"}
)


def guide_embed() -> discord.Embed:
    """チャンネル案内。"""
    embed = discord.Embed(
        title=t(msg.MSG_21),
        description=t(msg.MSG_22),
        color=discord.Color.from_rgb(120, 160, 220),
    )
    embed.add_field(name=t(msg.MSG_72), value=t(msg.MSG_73), inline=False)
    embed.add_field(name=t(msg.MSG_18), value=t(msg.MSG_23), inline=False)
    embed.set_footer(text=t(msg.MSG_16))
    return embed


def is_guide_message(message: discord.Message, bot_user_id: int) -> bool:
    """この Bot が立てた案内か。"""
    if message.author.id != bot_user_id or not message.embeds:
        return False
    embed = message.embeds[0]
    footer = embed.footer.text or ""
    return footer == t(msg.MSG_16) or footer in _LEGACY_GUIDE_FOOTERS or (embed.title or "") == t(msg.MSG_21)


def formula_embed() -> discord.Embed:
    """点数の見方。"""
    embed = discord.Embed(
        title=t(msg.MSG_27),
        description=t(msg.MSG_28),
        color=discord.Color.from_rgb(120, 160, 220),
    )
    embed.add_field(name=t(msg.MSG_17), value=t(msg.MSG_29), inline=False)
    return embed
