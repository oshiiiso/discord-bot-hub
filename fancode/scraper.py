"""交換コードのスクレイピング・期限判定・表記変換を担当するモジュール。"""
import re
from datetime import datetime
from urllib.parse import urlparse

import cloudscraper
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from .logger_setup import debug_log, info_log

DATE_PATTERN = r'([A-Za-z]+\s+\d{1,2},?\s+\d{4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})'


def _build_api_url_and_page(url):
    # 記事URL(https://xxx.fandom.com/wiki/Redemption_Code)から
    # MediaWiki APIのURLとページ名を作る。
    # api.php経由ならCloudflareのJSチェックを回避しやすい
    parsed = urlparse(url)
    page = parsed.path.rsplit('/', 1)[-1]
    api_url = f"{parsed.scheme}://{parsed.netloc}/api.php"
    return api_url, page


def is_expired(expiry_text):
    """
    Duration/Expiry列のテキストから期限切れかどうかを判定する。
    例: "Expired", "Valid until: 2024-01-01" などに対応。
    "Discovered: ..."のみで"Valid until"がない場合は
    発見日を終了日と誤解しないよう、期限不明(有効扱い)とする。
    判定できない場合は False（有効扱い）を返す。
    """
    if not expiry_text:
        return False

    text = expiry_text.strip()
    lower_text = text.lower()

    # 明示的に「期限切れ」とわかるキーワード
    if any(kw in lower_text for kw in ['expired', '終了', '期限切れ', 'ended']):
        return True

    # "Unknown" や "Permanent"、"TBD" などは有効扱い
    if any(kw in lower_text for kw in ['unknown', 'permanent', 'tbd', 'n/a', '不明']):
        return False

    # "Valid until"が明記されていなければ、Discovered日付だけの行なので
    # 期限不明として有効扱いにする(発見日を終了日と誤判定しない)。
    if 'valid until' not in lower_text and 'until' not in lower_text:
        return False

    # "Valid until" 以降の部分のみを対象に日付を抽出する
    until_part = re.split(r'valid until:?', text, flags=re.IGNORECASE)[-1]

    date_candidates = re.findall(DATE_PATTERN, until_part)

    parsed_dates = []
    for candidate in date_candidates:
        try:
            parsed = date_parser.parse(candidate, fuzzy=True)
            parsed_dates.append(parsed)
        except (ValueError, OverflowError):
            continue

    if not parsed_dates:
        # 日付を抽出できなければ判定不能として有効扱い
        return False

    # 複数の日付がある場合（期間表記）は最後の日付（終了日）を採用
    latest_date = max(parsed_dates)
    return latest_date < datetime.now()


def translate_expiry(expiry_text):
    """英語の期限表記を日本語（〇年〇月〇日まで）に変換する"""
    if not expiry_text:
        return "不明"

    text = expiry_text.strip()
    lower_text = text.lower()

    if any(kw in lower_text for kw in ['permanent', 'no expiration', 'unknown', 'tbd', 'n/a']):
        return "無期限/不明"

    if any(kw in lower_text for kw in ['expired', '終了', '期限切れ', 'ended']):
        return "期限切れ"

    # "Valid until"がなければ、Discovered日付を終了日と誤解しないように不明扱いにする
    if 'valid until' not in lower_text and 'until' not in lower_text:
        return "無期限/不明"

    until_part = re.split(r'valid until:?', text, flags=re.IGNORECASE)[-1]

    # テキスト中の日付らしき部分を正規表現で抽出（"In 3 weeks"のような相対表記は除外）
    date_candidates = re.findall(DATE_PATTERN, until_part)

    parsed_dates = []
    for candidate in date_candidates:
        try:
            parsed = date_parser.parse(candidate, fuzzy=True)
            parsed_dates.append(parsed)
        except (ValueError, OverflowError):
            continue

    if not parsed_dates:
        return text  # 日付を抽出できなければそのまま返す

    # 重複した同一日付をユニーク化し、最後（終了日）を採用
    unique_dates = sorted(set(parsed_dates))
    latest_date = unique_dates[-1]

    return f"{latest_date.year}年{latest_date.month}月{latest_date.day}日まで"


