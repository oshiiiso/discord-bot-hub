"""原神のサブステ加重スコア。"""

from __future__ import annotations

from games.base import CharacterBuild, ParsedPiece, ScoreResult
from games.genshin.stats import (
    ADJUSTED_SLOTS,
    BAND_KEYS,
    RATING_OFFSET_SLOTS,
    RATING_THRESHOLDS,
)


def score_piece(piece: ParsedPiece, build: CharacterBuild) -> ScoreResult:
    """サブステだけを加重して点数にする。"""
    per_stat: dict[str, float] = {}
    total = 0.0
    for sub in piece.subs:
        weight = float(build.weights.get(sub.key, 0.0))
        part = sub.value * weight
        if part:
            per_stat[sub.key] = per_stat.get(sub.key, 0.0) + part
        total += part

    total = round(total, 1)
    thresholds = list(RATING_THRESHOLDS)
    if piece.slot in ADJUSTED_SLOTS:
        thresholds = [line - RATING_OFFSET_SLOTS for line in thresholds]

    band_key = BAND_KEYS[0]
    for index, line in enumerate(thresholds):
        if total >= line:
            band_key = BAND_KEYS[index + 1]
    return ScoreResult(total=total, per_stat=per_stat, band_key=band_key)
