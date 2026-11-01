"""characters.json と artifact_sets.json を生成する。"""

from __future__ import annotations

import json
from pathlib import Path

from genshin_seed import ALIASES, ELEM, EXTRA_CHARS, SET_ROWS, _default_builds, _id_from_en, _traveler

ROOT = Path(__file__).resolve().parents[1]
TSV = Path(__file__).resolve().parent / "enka_index.tsv"
OUT_DIR = ROOT / "data" / "genshin"


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    seen_ids: set[str] = set()
    characters: list[dict] = _traveler()
    seen_ids.update(c["id"] for c in characters)

    for line in TSV.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        enka_id, element_raw, name_ja, name_en, side = line.split("\t")
        if "-" in enka_id:
            continue
        try:
            numeric_id = int(enka_id)
        except ValueError:
            continue
        if numeric_id < 10000000 or numeric_id >= 10000900:
            continue
        if enka_id in {"10000005", "10000007"}:
            continue
        if name_ja in {"?", ""}:
            continue
        element = ELEM.get(element_raw)
        if element is None:
            continue
        cid = _id_from_en(name_en, side)
        if cid in seen_ids:
            cid = f"{cid}_{enka_id[-2:]}"
        seen_ids.add(cid)
        aliases = list(ALIASES.get(enka_id, []))
        if name_en and name_en not in aliases:
            aliases.append(name_en)
        characters.append(
            {
                "id": cid,
                "name_ja": name_ja,
                "aliases": aliases,
                "element": element,
                "enka_keys": [enka_id],
                "builds": _default_builds(enka_id, element),
            }
        )

    have_enka = {key for c in characters for key in c["enka_keys"]}
    for extra in EXTRA_CHARS:
        enka_id = extra["enka_id"]
        if enka_id in have_enka:
            continue
        cid = extra["id"]
        if cid in seen_ids:
            cid = f"{cid}_{enka_id[-2:]}"
        seen_ids.add(cid)
        aliases = list(ALIASES.get(enka_id, []))
        for alias in extra.get("aliases") or []:
            if alias not in aliases:
                aliases.append(alias)
        characters.append(
            {
                "id": cid,
                "name_ja": extra["name_ja"],
                "aliases": aliases,
                "element": extra["element"],
                "enka_keys": [enka_id],
                "builds": _default_builds(enka_id, extra["element"]),
            }
        )

    characters.sort(key=lambda c: (c["element"], c["name_ja"]))
    (OUT_DIR / "artifact_sets.json").write_text(
        json.dumps(SET_ROWS, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (OUT_DIR / "characters.json").write_text(
        json.dumps(characters, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {len(characters)} characters, {len(SET_ROWS)} sets")


if __name__ == "__main__":
    main()
