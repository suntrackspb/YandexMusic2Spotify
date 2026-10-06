"""Работа со Spotify Web API: авторизация, поиск, плейлисты."""

from __future__ import annotations

from typing import Any, Iterator

import spotipy
from spotipy.cache_handler import CacheFileHandler
from spotipy.oauth2 import SpotifyOAuth

from .matching import CONFIDENT_SCORE, base_title, best_match
from .models import SpotifyTrack, YandexTrack
from .settings import SPOTIFY_TOKEN_CACHE, Credentials, validate_redirect_uri

SCOPES = " ".join([
    "playlist-read-private",
    "playlist-read-collaborative",
    "playlist-modify-public",
    "playlist-modify-private",
])
SEARCH_LIMIT = 10
ADD_BATCH = 100


class SpotifyError(Exception):
    pass


def _clean(text: str) -> str:
    """Убирает символы, ломающие синтаксис поискового запроса Spotify."""
    return " ".join(text.replace('"', " ").replace(":", " ").split())


class SpotifyService:
    def __init__(self, creds: Credentials):
        if not creds.has_spotify:
            raise SpotifyError("Не заданы Client ID / Client Secret Spotify (вкладка «Настройки»)")
        error = validate_redirect_uri(creds.spotify_redirect_uri)
        if error:
            raise SpotifyError(error)

        SPOTIFY_TOKEN_CACHE.parent.mkdir(parents=True, exist_ok=True)
        auth = SpotifyOAuth(
            client_id=creds.spotify_client_id,
            client_secret=creds.spotify_client_secret,
            redirect_uri=creds.spotify_redirect_uri,
            scope=SCOPES,
            cache_handler=CacheFileHandler(cache_path=str(SPOTIFY_TOKEN_CACHE)),
            open_browser=True,
        )
        # spotipy сам повторяет запросы при 429/5xx с учетом Retry-After
        self.sp = spotipy.Spotify(
            auth_manager=auth,
            requests_timeout=20,
            retries=5,
            status_retries=5,
            backoff_factor=1.0,
        )
        try:
            self.user = self.sp.current_user()
        except spotipy.SpotifyException as e:
            raise SpotifyError(f"Ошибка авторизации Spotify: {e.msg or e}") from e
        except spotipy.oauth2.SpotifyOauthError as e:
            raise SpotifyError(f"Ошибка авторизации Spotify: {e}. Проверьте Client ID/Secret и Redirect URI") from e
        self.user_id = self.user["id"]
        self.display_name = self.user.get("display_name") or self.user_id

    @staticmethod
    def logout() -> None:
        SPOTIFY_TOKEN_CACHE.unlink(missing_ok=True)

    def _paginate(self, page: dict | None) -> Iterator[dict]:
        while page:
            yield from page.get("items") or []
            page = self.sp.next(page) if page.get("next") else None

    # --- Поиск ---

    def _queries(self, track: YandexTrack) -> list[str]:
        artist = _clean(track.artists[0]) if track.artists else ""
        title = _clean(track.title)
        base = _clean(base_title(track.title))
        queries = []
        if artist:
            queries.append(f'track:"{base}" artist:"{artist}"')
            if title != base:
                queries.append(f"{title} {artist}")
            queries.append(f"{base} {artist}")
        else:
            queries.append(f'track:"{base}"')
        return list(dict.fromkeys(q for q in queries if q.strip()))

    def search(self, track: YandexTrack) -> tuple[SpotifyTrack | None, float]:
        """Ищет трек; исключения сети/API пробрасываются наружу, чтобы
        ошибка не выдавалась за «не найден»."""
        best, best_score = None, 0.0
        seen: set[str] = set()
        for query in self._queries(track):
            result = self.sp.search(q=query, type="track", limit=SEARCH_LIMIT)
            items = [i for i in (result.get("tracks") or {}).get("items") or [] if i and i.get("uri")]
            candidates = [SpotifyTrack.from_api(i) for i in items if i["uri"] not in seen]
            seen.update(c.uri for c in candidates)
            found, score = best_match(track, candidates)
            if found and score > best_score:
                best, best_score = found, score
            if best_score >= CONFIDENT_SCORE:
                break
        return best, best_score

    # --- Плейлисты ---

    def editable_playlists(self) -> list[dict[str, Any]]:
        """Только плейлисты, которые пользователь может изменять (свои и совместные)."""
        playlists = []
        for p in self._paginate(self.sp.current_user_playlists(limit=50)):
            if not p:
                continue
            owner = (p.get("owner") or {}).get("id")
            if owner != self.user_id and not p.get("collaborative"):
                continue
            counter = p.get("items") or p.get("tracks") or {}
            playlists.append({
                "id": p["id"],
                "name": p.get("name") or "(без названия)",
                "total": counter.get("total", 0) if isinstance(counter, dict) else 0,
                "public": bool(p.get("public")),
            })
        return playlists

    def playlist_tracks(self, playlist_id: str) -> list[SpotifyTrack]:
        tracks = []
        page = self.sp.playlist_items(playlist_id, limit=100, additional_types=("track",))
        for item in self._paginate(page):
            data = item.get("track") or item.get("item")
            if not data or data.get("type") != "track" or data.get("is_local") or not data.get("id"):
                continue
            tracks.append(SpotifyTrack.from_api(data))
        return tracks

    def create_playlist(self, name: str, public: bool, description: str) -> str:
        playlist = self.sp.current_user_playlist_create(name, public=public, description=description[:300])
        return playlist["id"]

    def add_tracks(self, playlist_id: str, uris: list[str], to_top: bool = False) -> None:
        """Добавляет треки, сохраняя их порядок. При to_top пачки вставляются
        в начало в обратном порядке — итоговый порядок совпадает с исходным."""
        batches = [uris[i:i + ADD_BATCH] for i in range(0, len(uris), ADD_BATCH)]
        if to_top:
            for batch in reversed(batches):
                self.sp.playlist_add_items(playlist_id, batch, position=0)
        else:
            for batch in batches:
                self.sp.playlist_add_items(playlist_id, batch)
