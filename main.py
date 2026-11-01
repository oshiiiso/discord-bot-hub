from bot import bot
from config import DISCORD_BOT_TOKEN, MSG_TOKEN_MISSING
from logging_config import get_logger, setup_logging

logger = get_logger(__name__)


def main() -> None:
    logger.info("起動しました")
    if not DISCORD_BOT_TOKEN:
        raise RuntimeError(MSG_TOKEN_MISSING)

    try:
        bot.run(DISCORD_BOT_TOKEN)
    except Exception:
        logger.exception("予期しないエラーで停止しました")
        raise
    finally:
        logger.info("終了しました")


if __name__ == "__main__":
    setup_logging()
    main()
