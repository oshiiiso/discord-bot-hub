"""VC マネージャの部屋名と保存。"""

from pathlib import Path

from vc_manager.create_view import (
    apply_occupied_count,
    format_capacity,
    format_duration_ja,
    panel_embed,
    recruit_embed,
)
from vc_manager.messages import (
    MSG_EMBED_KIND,
    MSG_EMBED_ROOM,
    MSG_OCCUPANCY_UNLIMITED,
    MSG_PANEL_FIELD_EXAMPLE,
    MSG_PANEL_FIELD_HOW,
    MSG_PANEL_FIELD_NOTE,
    MSG_PANEL_TITLE,
    MSG_ROOM_KINDS,
    ROOM_KIND_LABELS,
)
from vc_manager.rooms import (
    Room,
    clip_plain,
    composed_room_name,
    load_rooms,
    parse_occupancy,
    sanitize_channel_name,
    save_rooms,
    unique_channel_name,
    vacant_remaining_seconds,
)


def test_sanitize_channel_name_uses_custom() -> None:
    assert sanitize_channel_name("Among Us 初心者") == "Among Us 初心者"


def test_composed_room_name_joins_parts() -> None:
    assert composed_room_name("原神", "聖遺物厳選") == "原神-聖遺物厳選"


def test_composed_room_name_skips_empty_title() -> None:
    assert composed_room_name("原神", "") == "原神"


def test_composed_room_name_game_only() -> None:
    assert composed_room_name("Among Us", "") == "Among Us"


def test_composed_room_name_truncates_to_100() -> None:
    name = composed_room_name("原神", "あ" * 120)
    assert name.startswith("原神-")
    assert len(name) <= 100


def test_unique_channel_name_increments() -> None:
    assert unique_channel_name("原神", set()) == "原神"
    assert unique_channel_name("原神", {"原神"}) == "原神-1"
    assert unique_channel_name("原神", {"原神", "原神-1"}) == "原神-2"


def test_clip_plain_keeps_newlines_and_drops_controls() -> None:
    assert clip_plain("  a\x00b  ", 10) == "ab"
    assert clip_plain("a\n\n\nb", 10, keep_newlines=True) == "a\n\nb"


def test_room_kinds_include_requested_labels() -> None:
    labels = [label for _key, label in MSG_ROOM_KINDS]
    assert labels == ["原神", "ゼンゼロ", "スタレ", "鳴潮", "VALORANT", "Among Us", "雑談", "その他"]
    assert ROOM_KIND_LABELS["amongus"] == "Among Us"
    assert ROOM_KIND_LABELS["chat"] == "雑談"


def test_parse_occupancy_default_and_range() -> None:
    assert parse_occupancy("") is None
    assert parse_occupancy(" 8 ") == 8
    assert parse_occupancy("1") == 1
    assert parse_occupancy("15") == 15
    assert parse_occupancy("99") == 99
    assert parse_occupancy("１５") == 15
    assert parse_occupancy("８") == 8
    assert parse_occupancy("0") is None
    assert parse_occupancy("100") is None
    assert parse_occupancy("abc") is None
    assert parse_occupancy("１５人") is None
    assert parse_occupancy("1.5") is None


def test_save_and_load_rooms(tmp_path: Path) -> None:
    path = tmp_path / "vc_rooms.json"
    room = Room(
        voice_channel_id=1,
        guild_id=2,
        message_id=3,
        recruit_channel_id=4,
        invite_url="https://discord.gg/test",
        owner_id=5,
    )
    save_rooms({1: room}, path=path)
    loaded = load_rooms(path)
    assert loaded[1] == room
    assert loaded[1].occupied_once is False
    assert loaded[1].created_at == 0.0


def test_load_rooms_occupied_once_defaults_false(tmp_path: Path) -> None:
    path = tmp_path / "vc_rooms.json"
    path.write_text(
        '[{"voice_channel_id": 1, "guild_id": 2, "message_id": 3,'
        ' "recruit_channel_id": 4, "invite_url": "https://discord.gg/test",'
        ' "owner_id": 5}]',
        encoding="utf-8",
    )
    loaded = load_rooms(path)
    assert loaded[1].occupied_once is False
    assert loaded[1].created_at == 0.0
    assert loaded[1].card_message_id == 0


