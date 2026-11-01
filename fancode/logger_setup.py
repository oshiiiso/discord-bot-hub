"""FanCode 用のログヘルパー。本体の logging に乗せる。"""

from logging_config import get_logger

logger = get_logger("fancode")


def debug_log(message: str) -> None:
    logger.debug(message)


def info_log(message: str) -> None:
    logger.info(message)
