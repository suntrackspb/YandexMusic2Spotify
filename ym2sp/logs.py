"""Лог в файл и показ фатальных ошибок.

У windowed-сборки нет консоли: без файла лога и диалога ошибка при старте
выглядит как «ничего не происходит».
"""

from __future__ import annotations

import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from .settings import DATA_DIR

LOG_FILE = DATA_DIR / "app.log"

log = logging.getLogger("ym2sp")


def setup_logging() -> None:
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
    except OSError:
        pass
    if sys.stderr is not None:
        root.addHandler(logging.StreamHandler())

    def excepthook(exc_type, exc, tb):
        log.critical("Необработанное исключение", exc_info=(exc_type, exc, tb))

    def thread_excepthook(args):
        log.critical("Исключение в потоке %s", args.thread, exc_info=(args.exc_type, args.exc_value, args.exc_traceback))

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook


def show_fatal_error(message: str) -> None:
    """Нативное окно ошибки (на Windows) или вывод в stderr."""
    text = f"{message}\n\nПодробности в журнале:\n{LOG_FILE}"
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, "Yandex Music → Spotify", 0x10)
            return
        except Exception:
            pass
    if sys.stderr is not None:
        print(text, file=sys.stderr)
