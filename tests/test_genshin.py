"""スコアとビルドカードの回帰テスト。"""

from games.base import ParsedPiece, ParsedStat
from games.genshin import GenshinGame
from games.genshin.suitability import judge_suitability


def _sample_flower() -> ParsedPiece:
    return ParsedPiece(
        slot="flower",
        set_id="gladiator",
        set_name_ja="剣闘士のフィナーレ",
        main=ParsedStat(key="hp_flat", value=4780, is_percent=False),
        subs=[
            ParsedStat(key="crit_rate", value=3.9, is_percent=True),
            ParsedStat(key="crit_dmg", value=7.8, is_percent=True),
            ParsedStat(key="atk_pct", value=5.8, is_percent=True),
            ParsedStat(key="er", value=6.5, is_percent=True),
        ],
    )


def test_atk_score_formula() -> None:
    game = GenshinGame()
    piece = _sample_flower()
    preset = next(p for p in game.generic_presets() if p.id == "atk")
    result = game.score(piece, preset)
    assert result.total == 21.4


def test_suitability_standard_on_flower() -> None:
    game = GenshinGame()
    piece = _sample_flower()
    hutao = game.get_character("hutao")
    assert hutao is not None
    build = hutao.builds[0]
    suit = judge_suitability(piece, build)
    assert suit.main_mark == "preferred"


def test_messages_load() -> None:
    import messages as msg
    from services.copy import t

    assert msg.MSG_01 == "カードを出す"
    assert "UID" in t(msg.ERR_15)
    assert msg.MSG_RANK["godly"] == "SS"
    assert "Enka" not in msg.MSG_08
    assert "Enka" not in msg.MSG_30
    assert "Enka" not in msg.MSG_49
    assert msg.MSG_77
    assert msg.ERR_20
    assert "Enka" not in msg.ERR_12


def test_start_view_persistent() -> None:
    from config import START_BUTTON_CUSTOM_ID
    from ui.start_view import StartCardView

    view = StartCardView()
    assert view.timeout is None
    assert any(getattr(item, "custom_id", None) == START_BUTTON_CUSTOM_ID for item in view.children)


def test_latest_characters_and_sets() -> None:
    game = GenshinGame()
    assert game.resolve_character("マーヴィカ") is not None
    assert game.resolve_character("コロンビーナ") is not None
    assert game.resolve_character("オデット") is not None
    assert game.resolve_character("ヴェスナ") is not None
    assert game.resolve_character("ヴォジャニーツァ") is not None
    assert game.find_set("月を紡ぐ夜の歌") == "silken_moon"
    assert game.find_set("長き夜の誓い") == "long_night"
    assert game.find_set("紅血の証") == "crimson_oath"
    assert game.find_set("黒曜の秘典") == "obsidian"
    assert game.character_by_enka_key("10000106") is not None
    assert game.character_by_enka_key("10000125") is not None
    vesna = game.character_by_enka_key("10000143")
    assert vesna is not None
    assert vesna.builds[0].id == "dps"
    assert vesna.builds[0].sets_preferred[0] == "crimson_oath"
    vodya = game.character_by_enka_key("10000140")
    assert vodya is not None
    assert vodya.builds[0].id == "support"


def test_scale_from_special_prop() -> None:
    from services.character_learn import scale_from_special

    assert scale_from_special("FIGHT_PROP_HP_PERCENT") == "hp"
    assert scale_from_special("FIGHT_PROP_DEFENSE_PERCENT") == "def"
    assert scale_from_special("FIGHT_PROP_ELEMENT_MASTERY") == "em"
    assert scale_from_special("FIGHT_PROP_CHARGE_EFFICIENCY") == "er"
    assert scale_from_special("FIGHT_PROP_CRITICAL") == "atk"


def test_preferred_sets_from_usage_guide() -> None:
    from services.character_learn import preferred_set_ids, set_id_from_route

    assert set_id_from_route("Scarlet Proof") == "scarlet_proof"
    relics = {"15047": {"id": 15047, "name": "紅血の証"}}
    guide = {
        "azaData": {
            "bestReliquaryList": [
                {"setList": {"15047": 4}, "value": 0.975},
                {"setList": {"15045": 2, "15047": 2}, "value": 0.013},
            ]
        }
    }
    assert preferred_set_ids(guide, relics) == ["crimson_oath"]


