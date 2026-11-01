"""セットとメインの定番判定。"""

from __future__ import annotations

from games.base import CharacterBuild, ParsedPiece, Suitability
from games.genshin.stats import FIXED_MAIN_SLOTS


def _main_list(build: CharacterBuild, slot: str | None) -> list[str]:
    if slot == "sands":
        return build.main_sands
    if slot == "goblet":
        return build.main_goblet
    if slot == "circlet":
        return build.main_circlet
    return []


def judge_suitability(piece: ParsedPiece, build: CharacterBuild, *, generic: bool = False) -> Suitability:
    """セットとメインから ◎○△ と総合キーを出す。"""
    if generic:
        return Suitability(set_mark=None, main_mark=None, overall_key=None, color_key="unknown")

    set_mark: str | None
    if not piece.set_id:
        set_mark = None
    elif piece.set_id in build.sets_preferred:
        set_mark = "preferred"
    elif piece.set_id in build.sets_ok:
        set_mark = "ok"
    else:
        set_mark = "other"

    main_mark: str | None
    if piece.slot in FIXED_MAIN_SLOTS:
        main_mark = "preferred"
    elif piece.main is None or piece.slot is None:
        main_mark = None
    elif piece.main.key in _main_list(build, piece.slot):
        main_mark = "preferred"
    else:
        main_mark = "other"

    if set_mark is None or main_mark is None:
        overall = None
        color = "unknown"
    elif set_mark == "other" or main_mark == "other":
        overall = "different"
        color = "different"
    elif set_mark == "ok" and main_mark == "preferred":
        overall = "usable"
        color = "usable"
    else:
        overall = "standard"
        color = "standard"

    return Suitability(
        set_mark=set_mark,
        main_mark=main_mark,
        overall_key=overall,
        color_key=color,
    )
