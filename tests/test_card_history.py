"""ビルドカード履歴の保存。"""

from pathlib import Path

from services.card_history import HISTORY_MAX, CardHistoryStore, HistoryEntry


def test_remember_dedupes_and_caps(tmp_path: Path) -> None:
    store = CardHistoryStore(path=tmp_path / "history.json", max_entries=HISTORY_MAX)
    for index in range(6):
        store.remember(
            10,
            uid=f"80000000{index}",
            nickname=f"N{index}",
            avatar_id=1000 + index,
            skill_depot_id=1,
            character_name_ja=f"キャラ{index}",
            build_id="dps",
            build_name_ja="火力",
        )
    rows = store.list_for(10)
    assert len(rows) == HISTORY_MAX
    assert rows[0].uid.endswith("5")
    assert rows[-1].uid.endswith("1")

    store.remember(
        10,
        uid="800000001",
        nickname="更新",
        avatar_id=1001,
        skill_depot_id=1,
        character_name_ja="キャラ1",
        build_id="dps",
        build_name_ja="火力",
    )
    rows = store.list_for(10)
    assert len(rows) == HISTORY_MAX
    assert rows[0].nickname == "更新"
    assert rows[0].uid.endswith("1")
    assert sum(1 for row in rows if row.uid.endswith("1")) == 1


def test_history_is_per_user_and_clearable(tmp_path: Path) -> None:
    path = tmp_path / "history.json"
    store = CardHistoryStore(path=path, max_entries=5)
    store.remember(
        1,
        uid="812345678",
        nickname="A",
        avatar_id=100,
        skill_depot_id=2,
        character_name_ja="蛍",
        build_id=None,
    )
    store.remember(
        2,
        uid="876543210",
        nickname="B",
        avatar_id=200,
        skill_depot_id=3,
        character_name_ja="空",
        build_id="support",
        build_name_ja="サポ",
    )
    assert len(store.list_for(1)) == 1
    assert len(store.list_for(2)) == 1
    store.clear(1)
    assert store.list_for(1) == []
    assert len(store.list_for(2)) == 1

    reloaded = CardHistoryStore(path=path, max_entries=5)
    assert reloaded.list_for(1) == []
    assert reloaded.list_for(2)[0].character_name_ja == "空"
    assert reloaded.list_for(2)[0].key.endswith(":support")


def test_history_entry_key_distinguishes_build() -> None:
    base = HistoryEntry(
        uid="812345678",
        nickname="A",
        avatar_id=100,
        skill_depot_id=1,
        character_name_ja="雷電将軍",
        build_id="dps",
    )
    other = HistoryEntry(
        uid="812345678",
        nickname="A",
        avatar_id=100,
        skill_depot_id=1,
        character_name_ja="雷電将軍",
        build_id="support",
    )
    assert base.key != other.key


def test_unique_uid_entries_keeps_newest() -> None:
    from ui.history_view import unique_uid_entries

    rows = [
        HistoryEntry("111", "新A", 1, 1, "キャラ1"),
        HistoryEntry("222", "B", 2, 1, "キャラ2"),
        HistoryEntry("111", "旧A", 3, 1, "キャラ3"),
    ]
    unique = unique_uid_entries(rows)
    assert [row.uid for row in unique] == ["111", "222"]
    assert unique[0].nickname == "新A"


def test_find_history_avatar_prefers_skill_depot() -> None:
    from types import SimpleNamespace

    from cogs.buildcard import BuildCog
    from services.card_history import HistoryEntry

    avatars = [
        SimpleNamespace(avatar_id=100, skill_depot_id=1, name_ja="A"),
        SimpleNamespace(avatar_id=100, skill_depot_id=2, name_ja="B"),
    ]
    entry = HistoryEntry(
        uid="1",
        nickname="n",
        avatar_id=100,
        skill_depot_id=2,
        character_name_ja="B",
    )
    found = BuildCog._find_history_avatar(avatars, entry)  # type: ignore[arg-type]
    assert found is not None
    assert found[0] == 1
    assert found[1].name_ja == "B"
