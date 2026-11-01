"""全キャラの立ち絵名・天賦アイコン・ビルドを一括確認する。"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import messages as msg  # noqa: E402
from services.character_check import collect_rows, format_report, problem_rows  # noqa: E402
from services.copy import t  # noqa: E402
from services.enka_client import ENKA_UI_URL, EnkaClient  # noqa: E402

UA = "discord-bot-hub/0.1 (oshiiiso)"


def _load_store(client: EnkaClient) -> None:
    path = ROOT / "storage" / "enka_store" / "characters.json"
    if path.exists():
        client._store = json.loads(path.read_text(encoding="utf-8"))
    else:
        client._store = {}


def _head_ok(name: str) -> tuple[str, str | None]:
    url = ENKA_UI_URL.format(icon=name)
    req = Request(url, method="HEAD", headers={"User-Agent": UA})
    try:
        with urlopen(req, timeout=12) as resp:
            if resp.status == 200:
                return name, None
            return name, f"HTTP {resp.status}"
    except HTTPError as e:
        if e.code == 405:
            req = Request(url, headers={"User-Agent": UA, "Range": "bytes=0-0"})
            try:
                with urlopen(req, timeout=12) as resp:
                    if resp.status in {200, 206}:
                        return name, None
                    return name, f"HTTP {resp.status}"
            except Exception as err:
                return name, str(err)
        return name, f"HTTP {e.code}"
    except URLError as e:
        return name, str(e.reason or e)


def _prefetch(names: list[str]) -> dict[str, str | None]:
    unique = list(dict.fromkeys(names))
    found: dict[str, str | None] = {}
    with ThreadPoolExecutor(max_workers=16) as pool:
        futures = [pool.submit(_head_ok, name) for name in unique]
        for fut in as_completed(futures):
            name, err = fut.result()
            found[name] = err
    return found


def _cdn_problems(row: dict, found: dict[str, str | None]) -> list[str]:
    problems: list[str] = []
    portraits = [n for n in row["portraits"] if n]
    if portraits and not any(found.get(n) is None for n in portraits):
        problems.append("立ち絵がCDNに無い")
    missing_skills = [n for n in row["skills"] if found.get(n)]
    if missing_skills:
        problems.append("天賦 " + ", ".join(missing_skills))
    consts = [n for n in row["consts"] if n]
    if consts and all(found.get(n) for n in consts):
        problems.append("命ノ星座がCDNに無い")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=msg.MSG_45)
    parser.add_argument("--online", action="store_true", help="Enka CDN に実在するかも見る")
    parser.add_argument("--all", action="store_true", help="問題がなくても全員出す")
    args = parser.parse_args()

    client = EnkaClient()
    _load_store(client)
    rows = collect_rows(client)
    bad = problem_rows(rows)
    print(format_report(rows, everyone=args.all))

    cdn_bad = 0
    if args.online:
        names: list[str] = []
        for row in rows:
            names.extend(row["portraits"])
            names.extend(row["skills"])
            names.extend(row["consts"])
        found = _prefetch(names)
        print(t(msg.MSG_51, count=len(found)))
        cdn_rows = []
        for row in rows:
            problems = _cdn_problems(row, found)
            if problems:
                cdn_rows.append((row, problems))
        if cdn_rows:
            for row, problems in cdn_rows:
                print(f"  NG {row['name']} ({row['enka']}): {', '.join(problems)}")
            print(t(msg.MSG_53, count=len(cdn_rows)))
            cdn_bad = len(cdn_rows)
        else:
            print(t(msg.MSG_52))

    return 1 if bad or cdn_bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