def test_preferred_weapon_picks_signature_five_star() -> None:
    from services.character_learn import preferred_weapon_item
    from services.preview_card import weapon_from_yatta

    weapons = {
        "13401": {
            "id": 13401,
            "name": "匣中滅龍",
            "rank": 4,
            "icon": "UI_EquipIcon_Pole_Stardust",
            "specialProp": "FIGHT_PROP_ELEMENT_MASTERY",
        },
        "13501": {
            "id": 13501,
            "name": "護摩の杖",
            "rank": 5,
            "icon": "UI_EquipIcon_Pole_Homa",
            "specialProp": "FIGHT_PROP_CRITICAL_HURT",
        },
    }
    guide = {
        "gwData": {
            "builds": [
                {
                    "info": [
                        {
                            "name": "Best Weapon(s):",
                            "weaponList": {"13401": "Dragon's Bane", "13501": "Staff of Homa"},
                        }
                    ]
                }
            ]
        },
        "azaData": {
            "bestWeaponList": {
                "13401": {"id": 13401, "value": 0.11},
                "13501": {"id": 13501, "value": 0.66},
            }
        },
    }
    item = preferred_weapon_item(guide, weapons)
    assert item is not None
    assert item["name"] == "護摩の杖"
    weapon = weapon_from_yatta(item)
    assert weapon.name_ja == "護摩の杖"
    assert weapon.icon == "UI_EquipIcon_Pole_Homa"
    assert weapon.sub_key == "crit_dmg"


def test_preferred_weapon_from_usage_when_no_guide_text() -> None:
    from services.character_learn import preferred_weapon_item

    weapons = {
        "14402": {
            "id": 14402,
            "name": "流浪楽章",
            "rank": 4,
            "icon": "UI_EquipIcon_Catalyst_Troupe",
            "specialProp": "FIGHT_PROP_CRITICAL_HURT",
        },
        "14521": {
            "id": 14521,
            "name": "真言の匣",
            "rank": 5,
            "icon": "UI_EquipIcon_Catalyst_Sistrum",
            "specialProp": "FIGHT_PROP_CRITICAL_HURT",
        },
    }
    guide = {
        "azaData": {
            "bestWeaponList": {
                "14402": {"id": 14402, "value": 0.2},
                "14521": {"id": 14521, "value": 0.7},
            }
        }
    }
    item = preferred_weapon_item(guide, weapons)
    assert item is not None
    assert item["name"] == "真言の匣"


def test_uid_traveler_matches_each_element() -> None:
    from services.preview_card import dummy_avatar, preview_targets
    from services.enka_client import EnkaClient

    game = GenshinGame()
    pyro = game.character_by_enka_key("10000005-502")
    hydro = game.character_by_enka_key("10000005-503")
    cryo = game.character_by_enka_key("10000005-505")
    electro = game.character_by_enka_key("10000005-507")
    assert pyro is not None and pyro.id == "traveler_pyro" and pyro.name_ja == "旅人（炎）"
    assert hydro is not None and hydro.id == "traveler_hydro" and hydro.name_ja == "旅人（水）"
    assert cryo is not None and cryo.id == "traveler_cryo"
    assert electro is not None and electro.id == "traveler_electro"
    client = EnkaClient()
    client._store = {}
    avatar = dummy_avatar(client, pyro)
    assert avatar is not None
    assert avatar.skill_depot_id == 502
    assert avatar.element == "pyro"
    assert avatar.name_ja == "旅人（炎）"
    ids = [row.id for row in preview_targets() if row.id.startswith("traveler")]
    assert ids == ["traveler_anemo"]


