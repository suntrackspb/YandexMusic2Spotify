"""Сопоставление библиотеки Яндекса с Spotify и запись в плейлист."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable

import spotipy

from .matching import PlaylistIndex
from .models import Cancelled, SpotifyTrack, YandexTrack
from .settings import MATCHES_FILE, REPORTS_DIR, read_json, write_json
from .spotify import SpotifyService

# Статусы трека в результатах синхронизации
ADDED = "added"          # найден и будет/был добавлен
EXISTS = "exists"        # уже есть в плейлисте
DUPLICATE = "duplicate"  # найден, но тот же трек Spotify уже сопоставлен другому
NOT_FOUND = "not_found"
ERROR = "error"

CACHE_SAVE_EVERY = 25


class MatchCache:
    """Кэш yandex_id -> найденный трек Spotify, чтобы не искать повторно."""

    def __init__(self):
        raw = read_json(MATCHES_FILE, {})
        self._data: dict[str, dict] = raw if isinstance(raw, dict) else {}
        self._dirty = False

    def get(self, yandex_id: str) -> SpotifyTrack | None:
        entry = self._data.get(yandex_id)
        try:
            return SpotifyTrack.from_dict(entry) if entry else None
        except (KeyError, TypeError):
            return None

    def put(self, yandex_id: str, track: SpotifyTrack) -> None:
        self._data[yandex_id] = track.to_dict()
        self._dirty = True

    def save(self) -> None:
        if self._dirty:
            write_json(MATCHES_FILE, self._data)
            self._dirty = False


@dataclass
class SyncOptions:
    mode: str = "new"              # "new" | "existing"
    playlist_id: str = ""
    playlist_name: str = "Мне нравится (из Яндекс Музыки)"
    public: bool = False
    to_top: bool = True            # новые треки — в начало существующего плейлиста
    dry_run: bool = False
    use_cache: bool = True


@dataclass
class TrackResult:
    track: YandexTrack
    status: str
    spotify: SpotifyTrack | None = None
    score: float = 0.0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "yandex": self.track.to_dict(),
            "spotify": self.spotify.to_dict() | {"url": self.spotify.url} if self.spotify else None,
            "score": round(self.score, 3),
            "error": self.error,
        }


@dataclass
class SyncReport:
    results: list[TrackResult] = field(default_factory=list)
    playlist_id: str = ""
    playlist_name: str = ""
    dry_run: bool = False
    report_file: str = ""

    def count(self, status: str) -> int:
        return sum(1 for r in self.results if r.status == status)

    def summary(self) -> dict:
        return {
            "total": len(self.results),
            "added": self.count(ADDED),
            "exists": self.count(EXISTS),
            "duplicate": self.count(DUPLICATE),
            "not_found": self.count(NOT_FOUND),
            "error": self.count(ERROR),
            "playlist_id": self.playlist_id,
            "playlist_name": self.playlist_name,
            "dry_run": self.dry_run,
            "report_file": self.report_file,
        }


ProgressFn = Callable[[int, int, str], None]
LogFn = Callable[[str], None]
CancelFn = Callable[[], bool]


def run_sync(
    spotify: SpotifyService,
    tracks: list[YandexTrack],
    options: SyncOptions,
    progress: ProgressFn,
    log: LogFn,
    should_cancel: CancelFn,
) -> SyncReport:
    report = SyncReport(dry_run=options.dry_run)

    existing: list[SpotifyTrack] = []
    if options.mode == "existing":
        if not options.playlist_id:
            raise ValueError("Не выбран плейлист")
        log("📥 Загружаю треки выбранного плейлиста…")
        existing = spotify.playlist_tracks(options.playlist_id)
        log(f"   В плейлисте {len(existing)} треков")
        report.playlist_id = options.playlist_id
    report.playlist_name = options.playlist_name

    index = PlaylistIndex(existing)
    cache = MatchCache()
    taken: set[str] = set(index.uris)
    to_add: list[str] = []
    total = len(tracks)

    log(f"🔍 Сопоставляю {total} треков со Spotify…")
    try:
        for i, track in enumerate(tracks, 1):
            if should_cancel():
                raise Cancelled()
            progress(i, total, f"{track.artist} — {track.title}")
            report.results.append(_resolve(track, spotify, cache, index, taken, to_add, options.use_cache))
            if i % CACHE_SAVE_EVERY == 0:
                cache.save()
    finally:
        cache.save()

    if options.dry_run:
        log("🧪 Пробный запуск: Spotify не изменен")
    elif to_add:
        if options.mode == "new":
            description = f"Перенесено из Яндекс Музыки {datetime.now():%d.%m.%Y}"
            report.playlist_id = spotify.create_playlist(options.playlist_name, options.public, description)
            log(f"✅ Создан плейлист «{options.playlist_name}»")
            spotify.add_tracks(report.playlist_id, to_add)
        else:
            spotify.add_tracks(report.playlist_id, to_add, to_top=options.to_top)
        log(f"✅ Добавлено треков: {len(to_add)}")
    else:
        log("✅ Новых треков для добавления нет")

    report.report_file = _save_report(report)
    return report


def _resolve(
    track: YandexTrack,
    spotify: SpotifyService,
    cache: MatchCache,
    index: PlaylistIndex,
    taken: set[str],
    to_add: list[str],
    use_cache: bool,
) -> TrackResult:
    cached = cache.get(track.yandex_id) if use_cache else None
    if cached and cached.uri in index.uris:
        return TrackResult(track, EXISTS, cached, 1.0)

    present = index.find(track) if len(index) else None
    if present:
        return TrackResult(track, EXISTS, present, 1.0)

    if cached:
        found, score = cached, 1.0
    else:
        try:
            found, score = spotify.search(track)
        except spotipy.SpotifyException as e:
            return TrackResult(track, ERROR, error=e.msg or str(e))
        except Exception as e:  # сеть, таймауты
            return TrackResult(track, ERROR, error=str(e))
        if found:
            cache.put(track.yandex_id, found)

    if not found:
        return TrackResult(track, NOT_FOUND)
    if found.uri in taken:
        return TrackResult(track, DUPLICATE, found, score)
    taken.add(found.uri)
    to_add.append(found.uri)
    return TrackResult(track, ADDED, found, score)


def _save_report(report: SyncReport) -> str:
    path = REPORTS_DIR / f"report_{time.strftime('%Y%m%d_%H%M%S')}.json"
    write_json(path, {
        "summary": report.summary(),
        "not_found": [r.track.to_dict() for r in report.results if r.status == NOT_FOUND],
        "errors": [r.to_dict() for r in report.results if r.status == ERROR],
        "duplicates": [r.to_dict() for r in report.results if r.status == DUPLICATE],
    })
    return str(path)
