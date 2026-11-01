"""原神プラグイン。"""

from __future__ import annotations

from games.base import (
    CharacterBuild,
    CharacterInfo,
    ParsedPiece,
    ScoreResult,
    Suitability,
)
from games.genshin.catalog import character_by_enka_key, load_characters, load_sets
from games.genshin.score import score_piece
from games.genshin.stats import GENERIC_WEIGHTS, STAT_LABELS
from games.genshin.suitability import judge_suitability


class GenshinGame:
    """原神の聖遺物スコア。"""

    def get_character(self, character_id: str) -> CharacterInfo | None:
        for character in load_characters():
            if character.id == character_id:
                return character
        return None

    def resolve_character(self, query: str) -> CharacterInfo | None:
        q = query.strip().lower()
        if not q:
            return None
        for character in load_characters():
            names = [character.id, character.name_ja, *character.aliases]
            if any(q == n.lower() or q in n.lower() for n in names):
                return character
        return None

    def generic_presets(self) -> list[CharacterBuild]:
        labels = {
            "atk": "攻撃",
            "hp": "HP",
            "def": "防御",
            "em": "熟知",
            "er": "チャージ",
        }
        return [
            CharacterBuild(id=key, name_ja=labels[key], weights=dict(weights))
            for key, weights in GENERIC_WEIGHTS.items()
        ]

    def fallback_character(self, avatar_id: int, name_ja: str, element: str) -> CharacterInfo:
        """ローカル表に無い子。点数は汎用プリセットで出す。"""
        return CharacterInfo(
            id=f"enka_{avatar_id}",
            name_ja=name_ja,
            aliases=[],
            element=element,
            builds=self.generic_presets(),
            enka_keys=[str(avatar_id)],
        )

    def score(self, piece: ParsedPiece, build: CharacterBuild) -> ScoreResult:
        return score_piece(piece, build)

    def suitability(self, piece: ParsedPiece, build: CharacterBuild) -> Suitability:
        generic = build.id in GENERIC_WEIGHTS and not build.sets_preferred
        return judge_suitability(piece, build, generic=generic)

    def stat_label(self, key: str) -> str:
        return STAT_LABELS.get(key, key)

    def find_set(self, name: str) -> str | None:
        q = name.strip().lower()
        for set_id, row in load_sets().items():
            names = [set_id, str(row["name_ja"]), *list(row.get("aliases") or [])]
            if any(q == n.lower() or q in n.lower() for n in names):
                return set_id
        return None

    def character_by_enka_key(self, key: str) -> CharacterInfo | None:
        return character_by_enka_key(key)