def test_learn_unknown_character(tmp_path) -> None:
    import games.genshin.catalog as catalog
    from games.genshin import GenshinGame
    from services.character_learn import apply_index
    from services.enka_client import EnkaClient

    original = catalog._LEARNED_PATH
    catalog._LEARNED_PATH = tmp_path / "learned_characters.json"
    catalog.refresh_catalog()
    try:
        item = {
            "id": 10000199,
            "name": "テスト風",
            "element": "Wind",
            "icon": "UI_AvatarIcon_Testo",
            "route": "Testo",
            "specialProp": "FIGHT_PROP_CRITICAL",
        }
        assert apply_index({"10000199": item}) == ["テスト風"]
        info = GenshinGame().character_by_enka_key("10000199")
        assert info is not None
        assert info.builds[0].id == "dps"
        client = EnkaClient()
        client._store = {}
        names = client.portrait_names(10000199, 0, None)
        assert "UI_Gacha_AvatarImg_Testo" in names
        assert apply_index({"10000199": item}) == []
        assert apply_index({"10000143": {"id": 10000143, "name": "ヴェスナ", "element": "Wind", "route": "Vesna"}}) == []
    finally:
        catalog._LEARNED_PATH = original
        catalog.refresh_catalog()


def test_learn_unknown_set(tmp_path) -> None:
    import games.genshin.catalog as catalog
    from games.genshin import GenshinGame
    from services.character_learn import apply_sets

    original = catalog._EXTRAS_PATH
    catalog._EXTRAS_PATH = tmp_path / "extras.json"
    catalog.refresh_catalog()
    try:
        names = apply_sets(
            {
                "15999": {
                    "id": 15999,
                    "name": "テストの残響",
                    "route": "Echoes of Test",
                }
            }
        )
        assert names == ["テストの残響"]
        assert GenshinGame().find_set("テストの残響") == "echoes_of_test"
        assert apply_sets({"15999": {"id": 15999, "name": "テストの残響", "route": "Echoes of Test"}}) == []
    finally:
        catalog._EXTRAS_PATH = original
        catalog.refresh_catalog()


def test_fallback_character_uses_generic_builds() -> None:
    game = GenshinGame()
    character = game.fallback_character(10000999, "テスト", "pyro")
    assert character.name_ja == "テスト"
    assert {b.id for b in character.builds} >= {"atk", "hp", "def", "em", "er"}


def test_extra_character_uses_scale() -> None:
    from games.genshin.catalog import extra_character_to_info, valid_set_id

    info = extra_character_to_info(
        {
            "enka_id": "10000999",
            "name_ja": "テスト",
            "element": "geo",
            "scale": "def",
            "aliases": ["Testo"],
        }
    )
    assert info.id == "testo"
    assert info.enka_keys == ["10000999"]
    assert info.builds[0].id == "def"
    assert info.builds[0].weights["def_pct"] == 1.0
    assert valid_set_id("crimson_oath")
    assert not valid_set_id("紅血")
    assert not valid_set_id("1bad")


def test_costume_portrait_skips_missing_gacha_names() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {
        "10000046": {
            "SideIconName": "UI_AvatarIcon_Side_Hutao",
            "Costumes": {
                "204601": {
                    "sideIconName": "UI_AvatarIcon_Side_HutaoCostumeWinter",
                    "icon": "UI_AvatarIcon_HutaoCostumeWinter",
                    "art": "UI_Costume_HutaoCostumeWinter",
                }
            },
        }
    }
    names = client.portrait_names(10000046, 0, 204601)
    assert names[0] == "UI_Costume_HutaoCostumeWinter"
    assert "UI_AvatarIcon_HutaoCostumeWinter" in names
    assert "UI_Gacha_AvatarImg_HutaoCostumeWinter" not in names
    assert "UI_Gacha_AvatarIcon_HutaoCostumeWinter" not in names


def test_traveler_portrait_skips_missing_gacha_names() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {"10000005": {"SideIconName": "UI_AvatarIcon_Side_PlayerBoy"}}
    names = client.portrait_names(10000005, 504, None)
    assert names == ["UI_AvatarIcon_PlayerBoy"]


def test_chiori_portrait_names() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {
        "10000094-10941": {"Element": "Rock"},
        "10000094": {"SideIconName": "UI_AvatarIcon_Side_Chiori"},
    }
    names = client.portrait_names(10000094, 10941, None)
    assert names[0] == "UI_Gacha_AvatarImg_Chiori"
    assert "UI_Gacha_AvatarIcon_Chiori" in names
    assert "UI_AvatarIcon_Chiori" in names
    assert client._icon_for_avatar(10000094, 10941, None) == "UI_AvatarIcon_Chiori"


