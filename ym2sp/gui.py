"""Графический интерфейс на pywebview: мост между JS и логикой приложения."""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import webbrowser
from importlib import metadata
from pathlib import Path
from typing import Any, Callable

import webview

from . import __version__
from .logs import log
from .models import Cancelled
from .settings import (
    DATA_DIR,
    Credentials,
    load_credentials,
    save_credentials,
    validate_redirect_uri,
)
from .spotify import SpotifyError, SpotifyService
from .sync import SyncOptions, run_sync
from .yandex import YandexError, YandexService, load_library, save_library

PACKAGE_DIR = Path(__file__).resolve().parent
WEB_DIR = PACKAGE_DIR / "web"
INDEX_FILE = WEB_DIR / "index.html"
# WinForms грузит иконку через System.Drawing.Icon, который понимает только .ico:
# PNG там роняет процесс необработанным исключением .NET
ICON_FILE = PACKAGE_DIR / "assets" / ("icon.ico" if sys.platform == "win32" else "icon.png")

# Явный бэкенд: на Linux в .deb есть только GTK/WebKit2, на Windows — WebView2
GUI_BACKEND = {"darwin": "cocoa", "win32": "edgechromium"}.get(sys.platform, "gtk")
PROGRESS_INTERVAL = 0.1  # не чаще 10 обновлений прогресса в секунду


