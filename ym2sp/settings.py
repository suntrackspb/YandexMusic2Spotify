"""Пути к файлам данных и загрузка/сохранение учетных данных."""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

APP_NAME = "YandexMusic2Spotify"
ROOT = Path(__file__).resolve().parent.parent


def _user_data_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if sys.platform == "win32":
        return Path(os.getenv("APPDATA") or Path.home() / "AppData" / "Roaming") / APP_NAME
    return Path(os.getenv("XDG_DATA_HOME") or Path.home() / ".local" / "share") / APP_NAME


# Запуск из исходников: данные рядом с проектом. Собранное приложение (PyInstaller,
# .deb в /opt) не может писать в свой каталог — используем папку пользователя.
IS_SOURCE_CHECKOUT = not getattr(sys, "frozen", False) and os.access(ROOT, os.W_OK)
DATA_DIR = ROOT / "data" if IS_SOURCE_CHECKOUT else _user_data_dir()
SETTINGS_FILE = DATA_DIR / "settings.json"
LIBRARY_FILE = DATA_DIR / "yandex_library.json"
MATCHES_FILE = DATA_DIR / "matches.json"
REPORTS_DIR = DATA_DIR / "reports"
SPOTIFY_TOKEN_CACHE = DATA_DIR / "spotify_token.json"

LEGACY_CONFIG_FILE = ROOT / "config.py"
LEGACY_LIBRARY_FILE = ROOT / "yandex_liked_tracks.json"

DEFAULT_REDIRECT_URI = "http://127.0.0.1:8888/callback"

# Поле Credentials -> (переменная окружения, константа в config.py)
_SOURCES = {
    "yandex_token": ("YANDEX_MUSIC_TOKEN", "YANDEX_MUSIC_TOKEN"),
    "spotify_client_id": ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_ID"),
    "spotify_client_secret": ("SPOTIFY_CLIENT_SECRET", "SPOTIFY_CLIENT_SECRET"),
    "spotify_redirect_uri": ("SPOTIFY_REDIRECT_URI", "SPOTIFY_REDIRECT_URI"),
}


@dataclass
class Credentials:
    yandex_token: str = ""
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = DEFAULT_REDIRECT_URI

    @property
    def has_yandex(self) -> bool:
        return bool(self.yandex_token)

    @property
    def has_spotify(self) -> bool:
        return bool(self.spotify_client_id and self.spotify_client_secret)

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def _is_placeholder(value: str) -> bool:
    return not value or value.startswith("your_")


def _load_legacy_config() -> dict[str, str]:
    """Читает константы из config.py старого формата, не выполняя setup_environment()."""
    if not LEGACY_CONFIG_FILE.exists():
        return {}
    spec = importlib.util.spec_from_file_location("_ym2sp_legacy_config", LEGACY_CONFIG_FILE)
    if spec is None or spec.loader is None:
        return {}
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception:
        return {}
    values = {}
    for field, (_, const) in _SOURCES.items():
        value = str(getattr(module, const, "") or "").strip()
        if not _is_placeholder(value):
            values[field] = value
    return values


def load_credentials() -> Credentials:
    """Собирает учетные данные. Приоритет (по возрастанию): окружение, config.py, data/settings.json."""
    values: dict[str, str] = {}

    for field, (env, _) in _SOURCES.items():
        value = os.getenv(env, "").strip()
        if value:
            values[field] = value

    values.update(_load_legacy_config())

    stored = read_json(SETTINGS_FILE, {})
    if isinstance(stored, dict):
        values.update({k: str(v).strip() for k, v in stored.items() if k in _SOURCES and str(v).strip()})

    creds = Credentials(**values)
    if not creds.spotify_redirect_uri:
        creds.spotify_redirect_uri = DEFAULT_REDIRECT_URI
    return creds


def save_credentials(creds: Credentials) -> None:
    write_json(SETTINGS_FILE, creds.to_dict())
    try:
        SETTINGS_FILE.chmod(0o600)
    except OSError:
        pass


def validate_redirect_uri(uri: str) -> str | None:
    """Возвращает текст ошибки или None. GUI не умеет вводить код вручную,
    поэтому redirect URI должен указывать на локальный сервер с портом."""
    parsed = urlparse(uri)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port:
        return "Redirect URI должен иметь вид http://127.0.0.1:<порт>/callback (Spotify не принимает localhost)"
    return None


def read_json(path: Path, default: Any) -> Any:
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return default
    except (OSError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    """Атомарная запись: сначала во временный файл, затем замена."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)
