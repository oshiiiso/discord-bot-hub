from datetime import date, datetime, timedelta
import logging
from pathlib import Path
import re

from config import LOG_DIR, LOG_LEVEL, LOG_RETENTION_DAYS

LOG_FILENAME_PATTERN = re.compile(r"^\d{8}\.log$")

_NOISY_LOGGER_NAMES = (
    "aiohttp",
    "aiohttp.access",
    "asyncio",
    "discord",
    "urllib3",
)


def _suppress_noisy_loggers() -> None:
    """discord などの DEBUG を落とす。"""
    for name in _NOISY_LOGGER_NAMES:
        logging.getLogger(name).setLevel(logging.WARNING)


def _cleanup_old_logs(retention_days: int) -> None:
    """期限切れの logs/yyyymmdd.log を消す。"""
    if not LOG_DIR.exists():
        return

    threshold = date.today() - timedelta(days=retention_days)

    for log_file in LOG_DIR.glob("*.log"):
        if not LOG_FILENAME_PATTERN.match(log_file.name):
            continue

        file_date = datetime.strptime(log_file.stem, "%Y%m%d").date()
        if file_date < threshold:
            try:
                log_file.unlink()
            except OSError as e:
                logging.getLogger(__name__).warning("古いログファイルの削除に失敗しました: %s (%s)", log_file, e)


class DailyFileHandler(logging.Handler):
    """日付ごとに logs/yyyymmdd.log へ出す。"""

    def __init__(self, formatter: logging.Formatter, log_dir: Path):
        super().__init__()
        self.setFormatter(formatter)
        self._log_dir = log_dir
        self._current_date: date | None = None
        self._file_handler: logging.FileHandler | None = None
        self._rotate_if_needed()

    def _rotate_if_needed(self) -> None:
        today = datetime.now().date()
        if today == self._current_date:
            return

        if self._file_handler is not None:
            self._file_handler.close()

        self._log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self._log_dir / f"{today:%Y%m%d}.log"

        self._file_handler = logging.FileHandler(log_file, encoding="utf-8")
        self._file_handler.setFormatter(self.formatter)
        self._current_date = today

        _cleanup_old_logs(LOG_RETENTION_DAYS)

    def emit(self, record: logging.LogRecord) -> None:
        self._rotate_if_needed()
        if self._file_handler is not None:
            self._file_handler.emit(record)


def setup_logging() -> None:
    root_logger = logging.getLogger()
    if root_logger.handlers:
        return

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    daily_file_handler = DailyFileHandler(formatter, LOG_DIR)

    root_logger.setLevel(LOG_LEVEL)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(daily_file_handler)
    _suppress_noisy_loggers()


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