def test_format_duration_ja() -> None:
    assert format_duration_ja(0) == "すぐ"
    assert format_duration_ja(10) == "10秒"
    assert format_duration_ja(30) == "30秒"
    assert format_duration_ja(300) == "5分"


def test_panel_embed_explains_flow() -> None:
    embed = panel_embed()
    assert embed.title == MSG_PANEL_TITLE
    description = embed.description or ""
    assert f"**{MSG_PANEL_FIELD_HOW}**" in description
    assert f"**{MSG_PANEL_FIELD_NOTE}**" in description
    assert f"**{MSG_PANEL_FIELD_EXAMPLE}**" in description
    assert "5分" in description
    assert "10秒" in description
    assert "原神-探索" in description
    assert embed.fields == []


def test_format_capacity_unlimited() -> None:
    assert format_capacity(0, 0) == f"0/{MSG_OCCUPANCY_UNLIMITED}"
    assert format_capacity(3, 0) == f"3/{MSG_OCCUPANCY_UNLIMITED}"
    assert format_capacity(3, 15) == "3/15"


def test_recruit_embed_includes_details_and_join() -> None:
    with_details = recruit_embed(
        name="原神-聖遺物厳選",
        mention="<@1>",
        details="世界ランク60 / 夜まで",
        kind_label="原神",
        occupied=1,
        occupancy=15,
        room_mention="<#2>",
    )
    description = with_details.description or ""
    assert "<@1> が部屋を作りました" in description
    assert "世界ランク60 / 夜まで" in description
    assert f"**{MSG_EMBED_KIND}**\n原神" in description
    assert "**👥 人数**\n1/15" in description
    assert f"**{MSG_EMBED_ROOM}**\n<#2>" in description
    assert description.index("世界ランク60 / 夜まで") < description.index(MSG_EMBED_KIND)
    assert with_details.fields == []

    without = recruit_embed(
        name="原神-聖遺物厳選",
        mention="<@1>",
        details="",
        kind_label="原神",
        occupied=0,
        occupancy=0,
        room_mention="<#2>",
    )
    assert f"**👥 人数**\n0/{MSG_OCCUPANCY_UNLIMITED}" in (without.description or "")


def test_apply_occupied_count_updates_description() -> None:
    embed = recruit_embed(
        name="原神-聖遺物厳選",
        mention="<@1>",
        details="",
        kind_label="原神",
        occupied=0,
        occupancy=15,
        room_mention="<#2>",
    )
    assert apply_occupied_count(embed, 3) is True
    assert "**👥 人数**\n3/15" in (embed.description or "")
    assert apply_occupied_count(embed, 3) is False

    unlimited = recruit_embed(
        name="雑談",
        mention="<@1>",
        details="",
        kind_label="雑談",
        occupied=0,
        occupancy=0,
        room_mention="<#2>",
    )
    assert apply_occupied_count(unlimited, 2) is True
    assert f"**👥 人数**\n2/{MSG_OCCUPANCY_UNLIMITED}" in (unlimited.description or "")


def test_apply_occupied_count_updates_legacy_field() -> None:
    embed = recruit_embed(
        name="原神-聖遺物厳選",
        mention="<@1>",
        details="",
        kind_label="原神",
        occupied=1,
        occupancy=8,
        room_mention="<#2>",
    )
    embed.description = "<@1> が部屋を作りました"
    embed.clear_fields()
    embed.add_field(name="人数", value="1/8", inline=True)
    embed.add_field(name="参加する", value="https://discord.gg/test", inline=False)
    assert apply_occupied_count(embed, 4) is True
    assert embed.fields[0].value == "4/8"


def test_vacant_remaining_seconds() -> None:
    assert vacant_remaining_seconds(0, now=1000.0, timeout=300) == 300
    assert vacant_remaining_seconds(900.0, now=1000.0, timeout=300) == 200
    assert vacant_remaining_seconds(600.0, now=1000.0, timeout=300) == -100
