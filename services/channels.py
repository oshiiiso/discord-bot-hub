"""Bot 用チャンネルかどうか。"""

from __future__ import annotations

from config import CHANNEL_ID


def is_bot_channel(channel_id: int) -> bool:
    """設定したテキストチャンネルなら True。"""
    return CHANNEL_ID != 0 and channel_id == CHANNEL_ID
