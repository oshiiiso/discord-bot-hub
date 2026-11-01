"""全キャラの立ち絵名・天賦・ビルドが揃っているか見る。"""

from __future__ import annotations

import messages as msg
from games.genshin.catalog import load_characters
from services.copy import t
from services.enka_client import EnkaClient


def avatar_ids(key: str) -> tuple[int, int]:
    if "-" in key:
        avatar, depot = key.split("-", 1)
        return int(avatar), int(depot)
    return int(key), 0


def collect_rows(client: EnkaClient) -> list[dict]:
    rows = []
    for character in load_characters():
        if not character.enka_keys:
            rows.append(
                {
                    "name": character.name_ja,
                    "id": character.id,
                    "enka": "",
                    "store": False,
                    "portraits": [],
                    "skills": [],
                    "consts": [],
                    "builds": len(character.builds),
                    "problems": [t(msg.MSG_70)],
                    "notes": [],
                }
            )
            continue
        key = character.enka_keys[0]
        avatar_id, depot = avatar_ids(key)
        info = client._store_info(avatar_id, depot)
        in_store = bool(info.get("SideIconName") or info.get("SkillOrder"))
        name_id = client._name_id_for_avatar(avatar_id, depot, None)
        portraits = client.portrait_names(avatar_id, depot, None)
        dummy_levels = {str(i): 1 for i in (info.get("SkillOrder") or [1, 2, 3])}
        skills = [icon for icon, _lv in client._skills_for_avatar(info, dummy_levels, name_id) if icon]
        consts = [icon for icon in client._const_icons(info, name_id) if icon]
        notes: list[str] = []
        problems: list[str] = []
        if not portraits:
            problems.append(t(msg.MSG_68))
        if not character.builds:
            problems.append(t(msg.MSG_69))
        if not in_store:
            notes.append(t(msg.MSG_71))
        rows.append(
            {
                "name": character.name_ja,
                "id": character.id,
                "enka": key,
                "store": in_store,
                "portraits": portraits,
                "skills": skills,
                "consts": consts,
                "builds": len(character.builds),
                "problems": problems,
                "notes": notes,
            }
        )
    return rows


def problem_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["problems"]]


def note_rows(rows: list[dict]) -> list[dict]:
    return [row for row in rows if row["notes"] and not row["problems"]]


def format_report(rows: list[dict], *, everyone: bool = False) -> str:
    bad = problem_rows(rows)
    notes = note_rows(rows)
    lines = [t(msg.MSG_46, count=len(rows), bad=len(bad), notes=len(notes))]
    if everyone:
        lines.append(t(msg.MSG_50))
        for row in rows:
            mark = "NG" if row["problems"] else "OK"
            extra = ", ".join(row["problems"] + row["notes"]) or f"builds={row['builds']}"
            lines.append(f"  {mark} {row['name']} ({row['enka'] or row['id']}): {extra}")
        return "\n".join(lines)
    if bad:
        lines.append(t(msg.MSG_48))
        for row in bad:
            lines.append(f"  {row['name']} ({row['enka'] or row['id']}): {', '.join(row['problems'])}")
    else:
        lines.append(t(msg.MSG_47))
    if notes:
        lines.append(t(msg.MSG_49))
        for row in notes:
            lines.append(f"  {row['name']} ({row['enka']})")
    return "\n".join(lines)
