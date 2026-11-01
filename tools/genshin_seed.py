SET_ROWS: list[dict] = [
    {"id": "gladiator", "name_ja": "剣闘士のフィナーレ", "aliases": ["剣闘士", "グラジ"]},
    {"id": "wanderer", "name_ja": "大地を流浪する楽団", "aliases": ["楽団", "流浪"]},
    {"id": "noblesse", "name_ja": "旧貴族のしつけ", "aliases": ["旧貴族", "貴族"]},
    {"id": "maiden", "name_ja": "愛される少女", "aliases": ["少女"]},
    {"id": "viridescent", "name_ja": "翠緑の影", "aliases": ["翠緑", "VV"]},
    {"id": "archaic", "name_ja": "悠久の磐岩", "aliases": ["磐岩"]},
    {"id": "retracing", "name_ja": "逆飛びの流星", "aliases": ["逆飛び", "流星"]},
    {"id": "crimson", "name_ja": "燃え盛る炎の魔女", "aliases": ["炎魔女", "魔女"]},
    {"id": "lavawalker", "name_ja": "烈火を渡る賢者", "aliases": ["烈火"]},
    {"id": "thundering", "name_ja": "雷のような怒り", "aliases": ["如雷"]},
    {"id": "thundersoother", "name_ja": "雷を鎮める尊者", "aliases": ["平雷"]},
    {"id": "blizzard", "name_ja": "氷風を彷徨う勇士", "aliases": ["氷風"]},
    {"id": "heart_of_depth", "name_ja": "沈淪の心", "aliases": ["沈淪"]},
    {"id": "tenacity", "name_ja": "千岩牢固", "aliases": ["千岩"]},
    {"id": "pale_flame", "name_ja": "蒼白の炎", "aliases": ["蒼白"]},
    {"id": "bloodstained", "name_ja": "血染めの騎士道", "aliases": ["血染め"]},
    {"id": "shimenawa", "name_ja": "追憶のしめ縄", "aliases": ["追憶", "しめ縄"]},
    {"id": "emblem", "name_ja": "絶縁の旗印", "aliases": ["絶縁"]},
    {"id": "husk", "name_ja": "華館夢醒形骸記", "aliases": ["華館"]},
    {"id": "ocean_hued", "name_ja": "海染硨磲", "aliases": ["海染"]},
    {"id": "vermillion", "name_ja": "辰砂往生録", "aliases": ["辰砂"]},
    {"id": "echoes", "name_ja": "来歆の余響", "aliases": ["来歆", "余響"]},
    {"id": "deepwood", "name_ja": "深林の記憶", "aliases": ["深林"]},
    {"id": "gilded", "name_ja": "金メッキの夢", "aliases": ["金メッキ"]},
    {"id": "desert", "name_ja": "砂上の楼閣の史話", "aliases": ["楼閣"]},
    {"id": "paradise", "name_ja": "楽園の絶花", "aliases": ["楽園"]},
    {"id": "vourukasha", "name_ja": "花海甘露の光", "aliases": ["花海"]},
    {"id": "nymph", "name_ja": "水仙の夢", "aliases": ["水仙"]},
    {"id": "marechaussee", "name_ja": "ファントムハンター", "aliases": ["ファントム", "狩人"]},
    {"id": "golden_troupe", "name_ja": "黄金の劇団", "aliases": ["黄金劇団", "劇団"]},
    {"id": "song_past", "name_ja": "在りし日の歌", "aliases": ["在りし日"]},
    {"id": "whimsy", "name_ja": "諧律奇想の夜想曲", "aliases": ["諧律", "夜想曲"]},
    {"id": "reverie", "name_ja": "遂げられなかった想い", "aliases": ["想い"]},
    {"id": "obsidian", "name_ja": "黒曜の秘典", "aliases": ["黒曜", "黒曜の魔像"]},
    {"id": "cinder", "name_ja": "灰燼の都に立つ英雄", "aliases": ["灰燼", "巻物"]},
    {"id": "nighttime", "name_ja": "残響の森で囁かれる夜話", "aliases": ["夜話", "残響"]},
    {"id": "deep_galleries", "name_ja": "深廊の終曲", "aliases": ["深廊"]},
    {"id": "long_night", "name_ja": "長き夜の誓い", "aliases": ["長夜", "長夜の誓い"]},
    {"id": "silken_moon", "name_ja": "月を紡ぐ夜の歌", "aliases": ["月歌", "絹月", "紡ぐ夜"]},
    {"id": "sky_unveiling", "name_ja": "天穹の顕現せし夜", "aliases": ["天穹"]},
    {"id": "dawnstar", "name_ja": "暁の星と月の歌", "aliases": ["暁月", "暁の星"]},
    {"id": "rising_winds", "name_ja": "風立ちの日", "aliases": ["風立ち"]},
    {"id": "crimson_oath", "name_ja": "紅血の証", "aliases": ["紅血"]},
    {"id": "furnace_heart", "name_ja": "炉炎溶錬の心", "aliases": ["炉炎", "溶錬"]},
    {"id": "instructor", "name_ja": "教官", "aliases": []},
    {"id": "exile", "name_ja": "亡命者", "aliases": []},
    {"id": "berserker", "name_ja": "狂戦士", "aliases": []},
    {"id": "gambler", "name_ja": "博徒", "aliases": []},
    {"id": "scholar", "name_ja": "学者", "aliases": []},
    {"id": "brave", "name_ja": "勇士の心", "aliases": ["勇士"]},
    {"id": "defender", "name_ja": "守護の心", "aliases": ["守護"]},
    {"id": "sojourner", "name_ja": "旅人の心", "aliases": []},
    {"id": "martial", "name_ja": "武人", "aliases": []},
]

