"""送信済みコード・固定メッセージIDの永続化を担当するモジュール。"""
import os
import json
from datetime import datetime, timezone

from .config import DATA_DIR

HISTORY_MAX_ENTRIES = 20


def _sent_codes_path(game_key):
    return os.path.join(DATA_DIR, f"sent_codes_{game_key}.txt")


def _msg_id_path(game_key):
    return os.path.join(DATA_DIR, f"msg_id_{game_key}.txt")


def _codes_data_path(game_key):
    return os.path.join(DATA_DIR, f"codes_data_{game_key}.json")


def _last_check_path(game_key):
    return os.path.join(DATA_DIR, f"last_check_{game_key}.txt")


def _history_path(game_key):
    return os.path.join(DATA_DIR, f"history_{game_key}.json")


def _addition_notice_deletes_path():
    return os.path.join(DATA_DIR, "addition_notice_deletes.json")


def sent_codes_exists(game_key):
    return os.path.exists(_sent_codes_path(game_key))


def load_saved_codes(game_key):
    filename = _sent_codes_path(game_key)
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
    return set()


def save_current_codes(game_key, codes_set):
    filename = _sent_codes_path(game_key)
    with open(filename, "w", encoding="utf-8") as f:
        for code in codes_set:
            f.write(f"{code}\n")


def load_message_id(game_key):
    filename = _msg_id_path(game_key)
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            val = f.read().strip()
            return int(val) if val.isdigit() else None
    return None


def save_message_id(game_key, msg_id):
    filename = _msg_id_path(game_key)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(str(msg_id))


def save_codes_data(game_key, codes_dict):
    """直近取得できた交換コード(報酬・期限情報込み)をJSONで保存する。"""
    filename = _codes_data_path(game_key)
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(codes_dict, f, ensure_ascii=False)


def load_codes_data(game_key):
    filename = _codes_data_path(game_key)
    if not os.path.exists(filename):
        return {}
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_last_check(game_key, dt=None):
    """直近のチェック実行日時を保存する。"""
    dt = dt or datetime.now()
    filename = _last_check_path(game_key)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(dt.isoformat())


def load_last_check(game_key):
    filename = _last_check_path(game_key)
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return datetime.fromisoformat(f.read().strip())
            except ValueError:
                return None
    return None


def append_history(game_key, event_type, codes):
    """コードの追加/削除履歴を記録する（直近HISTORY_MAX_ENTRIES件のみ保持）。"""
    if not codes:
        return
    filename = _history_path(game_key)
    history = load_history(game_key)
    history.append({
        "timestamp": datetime.now().isoformat(),
        "type": event_type,  # "added" または "removed"
        "codes": sorted(codes),
    })
    history = history[-HISTORY_MAX_ENTRIES:]
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False)


def load_history(game_key):
    filename = _history_path(game_key)
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def load_pending_addition_notices() -> list[dict]:
    """再起動後も削除する追加通知の一覧を読み込む。"""
    filename = _addition_notice_deletes_path()
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if not isinstance(data, list):
        return []
    return [entry for entry in data if isinstance(entry, dict)]


def save_pending_addition_notices(entries: list[dict]) -> None:
    filename = _addition_notice_deletes_path()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False)


def add_pending_addition_notice(channel_id: int, message_id: int, delete_at: datetime) -> None:
    """追加通知の削除予定を保存する。"""
    if delete_at.tzinfo is None:
        delete_at = delete_at.replace(tzinfo=timezone.utc)
    entries = [
        entry for entry in load_pending_addition_notices()
        if entry.get("message_id") != message_id
    ]
    entries.append({
        "channel_id": channel_id,
        "message_id": message_id,
        "delete_at": delete_at.isoformat(),
    })
    save_pending_addition_notices(entries)


def remove_pending_addition_notice(message_id: int) -> None:
    entries = [
        entry for entry in load_pending_addition_notices()
        if entry.get("message_id") != message_id
    ]
    save_pending_addition_notices(entries)


def remove_pending_addition_notices_for_channel(channel_id: int) -> None:
    """指定チャンネルの追加通知削除予定をすべて取り除く。"""
    entries = [
        entry for entry in load_pending_addition_notices()
        if entry.get("channel_id") != channel_id
    ]
    save_pending_addition_notices(entries)


def delete_game_files(game_key):
    """指定ゲームの保存済みファイル（sent_codes, msg_id, codes_data, last_check, history）を削除する。"""
    deleted = []
    paths = (
        _sent_codes_path(game_key),
        _msg_id_path(game_key),
        _codes_data_path(game_key),
        _last_check_path(game_key),
        _history_path(game_key),
    )
    for path in paths:
        if os.path.exists(path):
            os.remove(path)
            deleted.append(path)
    return deleted
