"""交換コード投稿の権限チェック。"""

from types import SimpleNamespace

from fancode.checker import _post_permission_warning


def test_post_permission_warning_when_send_denied() -> None:
    perms = SimpleNamespace(view_channel=True, send_messages=False, embed_links=True)
    channel = SimpleNamespace(
        name="genshin-codes",
        guild=SimpleNamespace(me=object()),
        permissions_for=lambda _me: perms,
    )
    warning = _post_permission_warning(channel, "原神")
    assert warning is not None
    assert "原神" in warning
    assert "メッセージを送信" in warning


def test_post_permission_warning_when_ok() -> None:
    perms = SimpleNamespace(view_channel=True, send_messages=True, embed_links=True)
    channel = SimpleNamespace(
        name="genshin-codes",
        guild=SimpleNamespace(me=object()),
        permissions_for=lambda _me: perms,
    )
    assert _post_permission_warning(channel, "原神") is None