ELEM = {
    "Fire": "pyro",
    "Water": "hydro",
    "Ice": "cryo",
    "Electric": "electro",
    "Wind": "anemo",
    "Rock": "geo",
    "Grass": "dendro",
}

CRIT_ATK = {"crit_rate": 2.0, "crit_dmg": 1.0, "atk_pct": 1.0}
CRIT_HP = {"crit_rate": 2.0, "crit_dmg": 1.0, "hp_pct": 1.0}
CRIT_DEF = {"crit_rate": 2.0, "crit_dmg": 1.0, "def_pct": 1.0}
CRIT_EM = {"crit_rate": 2.0, "crit_dmg": 1.0, "em": 0.25}
ER_CRIT = {"crit_rate": 2.0, "crit_dmg": 1.0, "er": 1.0, "atk_pct": 1.0}
ER_HP = {"er": 1.0, "hp_pct": 1.0, "crit_rate": 2.0, "crit_dmg": 1.0}
EM_ER = {"em": 0.25, "er": 1.0, "hp_pct": 0.5}
HP_HEAL = {"hp_pct": 1.0, "er": 1.0, "healing": 0.0}
DEF_ER = {"def_pct": 1.0, "er": 1.0, "crit_rate": 2.0, "crit_dmg": 1.0}


def b(
    bid: str,
    name: str,
    weights: dict,
    pref: list[str],
    ok: list[str],
    sands: list[str],
    goblet: list[str],
    circlet: list[str],
) -> dict:
    return {
        "id": bid,
        "name_ja": name,
        "weights": weights,
        "sets_preferred": pref,
        "sets_ok": ok,
        "main_sands": sands,
        "main_goblet": goblet,
        "main_circlet": circlet,
    }


def dps(elem: str, pref: list[str], ok: list[str] | None = None, sands: list[str] | None = None) -> list[dict]:
    goblet = [elem, "atk_pct"] if elem not in {"anemo", "geo"} else [elem, "atk_pct"]
    if elem == "anemo":
        goblet = ["anemo", "atk_pct"]
    if elem == "geo":
        goblet = ["geo", "atk_pct"]
    return [
        b(
            "dps",
            "火力",
            CRIT_ATK,
            pref,
            ok or ["gladiator", "wanderer"],
            sands or ["atk_pct"],
            goblet,
            ["crit_rate", "crit_dmg"],
        )
    ]


