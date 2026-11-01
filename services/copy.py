"""ユーザー向け文言の組み立て。本文は messages.py。"""

from __future__ import annotations


def t(text: str, **kwargs: object) -> str:
    """プレースホルダを埋める。"""
    if not kwargs:
        return text
    return text.format(**kwargs)
