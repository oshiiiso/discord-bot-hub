"""FanCode（交換コード通知）の設定。"""

from __future__ import annotations

from config import DATA_DIR as HUB_DATA_DIR
from config import env_int

CHECK_INTERVAL_HOURS = max(1, env_int("CHECK_INTERVAL_HOURS", 1))
ADDITION_NOTICE_LIFETIME_SECONDS = 3 * 24 * 60 * 60

DATA_DIR = HUB_DATA_DIR / "fancode"
DATA_DIR.mkdir(parents=True, exist_ok=True)

GAME_CONFIG = {
    "genshin": {
        "name": "原神",
        "url": "https://genshin-impact.fandom.com/wiki/Promotional_Code",
        "channel_id": env_int("GENSHIN_CHANNEL_ID", 0),
        "color": 0x00FFCC,
        "redeem_url": "https://genshin.hoyoverse.com/ja/gift?code=",
    },
    "starrail": {
        "name": "崩壊：スターレイル",
        "url": "https://honkai-star-rail.fandom.com/wiki/Redemption_Code",
        "channel_id": env_int("STARRAIL_CHANNEL_ID", 0),
        "color": 0x00BFFF,
        "redeem_url": "https://hsr.hoyoverse.com/gift?code=",
    },
    "zzz": {
        "name": "ゼンレスゾーンゼロ",
        "url": "https://zenless-zone-zero.fandom.com/wiki/Redemption_Code",
        "channel_id": env_int("ZZZ_CHANNEL_ID", 0),
        "color": 0xFFCC00,
        "redeem_url": "https://zenless.hoyoverse.com/redemption?code=",
    },
    "wuthering": {
        "name": "鳴潮",
        "url": "https://wutheringwaves.fandom.com/wiki/Redemption_Code",
        "channel_id": env_int("WUTHERING_CHANNEL_ID", 0),
        "color": 0x9933FF,
        "redeem_url": None,
    },
}
