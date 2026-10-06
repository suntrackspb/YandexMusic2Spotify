"""Получение лайкнутых треков из Яндекс Музыки.

Запускать без ВПН: Яндекс Музыка блокирует доступ к аккаунту из-за рубежа.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Callable

from yandex_music import Client
from yandex_music.exceptions import (
    BadRequestError,
    NetworkError,
    NotFoundError,
    UnauthorizedError,
    YandexMusicError,
)

from .models import Cancelled, YandexTrack
from .settings import LEGACY_LIBRARY_FILE, LIBRARY_FILE, read_json, write_json

BATCH_SIZE = 100
MAX_ATTEMPTS = 6
BACKOFF_SECONDS = 3

ProgressFn = Callable[[int, int], None]
LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]


class YandexError(Exception):
    pass


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, (BadRequestError, NotFoundError, UnauthorizedError)):
        return False
    text = str(error).lower()
    return isinstance(error, NetworkError) or "too-many-requests" in text or "429" in text


class YandexService:
    def __init__(self, token: str, log: LogFn = print):
        if not token:
            raise YandexError("Не задан токен Яндекс Музыки (вкладка «Настройки»)")
        self._log = log
        try:
            self.client = Client(token).init()
            account = self.client.me.account if self.client.me else None
        except UnauthorizedError as e:
            raise YandexError("Токен Яндекс Музыки недействителен или устарел — получите новый") from e
        except YandexMusicError as e:
            raise YandexError(
                f"Не удалось подключиться к Яндекс Музыке: {e}. "
                "Если включен ВПН — отключите его на этом шаге."
            ) from e
        if account is None:
            raise YandexError("Не удалось получить аккаунт Яндекс Музыки. Проверьте токен и отключите ВПН.")
        self.account_name = account.display_name or account.login or str(account.uid)

    def _call(self, fn, what: str, should_cancel: CancelFn):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                return fn()
            except Exception as e:
                if not _is_retryable(e) or attempt == MAX_ATTEMPTS:
                    raise YandexError(f"{what}: {e}") from e
                wait = BACKOFF_SECONDS * attempt
                self._log(f"⏳ {what}: {e}. Повтор через {wait} с ({attempt}/{MAX_ATTEMPTS - 1})")
                for _ in range(wait * 10):
                    if should_cancel():
                        raise Cancelled()
                    time.sleep(0.1)

    def fetch_liked(self, progress: ProgressFn, should_cancel: CancelFn) -> list[YandexTrack]:
        likes = self._call(self.client.users_likes_tracks, "Список лайков", should_cancel)
        ids = [str(tid) for tid in likes.tracks_ids] if likes else []
        total = len(ids)
        self._log(f"📥 Лайков в Яндекс Музыке: {total}. Загружаю данные треков пачками по {BATCH_SIZE}…")
        progress(0, total)

        by_id: dict[str, YandexTrack] = {}
        for start in range(0, total, BATCH_SIZE):
            if should_cancel():
                raise Cancelled()
            chunk = ids[start:start + BATCH_SIZE]
            tracks = self._call(lambda: self.client.tracks(chunk), "Загрузка треков", should_cancel) or []
            for t in tracks:
                if not t or not t.title:
                    continue
                title = f"{t.title} ({t.version})" if getattr(t, "version", None) else t.title
                by_id[str(t.id)] = YandexTrack(
                    yandex_id=str(t.id),
                    title=title,
                    artists=[a.name for a in (t.artists or []) if a and a.name],
                    album=t.albums[0].title if t.albums and t.albums[0].title else "",
                    duration_ms=t.duration_ms,
                )
            progress(min(start + BATCH_SIZE, total), total)

        # Сохраняем порядок лайков (новые сверху) и убираем повторы
        result, seen = [], set()
        for tid in ids:
            key = tid.split(":", 1)[0]
            if key in by_id and key not in seen:
                seen.add(key)
                result.append(by_id[key])

        skipped = total - len(result)
        if skipped:
            self._log(f"⚠️ Пропущено {skipped} треков без данных (удалены или недоступны)")
        return result


def save_library(tracks: list[YandexTrack], account: str) -> dict:
    data = {
        "account": account,
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tracks": [t.to_dict() for t in tracks],
    }
    write_json(LIBRARY_FILE, data)
    return data


def load_library() -> dict | None:
    """Библиотека из data/ или, для совместимости, yandex_liked_tracks.json старой версии."""
    data = read_json(LIBRARY_FILE, None)
    if data is None:
        legacy = read_json(LEGACY_LIBRARY_FILE, None)
        if isinstance(legacy, list):
            data = {"account": "", "fetched_at": None, "tracks": legacy}
    if not isinstance(data, dict) or not isinstance(data.get("tracks"), list):
        return None
    data["tracks"] = [YandexTrack.from_dict(t) for t in data["tracks"] if isinstance(t, dict)]
    return data