def test_chiori_portrait_names_without_store() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    names = client.portrait_names(10000094, 0, None)
    assert "UI_Gacha_AvatarIcon_Chiori" in names
    assert "UI_AvatarIcon_Chiori" in names


def test_zibai_portrait_names() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    names = client.portrait_names(10000126, 0, None)
    assert "UI_Gacha_AvatarIcon_Zibai" in names
    assert "UI_AvatarIcon_Zibai" in names


def test_vesna_dummy_preview_card() -> None:
    from services.card_renderer import render_build_card
    from services.enka_client import EnkaClient, EnkaShowcase
    from services.preview_card import dummy_avatar

    game = GenshinGame()
    vesna = game.character_by_enka_key("10000143")
    assert vesna is not None
    client = EnkaClient()
    client._store = {}
    avatar = dummy_avatar(client, vesna)
    assert avatar is not None
    assert avatar.name_ja == "ヴェスナ"
    assert avatar.weapon is not None
    assert avatar.weapon.name_ja
    assert "テスト" not in avatar.weapon.name_ja
    png = render_build_card(
        EnkaShowcase(uid="", nickname="", level=0, avatars=[avatar], ttl=0),
        avatar,
        vesna.builds[0],
        portrait_bytes=None,
        weapon_bytes=None,
    )
    assert png.startswith(b"\x89PNG")


def test_dummy_avatar_uses_preferred_set_and_mains() -> None:
    from games.genshin.catalog import load_characters, relic_icon_name
    from services.enka_client import EnkaClient
    from services.preview_card import dummy_avatar

    game = GenshinGame()
    hutao = game.get_character("hutao")
    assert hutao is not None
    client = EnkaClient()
    client._store = {}
    avatar = dummy_avatar(client, hutao)
    assert avatar is not None
    assert avatar.weapon is not None
    assert avatar.weapon.name_ja == "護摩の杖"
    assert "テスト" not in avatar.weapon.name_ja
    assert {p.set_id for p in avatar.pieces} == {"crimson"}
    by_slot = {p.slot: p for p in avatar.pieces}
    assert by_slot["sands"].main and by_slot["sands"].main.key == "hp_pct"
    assert by_slot["goblet"].main and by_slot["goblet"].main.key == "pyro"
    assert by_slot["flower"].icon == relic_icon_name("crimson", "flower")
    from services.card_renderer import _substat_upgrades

    assert sum(_substat_upgrades(sub.rolls) for sub in by_slot["flower"].subs) == 5
    assert len(by_slot["flower"].subs) == 4
    assert len(load_characters()) >= 100


def test_vesna_portrait_names() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    names = client.portrait_names(10000143, 0, None)
    assert names[0] == "UI_Gacha_AvatarImg_Vesna"
    assert "UI_AvatarIcon_Vesna" in names
    assert client._icon_for_avatar(10000143, 0, None) == "UI_AvatarIcon_Vesna"


def test_zibai_skills_without_store() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    skills = client._skills_for_avatar({}, {"12631": 8, "12632": 6, "12635": 7}, "Zibai")
    assert skills == [
        ("Skill_A_01", 8),
        ("Skill_S_Zibai_01", 6),
        ("Skill_E_Zibai_01", 7),
    ]
    consts = client._const_icons({}, "Zibai")
    assert consts[0] == "UI_Talent_S_Zibai_01"
    assert len(consts) == 6


def _named_piece(slot: str, name: str) -> ParsedPiece:
    return ParsedPiece(slot=slot, set_id=None, set_name_ja=name, main=None, subs=[])


