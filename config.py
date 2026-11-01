"""環境変数と、Bot 全体で共有する定数。"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

try:
    load_dotenv()
except UnicodeDecodeError as e:
    raise RuntimeError(
        ".env ファイルの文字コードがUTF-8ではありません。"
        "エディタで開いてUTF-8(BOMなし)で保存し直してください。"
        f"(詳細: {e})"
    ) from e

def env_int(name: str, default: int) -> int:
    """整数の環境変数を読む。空・不正なら default。"""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(str(raw).strip())
    except ValueError:
        return default


_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
STORAGE_DIR = BASE_DIR / "storage"
LOG_DIR = BASE_DIR / "logs"

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN")
GUILD_ID = env_int("GUILD_ID", 0) or None
LOG_LEVEL = (os.getenv("LOG_LEVEL") or "INFO").strip().upper()
if LOG_LEVEL not in _LOG_LEVELS:
    LOG_LEVEL = "INFO"
LOG_RETENTION_DAYS = max(1, env_int("LOG_RETENTION_DAYS", 30))

BOT_DISPLAY_NAME = "おしーそBot"

# BuildCard。GENSHIN_CHANNEL_ID は交換コード用なのでここでは読まない
CHANNEL_ID = env_int("BUILDCARD_CHANNEL_ID", 0) or env_int("CHANNEL_ID", 0)
ENKA_ASSET_RETENTION_DAYS = max(0, env_int("ENKA_ASSET_RETENTION_DAYS", 30))
CHARACTER_LEARN_HOURS = max(0, env_int("CHARACTER_LEARN_HOURS", 24))
VIEW_TIMEOUT_SECONDS = 900
EPHEMERAL_DELETE_SECONDS = max(0, env_int("EPHEMERAL_DELETE_SECONDS", 5))
ENKA_CACHE_SECONDS_FALLBACK = 300
START_BUTTON_CUSTOM_ID = "buildcard:start"

MSG_TOKEN_MISSING = "DISCORD_BOT_TOKEN が .env に設定されていません。"
MSG_MISSING_PERMISSIONS = "このコマンドを実行する権限がありません。"
MSG_COMMAND_ERROR = "エラーが発生しました。"
MSG_NICK_FAILED = "サーバーニックネームを {name} にできませんでした"
MSG_WORKING = "操作中"

COG_EXTENSIONS = (
    "cogs.fancode",
    "cogs.buildcard",
    "cogs.vc_manager",
)

DATA_DIR.mkdir(parents=True, exist_ok=True)
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)
