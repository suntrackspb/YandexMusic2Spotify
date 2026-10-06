"""Лог в файл и показ фатальных ошибок.

У windowed-сборки нет консоли: без файла лога и диалога ошибка при старте
выглядит как «ничего не происходит».
"""

from __future__ import annotations

import faulthandler
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler

from .settings import DATA_DIR

LOG_FILE = DATA_DIR / "app.log"

log = logging.getLogger("ym2sp")


CRASH_FILE = DATA_DIR / "crash.log"
_crash_stream = None


def setup_logging() -> None:
    global _crash_stream
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Подробный лог pywebview: какой бэкенд выбран, где падает инициализация
    logging.getLogger("pywebview").setLevel(logging.DEBUG)
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(LOG_FILE, maxBytes=1_000_000, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root.addHandler(handler)
        # Нативные падения (access violation, необработанное исключение .NET)
        # убивают процесс мимо Python — faulthandler успевает записать стек
        _crash_stream = open(CRASH_FILE, "w", encoding="utf-8")
        faulthandler.enable(file=_crash_stream, all_threads=True)
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
    text = f"{message}\n\nПодробности в журналах:\n{LOG_FILE}\n{CRASH_FILE}"
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(None, text, "Yandex Music → Spotify", 0x10)
            return
        except Exception:
            pass
    if sys.stderr is not None:
        print(text, file=sys.stderr)
