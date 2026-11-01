"""原神のステータスキーと表示名。"""

STAT_LABELS: dict[str, str] = {
    "hp_flat": "HP",
    "hp_pct": "HP%",
    "atk_flat": "攻撃力",
    "atk_pct": "攻撃力%",
    "def_flat": "防御力",
    "def_pct": "防御力%",
    "em": "元素熟知",
    "er": "元素チャージ効率",
    "crit_rate": "会心率",
    "crit_dmg": "会心ダメージ",
    "healing": "与える治療効果",
    "pyro": "炎元素ダメージ",
    "hydro": "水元素ダメージ",
    "cryo": "氷元素ダメージ",
    "electro": "雷元素ダメージ",
    "anemo": "風元素ダメージ",
    "geo": "岩元素ダメージ",
    "dendro": "草元素ダメージ",
    "physical": "物理ダメージ",
}

PERCENT_KEYS = {
    "hp_pct",
    "atk_pct",
    "def_pct",
    "er",
    "crit_rate",
    "crit_dmg",
    "healing",
    "pyro",
    "hydro",
    "cryo",
    "electro",
    "anemo",
    "geo",
    "dendro",
    "physical",
}

SLOT_LABELS = {
    "flower": "花",
    "feather": "羽",
    "sands": "時計",
    "goblet": "杯",
    "circlet": "冠",
}

FIXED_MAIN_SLOTS = {"flower", "feather"}
ADJUSTED_SLOTS = {"sands", "goblet", "circlet"}

SLOT_FROM_ENKA = {
    "EQUIP_BRACER": "flower",
    "EQUIP_NECKLACE": "feather",
    "EQUIP_SHOES": "sands",
    "EQUIP_RING": "goblet",
    "EQUIP_DRESS": "circlet",
}

ENKA_PROP_TO_KEY = {
    "FIGHT_PROP_HP": "hp_flat",
    "FIGHT_PROP_HP_PERCENT": "hp_pct",
    "FIGHT_PROP_ATTACK": "atk_flat",
    "FIGHT_PROP_ATTACK_PERCENT": "atk_pct",
    "FIGHT_PROP_DEFENSE": "def_flat",
    "FIGHT_PROP_DEFENSE_PERCENT": "def_pct",
    "FIGHT_PROP_ELEMENT_MASTERY": "em",
    "FIGHT_PROP_CHARGE_EFFICIENCY": "er",
    "FIGHT_PROP_CRITICAL": "crit_rate",
    "FIGHT_PROP_CRITICAL_HURT": "crit_dmg",
    "FIGHT_PROP_HEAL_ADD": "healing",
    "FIGHT_PROP_PHYSICAL_ADD_HURT": "physical",
    "FIGHT_PROP_FIRE_ADD_HURT": "pyro",
    "FIGHT_PROP_WATER_ADD_HURT": "hydro",
    "FIGHT_PROP_ICE_ADD_HURT": "cryo",
    "FIGHT_PROP_ELEC_ADD_HURT": "electro",
    "FIGHT_PROP_WIND_ADD_HURT": "anemo",
    "FIGHT_PROP_ROCK_ADD_HURT": "geo",
    "FIGHT_PROP_GRASS_ADD_HURT": "dendro",
}

RATING_THRESHOLDS = (30.0, 40.0, 45.0, 50.0)
RATING_OFFSET_SLOTS = 5.0
BAND_KEYS = ("growing", "ok", "good", "great", "godly")

GENERIC_WEIGHTS = {
    "atk": {"crit_rate": 2.0, "crit_dmg": 1.0, "atk_pct": 1.0},
    "hp": {"crit_rate": 2.0, "crit_dmg": 1.0, "hp_pct": 1.0},
    "def": {"crit_rate": 2.0, "crit_dmg": 1.0, "def_pct": 1.0},
    "em": {"crit_rate": 2.0, "crit_dmg": 1.0, "em": 0.25},
    "er": {"crit_rate": 2.0, "crit_dmg": 1.0, "er": 1.0},
}


_AFFIX_FAMILY = {
    102: "hp_flat",
    103: "hp_pct",
    105: "atk_flat",
    106: "atk_pct",
    108: "def_flat",
    109: "def_pct",
    120: "crit_rate",
    122: "crit_dmg",
    123: "er",
    124: "em",
}


def affix_stat_key(affix_id: int) -> str:
    """Enka の appendPropId からサブステ種別を返す。"""
    family = (int(affix_id) // 10) % 1000
    return _AFFIX_FAMILY.get(family, "")


def format_stat_value(key: str, value: float) -> str:
    """ステ数値を表示用文字列にする。"""
    if key in PERCENT_KEYS:
        return f"{value:.1f}%"
    if key == "em":
        return f"{value:.0f}" if value == int(value) else f"{value:.1f}"
    return f"{value:.0f}" if value == int(value) else f"{value:.1f}"