def test_set_layout_partitions() -> None:
    from services.card_renderer import _SLOT_ORDER, _set_layout

    slots = list(_SLOT_ORDER)

    def pcs(*names: str):
        return [_named_piece(slots[i], name) for i, name in enumerate(names)]

    kind, lines, off = _set_layout(pcs("A", "A", "A", "A", "A"))
    assert kind == "match" and lines == [("A", 5)] and off == []

    kind, lines, off = _set_layout(pcs("A", "A", "A", "A", "B"))
    assert kind == "four_one" and lines == [("A", 4)] and [p.set_name_ja for p in off] == ["B"]

    kind, lines, off = _set_layout(pcs("B", "A", "A", "A", "A"))
    assert kind == "four_one" and lines == [("A", 4)]

    kind, lines, off = _set_layout(pcs("A", "A", "A", "B", "B"))
    assert kind == "two_two" and lines == [("A", 3), ("B", 2)] and off == []

    kind, lines, off = _set_layout(pcs("B", "B", "B", "A", "A"))
    assert kind == "two_two" and lines == [("B", 3), ("A", 2)]

    kind, lines, off = _set_layout(pcs("A", "A", "B", "B", "C"))
    assert kind == "two_two_one" and lines == [("A", 2), ("B", 2)] and [p.set_name_ja for p in off] == ["C"]

    kind, lines, off = _set_layout(pcs("A", "A", "A", "B", "C"))
    assert kind == "two" and lines == [("A", 3)] and [p.set_name_ja for p in off] == ["B", "C"]

    kind, lines, off = _set_layout(pcs("A", "A", "B", "C", "D"))
    assert kind == "two" and lines == [("A", 2)] and len(off) == 3

    kind, lines, off = _set_layout(pcs("A", "B", "C", "D", "E"))
    assert kind == "mixed" and lines == []

    kind, lines, off = _set_layout(pcs("A", "A", "A", "A"))
    assert kind == "match" and lines == [("A", 4)]

    kind, lines, off = _set_layout(pcs("A", "A", "B", "B"))
    assert kind == "two_two" and lines == [("A", 2), ("B", 2)] and off == []

    kind, lines, off = _set_layout(pcs("A"))
    assert kind == "none" and lines == []

    assert _set_layout([]) == ("empty", [], [])


def test_set_from_icon_whimsy() -> None:
    from games.genshin.catalog import set_from_icon

    row = set_from_icon("UI_RelicIcon_15035_4")
    assert row is not None
    assert row["name_ja"] == "諧律奇想の断章"


def test_affix_stat_key_crit_and_atk() -> None:
    from games.genshin.stats import affix_stat_key

    assert affix_stat_key(501204) == "crit_rate"
    assert affix_stat_key(501224) == "crit_dmg"
    assert affix_stat_key(501064) == "atk_pct"
    assert affix_stat_key(501234) == "er"


