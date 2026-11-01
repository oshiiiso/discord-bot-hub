"""スコアと定番判定の型。"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CharacterBuild:
    """キャラ1ビルド分のウェイトと定番装備。"""

    id: str
    name_ja: str
    weights: dict[str, float]
    sets_preferred: list[str] = field(default_factory=list)
    sets_ok: list[str] = field(default_factory=list)
    main_sands: list[str] = field(default_factory=list)
    main_goblet: list[str] = field(default_factory=list)
    main_circlet: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CharacterInfo:
    """ゲーム内キャラ1人。"""

    id: str
    name_ja: str
    aliases: list[str]
    element: str
    builds: list[CharacterBuild]
    enka_keys: list[str] = field(default_factory=list)


@dataclass
class ParsedStat:
    """メインまたはサブ1本。"""

    key: str
    value: float
    is_percent: bool
    rolls: int = 0


@dataclass
class ParsedPiece:
    """Enka から読んだ装備1個。"""

    slot: str | None
    set_id: str | None
    set_name_ja: str | None
    main: ParsedStat | None
    subs: list[ParsedStat]
    rarity: int | None = None
    level: int | None = None
    icon: str | None = None


@dataclass(frozen=True)
class ScoreResult:
    """サブステ加重スコア。"""

    total: float
    per_stat: dict[str, float]
    band_key: str


@dataclass(frozen=True)
class Suitability:
    """セットとメインの定番判定。"""

    set_mark: str | None
    main_mark: str | None
    overall_key: str | None
    color_key: str