def fetch_latest_codes(game_key, url):
    """最新の交換コードを取得する。
    取得失敗時はNoneを返す(0件と区別するため)。
    """
    codes = {}
    scraper = None
    try:
        # 通常のページ閲覧はCloudflareにJSチェックで弾かれやすいので、
        # MediaWiki API(action=parse)でレンダリング済みHTMLを取ってくる
        scraper = cloudscraper.create_scraper(
            browser={
                "browser": "chrome",
                "platform": "windows",
                "desktop": True,
            }
        )
        headers = {
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
            "Accept": "application/json, text/javascript, */*; q=0.01",
        }
        api_url, page = _build_api_url_and_page(url)
        params = {
            "action": "parse",
            "page": page,
            "format": "json",
            "formatversion": "2",
            "prop": "text",
            "redirects": "1",
        }
        res = scraper.get(api_url, headers=headers, params=params, timeout=15)

        if res.status_code != 200:
            info_log(
                f"[エラー] {game_key} のページ取得失敗 (Status: {res.status_code})"
            )
            debug_log(
                f"{game_key}: レスポンス本文(先頭300文字): {res.text[:300] if res.text else '(空)'}"
            )
            return None

        try:
            data = res.json()
        except ValueError:
            info_log(f"[エラー] {game_key} のAPIレスポンスがJSONではありません。")
            debug_log(
                f"{game_key}: レスポンス本文(先頭300文字): {res.text[:300] if res.text else '(空)'}"
            )
            return None

        if "error" in data:
            info_log(f"[エラー] {game_key} のAPIエラー: {data['error']}")
            return None

        html_fragment = data.get("parse", {}).get("text", "")
        if not html_fragment:
            info_log(f"[エラー] {game_key} のページ本文が取得できませんでした。")
            return None

        soup = BeautifulSoup(html_fragment, 'lxml')

        # "Code"列を含むテーブルを正しく選別する
        table = None
        candidates = soup.find_all('table', class_='wikitable') or soup.find_all('table', class_='article-table') or soup.find_all('table')
        for cand in candidates:
            first_row = cand.find('tr')
            if not first_row:
                continue
            header_texts_check = [h.text.strip().lower() for h in first_row.find_all(['th', 'td'])]
            if any('code' in t for t in header_texts_check):
                table = cand
                break
        if table is None and candidates:
            table = candidates[0]

        if table:
            rows = table.find_all('tr')
            if not rows:
                return codes

            # ヘッダー行から列インデックスを特定
            header_cells = rows[0].find_all(['th', 'td'])
            header_texts = [h.text.strip().lower() for h in header_cells]

            def find_col(*keywords):
                for i, text in enumerate(header_texts):
                    if any(kw in text for kw in keywords):
                        return i
                return None

            code_idx = find_col('code') or 0
            server_idx = find_col('server', 'region')
            reward_idx = find_col('reward', 'rewards')
            expiry_idx = find_col('expir', 'expire', 'expires', 'date', 'duration')

            debug_log(f"{game_key}: 列インデックス - code:{code_idx}, server:{server_idx}, reward:{reward_idx}, expiry:{expiry_idx}")

            for row in rows[1:]:
                cols = row.find_all(['th', 'td'])
                if not cols:
                    continue

                # Server列の判定（All または Asia を含む場合のみ採用）
                if server_idx is not None and server_idx < len(cols):
                    server_text = cols[server_idx].text.strip()
                    if not (server_text == 'All' or 'Asia' in server_text):
                        continue

                if code_idx >= len(cols):
                    continue

                code_tag = cols[code_idx].find('code') or cols[code_idx].find('b')
                code_text = code_tag.text.strip() if code_tag else cols[code_idx].text.strip()

                if reward_idx is not None and reward_idx < len(cols):
                    raw_rewards = cols[reward_idx].text.strip().split('\n')
                    rewards_text = ", ".join([r.strip() for r in raw_rewards if r.strip()])
                else:
                    rewards_text = ""

                if expiry_idx is not None and expiry_idx < len(cols):
                    expiry_text = cols[expiry_idx].text.strip()
                else:
                    expiry_text = "不明"

                if code_text and not code_text.startswith(('^', 'Code', '▼', '[', '限定', '基本', '期間')):
                    if ' ' in code_text:
                        code_text = code_text.split()[0]

                    clean_code = code_text.replace('\xa0', '').strip()
                    # 4文字以上の英数字のコードのみを厳選
                    if clean_code and len(clean_code) >= 4 and clean_code.isalnum():
                        # 期限切れのコードはスキップする
                        if is_expired(expiry_text):
                            continue
                        codes[clean_code] = {
                            "reward": rewards_text,
                            "expiry": expiry_text
                        }
        else:
            info_log(f"[警告] {game_key} のテーブルが見つかりません。URL: {url}")
            return None

        debug_log(f"{game_key}: 取得件数: {len(codes)}件")
    except Exception as e:
        info_log(f"[エラー] {game_key} のスクレイピング中に問題が発生: {e}")
        return None
    finally:
        # セッションを閉じないと接続が残り、VPSで Too many open files になる
        if scraper is not None:
            scraper.close()
    return codes