SPECIAL: dict[str, list[dict]] = {
    "10000037": [  # 甘雨
        b("freeze", "凍結", CRIT_ATK, ["blizzard"], ["noblesse", "gladiator"], ["atk_pct"], ["cryo"], ["crit_rate", "crit_dmg"]),
        b("melt", "溶解", CRIT_ATK, ["wanderer", "shimenawa", "marechaussee"], ["blizzard", "gladiator"], ["atk_pct"], ["cryo"], ["crit_rate", "crit_dmg"]),
    ],
    "10000030": [  # 鍾離
        b("shield", "シールド", {"hp_pct": 1.0, "er": 1.0}, ["tenacity"], ["archaic", "noblesse"], ["hp_pct", "er"], ["hp_pct", "geo"], ["hp_pct"]),
        b("burst", "爆発", CRIT_HP, ["tenacity", "noblesse"], ["archaic"], ["hp_pct", "er"], ["geo", "hp_pct"], ["crit_rate", "crit_dmg", "hp_pct"]),
    ],
    "10000052": [  # 雷電
        b("burst", "爆発", ER_CRIT, ["emblem"], ["thundering"], ["er", "atk_pct"], ["electro", "atk_pct"], ["crit_rate", "crit_dmg"]),
        b("hyperbloom", "超開花", EM_ER, ["paradise", "gilded"], ["thundering", "instructor"], ["em", "er"], ["em"], ["em"]),
    ],
    "10000065": [  # 久岐忍
        b("hyperbloom", "超開花", EM_ER, ["paradise", "gilded"], ["thundering", "instructor"], ["em"], ["em"], ["em"]),
        b("heal", "治療", {"em": 0.25, "hp_pct": 1.0, "er": 1.0}, ["tenacity", "vourukasha"], ["maiden", "ocean_hued"], ["em", "hp_pct", "er"], ["em", "hp_pct"], ["healing", "em", "hp_pct"]),
    ],
    "10000073": [  # ナヒーダ
        b("off", "オフフィールド", CRIT_EM, ["deepwood"], ["gilded", "wanderer"], ["em", "er"], ["em", "dendro"], ["em", "crit_rate", "crit_dmg"]),
        b("on", "オンフィールド", CRIT_EM, ["deepwood", "gilded"], ["wanderer"], ["em", "atk_pct"], ["dendro", "em"], ["crit_rate", "crit_dmg", "em"]),
    ],
    "10000079": [  # ディシア
        b("dps", "火力", CRIT_ATK, ["crimson", "vourukasha", "marechaussee"], ["tenacity"], ["atk_pct", "hp_pct", "er"], ["pyro", "atk_pct"], ["crit_rate", "crit_dmg"]),
        b("tank", "耐久", {"hp_pct": 1.0, "er": 1.0, "atk_pct": 0.5}, ["tenacity", "vourukasha"], ["noblesse"], ["hp_pct", "er"], ["hp_pct", "pyro"], ["hp_pct"]),
    ],
    "10000032": [  # ベネット
        b("support", "サポート", {"er": 1.0, "hp_pct": 1.0}, ["noblesse"], ["emblem", "instructor"], ["er", "hp_pct"], ["hp_pct", "pyro"], ["healing", "hp_pct"]),
        b("dps", "火力", ER_CRIT, ["emblem", "noblesse"], ["crimson"], ["er", "atk_pct"], ["pyro", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000102": [  # ムアラニ
        b("hp", "HP火力", CRIT_HP, ["obsidian"], ["heart_of_depth", "marechaussee"], ["hp_pct", "er"], ["hydro", "hp_pct"], ["crit_rate", "crit_dmg", "hp_pct"]),
    ],
    "10000104": [  # チャスカ
        b("dps", "火力", CRIT_ATK, ["obsidian"], ["viridescent", "wanderer"], ["atk_pct"], ["anemo", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000111": [  # ヴァレサ
        b("dps", "火力", CRIT_ATK, ["long_night", "obsidian"], ["marechaussee", "gladiator"], ["atk_pct"], ["electro", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000114": [  # スカーク
        b("dps", "火力", CRIT_ATK, ["deep_galleries"], ["blizzard", "marechaussee"], ["atk_pct"], ["cryo", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000119": [  # ラウマ
        b("em", "熟知", CRIT_EM, ["deepwood", "dawnstar"], ["gilded", "silken_moon"], ["em", "er"], ["em", "dendro"], ["em", "crit_rate", "crit_dmg"]),
    ],
    "10000120": [  # フリンズ
        b("dps", "火力", CRIT_ATK, ["sky_unveiling"], ["thundering", "gilded"], ["atk_pct", "em"], ["electro", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000122": [  # ネフェル
        b("em", "熟知", CRIT_EM, ["sky_unveiling", "gilded"], ["deepwood", "wanderer"], ["em", "atk_pct"], ["dendro", "em"], ["crit_rate", "crit_dmg", "em"]),
    ],
    "10000123": [  # ドゥリン
        b("support", "サポート", ER_CRIT, ["rising_winds", "noblesse"], ["crimson", "emblem"], ["er", "atk_pct"], ["pyro", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000125": [  # コロンビーナ
        b("hp", "HP火力", CRIT_HP, ["dawnstar", "silken_moon", "sky_unveiling"], ["tenacity", "heart_of_depth"], ["hp_pct", "er", "em"], ["hp_pct", "hydro"], ["crit_rate", "crit_dmg", "hp_pct"]),
    ],
    "10000128": [  # ファルカ
        b("dps", "火力", CRIT_ATK, ["rising_winds"], ["viridescent", "obsidian"], ["atk_pct"], ["anemo", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000133": [  # サンドローネ
        b("dps", "火力", CRIT_ATK, ["furnace_heart"], ["blizzard", "golden_troupe"], ["atk_pct"], ["cryo", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
    "10000140": [  # ヴォジャニーツァ
        b("support", "サポート", {"hp_pct": 1.0, "er": 1.0}, ["tenacity"], ["maiden", "ocean_hued", "noblesse"], ["hp_pct", "er"], ["hp_pct", "hydro"], ["hp_pct", "healing"]),
    ],
    "10000143": [  # ヴェスナ
        b("dps", "火力", CRIT_ATK, ["crimson_oath"], ["rising_winds", "viridescent", "furnace_heart"], ["atk_pct", "em"], ["atk_pct", "anemo"], ["crit_rate", "crit_dmg"]),
    ],
    "10000150": [  # オデット
        b("dps", "火力", CRIT_ATK, ["furnace_heart", "crimson_oath"], ["blizzard", "noblesse"], ["atk_pct", "er"], ["cryo", "atk_pct"], ["crit_rate", "crit_dmg"]),
    ],
}

DEFAULT_PREF = {
    "pyro": ["crimson", "shimenawa", "obsidian", "rising_winds"],
    "hydro": ["heart_of_depth", "nymph", "marechaussee", "dawnstar"],
    "cryo": ["blizzard", "deep_galleries", "furnace_heart", "marechaussee"],
    "electro": ["thundering", "emblem", "sky_unveiling", "obsidian"],
    "anemo": ["viridescent", "rising_winds", "crimson_oath", "obsidian"],
    "geo": ["husk", "cinder", "nighttime", "golden_troupe"],
    "dendro": ["deepwood", "gilded", "sky_unveiling", "paradise"],
}

HP_IDS = {
    "10000046",  # hutao
    "10000060",  # yelan
    "10000089",  # furina
    "10000087",  # neuvillette
    "10000054",  # kokomi
    "10000070",  # nilou
    "10000102",  # mualani
    "10000072",  # candace
    "10000095",  # sigewinne
    "10000014",  # barbara
}
DEF_IDS = {
    "10000057",  # itto
    "10000034",  # noelle
    "10000038",  # albedo
    "10000094",  # chiori
    "10000126",  # zibai
    "10000100",  # kachina
    "10000103",  # xilonen
    "10000055",  # gorou
}
EM_IDS = {
    "10000047",  # kazuha
    "10000043",  # sucrose
    "10000022",  # venti
    "10000081",  # kaveh
    "10000067",  # collei
}
ER_SUPPORT_IDS = {
    "10000023",  # xiangling emblem
    "10000025",  # xingqiu
    "10000012",
    "10000056",  # sara
    "10000064",  # yunjin
    "10000076",  # faruzan
    "10000090",  # chevy
    "10000105",  # ororon
    "10000110",  # iansan
    "10000148",  # alyosha
}

ALIASES: dict[str, list[str]] = {
    "10000052": ["雷電", "将軍", "雷電将軍", "らいでん"],
    "10000046": ["ふーたお", "HuTao", "胡桃"],
    "10000047": ["万葉", "かずは"],
    "10000030": ["しょうり", "鍾離"],
    "10000073": ["ナヒダ", "草神"],
    "10000087": ["ヌビレット", "ヌヴィ"],
    "10000089": ["水神", "フリーナ"],
    "10000075": ["スカラ", "放浪者"],
    "10000033": ["公子", "タルタリヤ", "チャイルド"],
    "10000054": ["心海", "ココミ"],
    "10000057": ["一斗", "荒瀧"],
    "10000002": ["綾華", "あやか"],
    "10000066": ["綾人", "あやと"],
    "10000058": ["神子", "八重"],
    "10000065": ["忍", "くき"],
    "10000106": ["火神", "マーヴィカ"],
    "10000096": ["アルレ", "召使"],
    "10000109": ["瑞希", "夢見月"],
    "10000108": ["ランヤン", "Lan Yan"],
    "10000125": ["コロンビナ", "ダムセレット"],
    "10000126": ["茲白", "Zibai"],
    "10000128": ["ヴァルカ", "Varka"],
    "10000131": ["ニコ・リヤン", "Nicole"],
    "10000133": ["マリオネット", "傀儡"],
    "10000140": ["ヴォジャニツァ", "Vodya", "Vodyanitsa"],
    "10000143": ["ベスナ", "Vesna"],
    "10000150": ["Odette"],
    "10000148": ["Alyosha"],
}

# Enka store にまだ無い実装済みキャラ
EXTRA_CHARS: list[dict] = [
    {"enka_id": "10000125", "id": "columbina", "name_ja": "コロンビーナ", "element": "hydro", "aliases": ["Columbina"]},
    {"enka_id": "10000126", "id": "zibai", "name_ja": "兹白", "element": "geo", "aliases": ["茲白", "Zibai"]},
    {"enka_id": "10000127", "id": "illuga", "name_ja": "イルーガ", "element": "geo", "aliases": ["Illuga"]},
    {"enka_id": "10000128", "id": "varka", "name_ja": "ファルカ", "element": "anemo", "aliases": ["Varka"]},
    {"enka_id": "10000129", "id": "lohen", "name_ja": "ローエン", "element": "cryo", "aliases": ["Lohen"]},
    {"enka_id": "10000130", "id": "linnea", "name_ja": "リンネア", "element": "geo", "aliases": ["Linnea"]},
    {"enka_id": "10000131", "id": "nicole", "name_ja": "ニコ", "element": "pyro", "aliases": ["Nicole"]},
    {"enka_id": "10000132", "id": "prune", "name_ja": "プルーネ", "element": "anemo", "aliases": ["Prune"]},
    {"enka_id": "10000133", "id": "sandrone", "name_ja": "サンドローネ", "element": "cryo", "aliases": ["Sandrone"]},
    {"enka_id": "10000140", "id": "vodyanitsa", "name_ja": "ヴォジャニーツァ", "element": "hydro", "aliases": ["Vodyanitsa"]},
    {"enka_id": "10000143", "id": "vesna", "name_ja": "ヴェスナ", "element": "anemo", "aliases": ["Vesna"]},
    {"enka_id": "10000148", "id": "alyosha", "name_ja": "アリョーシャ", "element": "electro", "aliases": ["Alyosha"]},
    {"enka_id": "10000150", "id": "odette", "name_ja": "オデット", "element": "cryo", "aliases": ["Odette"]},
]


def _id_from_en(en: str, side: str) -> str:
    side_id = side.replace("UI_AvatarIcon_Side_", "").lower()
    special = {
        "qin": "jean",
        "shougun": "raiden",
        "hutao": "hutao",
        "noel": "noelle",
        "tohma": "thoma",
        "yae": "yae_miko",
        "heizo": "heizou",
        "shinobu": "kuki",
        "momoka": "kirara",
        "baizhuer": "baizhu",
        "linette": "lynette",
        "liney": "lyney",
        "liuyun": "xianyun",
        "olorun": "ororon",
        "alhatham": "alhaitham",
        "feiyan": "yanfei",
        "ambor": "amber",
        "skirknew": "skirk",
        "marionettenew": "sandrone",
    }
    return special.get(side_id, side_id)


def _default_builds(enka_id: str, element: str) -> list[dict]:
    if enka_id in SPECIAL:
        return SPECIAL[enka_id]
    pref = DEFAULT_PREF.get(element, ["gladiator"])
    if enka_id in HP_IDS:
        return [
            b("hp", "HP火力", CRIT_HP, pref, ["gladiator", "tenacity"], ["hp_pct", "er"], [element, "hp_pct"], ["crit_rate", "crit_dmg", "hp_pct"])
        ]
    if enka_id in DEF_IDS:
        return [
            b("def", "防御", CRIT_DEF, ["husk", "archaic", "cinder"], ["noblesse", "gladiator"], ["def_pct", "er"], ["geo", "def_pct"], ["crit_rate", "crit_dmg", "def_pct"])
        ]
    if enka_id in EM_IDS:
        return [
            b("em", "熟知", CRIT_EM, ["viridescent", "gilded", "instructor"], ["wanderer"], ["em", "er", "atk_pct"], ["em", element], ["em", "crit_rate", "crit_dmg"])
        ]
    if enka_id in ER_SUPPORT_IDS:
        return [
            b("support", "サポート", ER_CRIT, ["emblem", "noblesse"], pref, ["er", "atk_pct"], [element, "atk_pct"], ["crit_rate", "crit_dmg", "er"])
        ]
    return dps(element, pref)


def _traveler() -> list[dict]:
    variants = [
        ("traveler_anemo", "旅人（風）", "anemo", ["10000005-504", "10000007-704"], ["viridescent"], "anemo"),
        ("traveler_geo", "旅人（岩）", "geo", ["10000005-506", "10000007-706"], ["archaic", "cinder"], "geo"),
        ("traveler_electro", "旅人（雷）", "electro", ["10000005-507", "10000007-707"], ["emblem", "thundering"], "electro"),
        ("traveler_dendro", "旅人（草）", "dendro", ["10000005-508", "10000007-708"], ["deepwood", "gilded"], "dendro"),
        ("traveler_hydro", "旅人（水）", "hydro", ["10000005-503", "10000007-703"], ["nymph", "heart_of_depth"], "hydro"),
        ("traveler_pyro", "旅人（炎）", "pyro", ["10000005-502", "10000007-702"], ["obsidian", "cinder", "crimson"], "pyro"),
        ("traveler_cryo", "旅人（氷）", "cryo", ["10000005-505", "10000007-705"], ["furnace_heart", "blizzard", "crimson_oath"], "cryo"),
    ]
    rows = []
    for cid, name, element, keys, pref, goblet_el in variants:
        rows.append(
            {
                "id": cid,
                "name_ja": name,
                "aliases": ["旅人", "蛍", "空"],
                "element": element,
                "enka_keys": keys,
                "builds": dps(goblet_el, pref),
            }
        )
    return rows