class Api:
    """Публичные методы доступны из JS как window.pywebview.api.<name>.
    Атрибуты с подчеркиванием pywebview не экспортирует."""

    def __init__(self):
        self._window: webview.Window | None = None
        self._job: threading.Thread | None = None
        self._job_lock = threading.Lock()
        self._cancel = threading.Event()
        self._spotify: SpotifyService | None = None
        self._last_progress = 0.0

    # --- события в JS ---

    def _emit(self, event: str, **payload: Any) -> None:
        if not self._window:
            return
        data = json.dumps({"event": event, **payload}, ensure_ascii=False)
        try:
            self._window.evaluate_js(f"window.app && window.app.onEvent({data})")
        except Exception:
            pass

    def _log(self, message: str, level: str = "info") -> None:
        self._emit("log", level=level, message=message, time=time.strftime("%H:%M:%S"))

    def _progress(self, current: int, total: int, text: str = "", force: bool = False) -> None:
        now = time.monotonic()
        if not force and current < total and now - self._last_progress < PROGRESS_INTERVAL:
            return
        self._last_progress = now
        self._emit("progress", current=current, total=total, text=text)

    def _run_job(self, name: str, fn: Callable[[], None]) -> dict:
        with self._job_lock:
            if self._job and self._job.is_alive():
                return {"ok": False, "error": "Уже выполняется другая операция"}
            self._cancel.clear()
            self._job = threading.Thread(target=self._job_wrapper, args=(name, fn), daemon=True)
            self._job.start()
        return {"ok": True}

    def _job_wrapper(self, name: str, fn: Callable[[], None]) -> None:
        self._emit("busy", busy=True, job=name)
        try:
            fn()
        except Cancelled:
            self._log("⏹ Операция отменена", "warn")
        except (YandexError, SpotifyError, ValueError) as e:
            self._log(f"❌ {e}", "error")
            self._emit("error", message=str(e))
        except Exception as e:
            log.exception("Ошибка в задаче %s", name)
            self._log(f"❌ Непредвиденная ошибка: {e}", "error")
            self._emit("error", message=str(e))
        finally:
            self._emit("busy", busy=False, job=name)

    # --- состояние и настройки ---

    def get_state(self) -> dict:
        library = load_library()
        return {
            "version": __version__,
            "credentials": load_credentials().to_dict(),
            "library": {
                "count": len(library["tracks"]),
                "account": library.get("account") or "",
                "fetched_at": library.get("fetched_at"),
            } if library else None,
            "spotify_user": self._spotify.display_name if self._spotify else None,
            "busy": bool(self._job and self._job.is_alive()),
        }

    def save_settings(self, data: dict) -> dict:
        creds = Credentials(**{k: str(data.get(k, "")).strip() for k in Credentials().to_dict()})
        error = validate_redirect_uri(creds.spotify_redirect_uri)
        if error:
            return {"ok": False, "error": error}
        old = load_credentials()
        save_credentials(creds)
        if (old.spotify_client_id, old.spotify_client_secret) != (creds.spotify_client_id, creds.spotify_client_secret):
            self._spotify = None
            SpotifyService.logout()
        return {"ok": True, "state": self.get_state()}

    # --- шаг 1: Яндекс ---

    def fetch_yandex(self) -> dict:
        def job():
            self._log("🎵 Подключаюсь к Яндекс Музыке…")
            service = YandexService(load_credentials().yandex_token, log=self._log)
            self._log(f"✅ Аккаунт: {service.account_name}")
            tracks = service.fetch_liked(
                progress=lambda c, t: self._progress(c, t, "Загрузка лайков"),
                should_cancel=self._cancel.is_set,
            )
            save_library(tracks, service.account_name)
            self._log(f"💾 Сохранено треков: {len(tracks)}. Теперь можно включить ВПН и перейти к Spotify.", "success")
            self._emit("library", library=self.get_state()["library"])

        return self._run_job("yandex", job)

    # --- шаг 2: Spotify ---

    def connect_spotify(self) -> dict:
        def job():
            self._log("🔑 Авторизация в Spotify (при первом входе откроется браузер)…")
            self._spotify = SpotifyService(load_credentials())
            self._log(f"✅ Spotify: {self._spotify.display_name}", "success")
            self._emit("spotify", user=self._spotify.display_name, playlists=self._spotify.editable_playlists())

        return self._run_job("spotify", job)

    def refresh_playlists(self) -> dict:
        if not self._spotify:
            return self.connect_spotify()

        def job():
            self._emit("spotify", user=self._spotify.display_name, playlists=self._spotify.editable_playlists())

        return self._run_job("playlists", job)

    def logout_spotify(self) -> dict:
        if self._job and self._job.is_alive():
            return {"ok": False, "error": "Дождитесь завершения операции"}
        self._spotify = None
        SpotifyService.logout()
        return {"ok": True}

    def start_sync(self, opts: dict) -> dict:
        if not self._spotify:
            return {"ok": False, "error": "Сначала подключите Spotify"}
        library = load_library()
        if not library or not library["tracks"]:
            return {"ok": False, "error": "Нет треков: сначала загрузите лайки из Яндекс Музыки"}

        options = SyncOptions(
            mode="existing" if opts.get("mode") == "existing" else "new",
            playlist_id=str(opts.get("playlist_id") or ""),
            playlist_name=str(opts.get("playlist_name") or "").strip() or SyncOptions.playlist_name,
            public=bool(opts.get("public")),
            to_top=bool(opts.get("to_top", True)),
            dry_run=bool(opts.get("dry_run")),
            use_cache=bool(opts.get("use_cache", True)),
        )
        if options.mode == "existing" and not options.playlist_id:
            return {"ok": False, "error": "Выберите плейлист"}

        def job():
            report = run_sync(
                self._spotify,
                library["tracks"],
                options,
                progress=lambda c, t, text: self._progress(c, t, text),
                log=self._log,
                should_cancel=self._cancel.is_set,
            )
            self._progress(1, 1, "Готово", force=True)
            self._emit("result", summary=report.summary(), results=[r.to_dict() for r in report.results])
            if not options.dry_run and options.mode == "new" and report.playlist_id:
                self._emit("spotify", user=self._spotify.display_name, playlists=self._spotify.editable_playlists())

        return self._run_job("sync", job)

    def cancel(self) -> dict:
        self._cancel.set()
        return {"ok": True}

    # --- утилиты ---

    def open_url(self, url: str) -> dict:
        if not url.startswith(("https://open.spotify.com/", "https://developer.spotify.com/",
                               "https://oauth.yandex.ru/", "https://music.yandex.ru/")):
            return {"ok": False}
        webbrowser.open(url)
        return {"ok": True}

    def open_data_dir(self) -> dict:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(DATA_DIR)])
        elif sys.platform == "win32":
            subprocess.Popen(["explorer", str(DATA_DIR)])
        else:
            subprocess.Popen(["xdg-open", str(DATA_DIR)])
        return {"ok": True}


def run(debug: bool = False) -> None:
    api = Api()
    window = webview.create_window(
        "Yandex Music → Spotify",
        url=str(INDEX_FILE),
        js_api=api,
        width=1180,
        height=800,
        min_size=(860, 600),
    )
    api._window = window

    shown = threading.Event()
    window.events.shown += shown.set
    try:
        webview_version = metadata.version("pywebview")
    except metadata.PackageNotFoundError:
        webview_version = "?"
    storage = DATA_DIR / "webview"
    storage.mkdir(parents=True, exist_ok=True)
    log.info("pywebview %s, backend %s, storage %s", webview_version, GUI_BACKEND, storage)
    # Явная постоянная папка профиля WebView2: с приватным режимом и временным
    # профилем по умолчанию WebView2 на Windows может падать без сообщений
    webview.start(
        gui=GUI_BACKEND,
        icon=str(ICON_FILE),
        debug=debug,
        private_mode=False,
        storage_path=str(storage),
    )
    log.info("Окно закрыто")
    # Если бэкенд не смог инициализироваться, pywebview иногда просто
    # возвращает управление без окна и без исключения
    if not shown.is_set():
        raise RuntimeError(f"Окно не было создано (бэкенд {GUI_BACKEND})")