def test_set_layout_icon_only_uses_catalog_name() -> None:
    from services.card_renderer import _set_layout

    pieces = [
        ParsedPiece(slot="flower", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15035_1", main=None, subs=[]),
        ParsedPiece(slot="feather", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15035_2", main=None, subs=[]),
        ParsedPiece(slot="sands", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15035_3", main=None, subs=[]),
        ParsedPiece(slot="goblet", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15035_4", main=None, subs=[]),
        ParsedPiece(slot="circlet", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15001_5", main=None, subs=[]),
    ]
    kind, lines, off = _set_layout(pieces)
    assert kind == "four_one"
    assert lines == [("諧律奇想の断章", 4)]
    assert [p.slot for p in off] == ["circlet"]


def test_set_layout_groups_by_relic_icon() -> None:
    from services.card_renderer import _set_layout

    pieces = [
        ParsedPiece(slot="flower", set_id=None, set_name_ja="剣闘士のフィナーレ", icon="UI_RelicIcon_15001_1", main=None, subs=[]),
        ParsedPiece(slot="feather", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15001_2", main=None, subs=[]),
        ParsedPiece(slot="sands", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15001_3", main=None, subs=[]),
        ParsedPiece(slot="goblet", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15031_4", main=None, subs=[]),
        ParsedPiece(slot="circlet", set_id=None, set_name_ja=None, icon="UI_RelicIcon_15001_5", main=None, subs=[]),
    ]
    kind, lines, off = _set_layout(pieces)
    assert kind == "four_one"
    assert lines == [("剣闘士のフィナーレ", 4)]
    assert [p.slot for p in off] == ["goblet"]


def test_labeled_chip_row_centers_cluster() -> None:
    from PIL import Image, ImageDraw

    from services.card_renderer import _draw_labeled_chip_row, _font

    img = Image.new("RGB", (400, 40), (0, 0, 0))
    draw = ImageDraw.Draw(img)
    _draw_labeled_chip_row(
        draw,
        left=0,
        right=400,
        cy=20,
        label="天穹の顕現せし夜",
        chip="4",
        font_label=_font(18),
        font_chip=_font(14),
        label_fill=(255, 255, 255),
        chip_fill=(0, 0, 0),
        chip_bg=(232, 88, 66),
    )
    xs = [
        x
        for x in range(400)
        if any(img.getpixel((x, y))[0] > 200 and img.getpixel((x, y))[1] < 120 for y in range(40))
    ]
    assert xs
    assert min(xs) > 180
    assert max(xs) < 340


def test_flex_xs_centers_name_and_chip() -> None:
    from services.card_renderer import _flex_xs

    xs = _flex_xs([120, 28], left=0, right=400, gap=8, justify="center")
    start = (400 - (120 + 8 + 28)) / 2
    assert xs[0] == start
    assert xs[1] == start + 128
    assert _flex_xs([80], left=0, right=200, justify="center") == [60]


def test_flex_xs_space_between_and_overflow() -> None:
    from services.card_renderer import _flex_xs

    xs = _flex_xs([40, 20], left=10, right=110, justify="space-between")
    assert xs[0] == 10
    assert xs[1] == 90
    assert _flex_xs([300, 50], left=0, right=200, gap=8, justify="center")[0] == 0
    assert _flex_xs([], left=0, right=100) == []


def test_substat_upgrades_hide_initial_roll() -> None:
    from services.card_renderer import _substat_upgrades

    assert _substat_upgrades(0) == 0
    assert _substat_upgrades(1) == 0
    assert _substat_upgrades(2) == 1
    assert _substat_upgrades(5) == 4
    assert _substat_upgrades(-3) == 0


def test_relic_tile_has_rounded_alpha() -> None:
    from PIL import Image
    from services.card_renderer import _relic_tile

    src = Image.new("RGBA", (64, 64), (200, 80, 40, 255))
    out = _relic_tile(src, 80, (232, 88, 66))
    assert out.size[0] >= 80
    assert out.getpixel((0, 0))[3] < 40
    assert out.getpixel((out.width // 2, out.height // 2))[3] > 80


def test_feather_edges_softens_box() -> None:
    from PIL import Image
    from services.card_renderer import _feather_edges

    src = Image.new("RGBA", (200, 80), (10, 20, 30, 255))
    out = _feather_edges(src, left=0, right=40, top=0, bottom=0)
    assert out.getpixel((199, 40))[3] < 30
    assert out.getpixel((20, 40))[3] > 200
    assert out.getpixel((160, 40))[3] > 200


def test_soften_opaque_box_rounds_corners() -> None:
    from PIL import Image
    from services.card_renderer import _soften_opaque_box

    src = Image.new("RGBA", (200, 200), (10, 20, 30, 255))
    out = _soften_opaque_box(src)
    assert out.getpixel((2, 2))[3] < 80
    assert out.getpixel((100, 100))[3] > 200


def test_fit_portrait_keeps_tall_art() -> None:
    from PIL import Image
    from services.card_renderer import _fit_portrait

    src = Image.new("RGBA", (100, 400), (0, 0, 0, 0))
    src.paste(Image.new("RGBA", (80, 380), (255, 0, 0, 255)), (10, 10))
    out = _fit_portrait(src, (200, 220))
    assert out.size == (200, 220)
    assert out.getpixel((0, 110))[3] < 16
    assert out.getpixel((199, 110))[3] < 16


def test_fit_portrait_keeps_centered_wide_splash() -> None:
    from PIL import Image, ImageDraw
    from services.card_renderer import _fit_portrait

    src = Image.new("RGBA", (400, 200), (0, 0, 0, 0))
    ImageDraw.Draw(src).ellipse((150, 20, 250, 180), fill=(240, 70, 70, 255))
    out = _fit_portrait(src, (200, 150))
    px = out.getpixel((int(out.width * 0.42), out.height // 2))
    assert px[0] > 180 and px[3] > 180
    assert out.getpixel((out.width - 4, out.height // 2))[3] < 40
    assert out.getpixel((4, out.height // 2))[3] < 40


def test_render_card_smoke() -> None:
    from services.card_renderer import render_build_card
    from services.enka_client import EnkaAvatar, EnkaShowcase

    game = GenshinGame()
    hutao = game.get_character("hutao")
    assert hutao is not None
    piece = _sample_flower()
    avatar = EnkaAvatar(
        avatar_id=10000046,
        skill_depot_id=0,
        name_ja=hutao.name_ja,
        icon="",
        level=90,
        constellations=6,
        friendship=10,
        character=hutao,
        pieces=[piece],
        weapon=None,
        stats={"hp": 30000, "atk": 2000, "def": 800, "em": 100, "er": 120, "crit_rate": 80, "crit_dmg": 200},
        element="pyro",
    )
    png = render_build_card(
        EnkaShowcase(uid="1", nickname="tester", level=60, avatars=[avatar], ttl=60),
        avatar,
        hutao.builds[0],
        portrait_bytes=None,
        weapon_bytes=None,
    )
    assert png.startswith(b"\x89PNG")


def test_render_card_draws_weapon_without_name() -> None:
    from services.card_renderer import render_build_card
    from services.enka_client import EnkaAvatar, EnkaShowcase, EnkaWeapon

    game = GenshinGame()
    hutao = game.get_character("hutao")
    assert hutao is not None
    avatar = EnkaAvatar(
        avatar_id=10000046,
        skill_depot_id=0,
        name_ja=hutao.name_ja,
        icon="",
        level=90,
        constellations=0,
        friendship=10,
        character=hutao,
        pieces=[_sample_flower()],
        weapon=EnkaWeapon(name_ja="", level=90, refine=1, icon="", rarity=5, base_atk=608),
        stats={"hp": 30000, "atk": 2000, "def": 800, "em": 100, "er": 120, "crit_rate": 80, "crit_dmg": 200},
        element="pyro",
    )
    png = render_build_card(
        EnkaShowcase(uid="1", nickname="tester", level=60, avatars=[avatar], ttl=60),
        avatar,
        hutao.builds[0],
        portrait_bytes=None,
        weapon_bytes=None,
    )
    assert png.startswith(b"\x89PNG")


def test_uid_pick_empty_name_keeps_select_label() -> None:
    import discord

    import messages as msg
    from games.genshin import GenshinGame
    from services.copy import t
    from services.enka_client import EnkaAvatar
    from services.session_store import SessionStore, UidSession
    from ui.uid_view import UidPickView

    class _Cog:
        def __init__(self) -> None:
            self.sessions = SessionStore()

    game = GenshinGame()
    character = game.fallback_character(10000999, t(msg.MSG_57), "pyro")
    avatars = [
        EnkaAvatar(
            avatar_id=10000999,
            skill_depot_id=0,
            name_ja="",
            icon="",
            level=90,
            constellations=0,
            friendship=1,
            character=character,
            pieces=[],
            weapon=None,
        )
        for _ in range(12)
    ]
    cog = _Cog()
    cog.sessions.put(1, UidSession(user_id=1, uid="123456789", nickname="t", avatars=avatars))
    view = UidPickView(cog, 1)  # type: ignore[arg-type]
    select = next(child for child in view.children if isinstance(child, discord.ui.Select))
    assert all(1 <= len(option.label) <= 100 for option in select.options)


def test_uid_pick_has_refresh() -> None:
    import messages as msg
    from services.copy import t
    from services.session_store import SessionStore, UidSession
    from ui.uid_view import UidPickView

    class _Cog:
        def __init__(self) -> None:
            self.sessions = SessionStore()

    cog = _Cog()
    cog.sessions.put(1, UidSession(user_id=1, uid="123456789", nickname="t", avatars=[]))
    view = UidPickView(cog, 1)  # type: ignore[arg-type]
    labels = [getattr(item, "label", None) for item in view.children]
    assert t(msg.MSG_55) in labels
    assert t(msg.MSG_74) in labels


def test_all_characters_have_portrait_and_build() -> None:
    from services.character_check import collect_rows, problem_rows
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    rows = collect_rows(client)
    assert rows
    assert problem_rows(rows) == []


def test_cleanup_enka_assets_drops_old_and_empty(tmp_path) -> None:
    import os
    import time

    from services.enka_client import cleanup_enka_assets

    keep = tmp_path / "keep.png"
    old = tmp_path / "old.png"
    empty = tmp_path / "empty.png"
    keep.write_bytes(b"abc")
    old.write_bytes(b"abc")
    empty.write_bytes(b"")
    now = time.time()
    os.utime(old, (now - 40 * 86400, now - 40 * 86400))
    assert cleanup_enka_assets(tmp_path, 30, now=now) == 2
    assert keep.exists()
    assert not old.exists()
    assert not empty.exists()


def test_cleanup_enka_assets_skips_when_disabled(tmp_path) -> None:
    from services.enka_client import cleanup_enka_assets

    path = tmp_path / "keep.png"
    path.write_bytes(b"abc")
    assert cleanup_enka_assets(tmp_path, 0) == 0
    assert path.exists()


def test_parse_weapon_without_loc_keeps_icon() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    client._loc_ja = {}
    raw = {
        "avatarId": 10000046,
        "skillDepotId": 0,
        "skillLevelMap": {},
        "propMap": {"4001": {"val": "90"}},
        "fightPropMap": {"2000": 1},
        "fetterInfo": {"expLevel": 10},
        "equipList": [
            {
                "weapon": {"level": 90, "affixMap": {"14512": 0}},
                "flat": {
                    "itemType": "ITEM_WEAPON",
                    "icon": "UI_EquipIcon_Pole_Homa",
                    "rankLevel": 5,
                    "weaponStats": [{"appendPropId": "FIGHT_PROP_BASE_ATTACK", "statValue": 608}],
                },
            }
        ],
    }
    avatar = client._parse_avatar(GenshinGame(), raw)
    assert avatar.weapon is not None
    assert avatar.weapon.icon == "UI_EquipIcon_Pole_Homa"
    assert avatar.weapon.level == 90
    assert avatar.weapon.refine == 1
    assert avatar.weapon.base_atk == 608


def test_parse_avatar_keeps_skills_after_artifact_rolls() -> None:
    from services.enka_client import EnkaClient

    client = EnkaClient()
    client._store = {}
    client._loc_ja = {}
    raw = {
        "avatarId": 10000046,
        "skillDepotId": 0,
        "skillLevelMap": {"10341": 8, "10342": 6, "10345": 7},
        "propMap": {"4001": {"val": "90"}},
        "fightPropMap": {"2000": 30000, "20": 0.8, "22": 2.0, "23": 1.2},
        "fetterInfo": {"expLevel": 10},
        "talentIdList": [1, 2, 3],
        "equipList": [
            {
                "flat": {
                    "equipType": "EQUIP_BRACER",
                    "icon": "UI_RelicIcon_15001_1",
                    "rankLevel": 5,
                    "reliquarySubstats": [
                        {"appendPropId": "FIGHT_PROP_CRITICAL", "statValue": 3.9},
                        {"appendPropId": "FIGHT_PROP_CRITICAL_HURT", "statValue": 7.8},
                    ],
                },
                "reliquary": {"level": 21, "appendPropIdList": [501204, 501224, 501204]},
            }
        ],
    }
    avatar = client._parse_avatar(GenshinGame(), raw)
    assert avatar.level == 90
    assert avatar.friendship == 10
    assert avatar.constellations == 3
    assert avatar.pieces[0].subs[0].rolls == 2
    assert avatar.pieces[0].subs[1].rolls == 1
    assert avatar.name_ja


def test_download_icon_rejects_unsafe_names() -> None:
    import asyncio

    from services.enka_client import EnkaClient

    client = EnkaClient()

    async def check() -> None:
        assert await client.download_icon("../etc/passwd") is None
        assert await client.download_icon("..") is None
        assert await client.download_icon("a/b") is None
        assert await client.download_icon("") is None

    asyncio.run(check())
