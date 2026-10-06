"""Нормализация названий и оценка совпадения треков Яндекс Музыки и Spotify.

Ключевые правила:
- трек принимается, только если похожи И название, И исполнитель
  (совпадение одного названия у другого артиста не засчитывается);
- кириллица транслитерируется, поэтому «Кино» совпадает с «Kino»;
- ремиксы/live/акустические версии не путаются с оригиналом;
- длительность (если известна) повышает или понижает оценку.
"""

from __future__ import annotations

import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache

from .models import SpotifyTrack, YandexTrack

TITLE_MIN = 0.75
ARTIST_MIN = 0.6
ACCEPT_SCORE = 0.78
CONFIDENT_SCORE = 0.97

_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ж": "zh", "з": "z",
    "и": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r",
    "с": "s", "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh",
    "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
}

_FEAT_RE = re.compile(r"\s*[\(\[]?\s*\b(feat\.?|ft\.?|featuring|при уч\.?)\s.*$", re.IGNORECASE)
_BRACKETS_RE = re.compile(r"\s*[\(\[].*?[\)\]]")
_DASH_SUFFIX_RE = re.compile(r"\s+[-–—]\s+.*$")
_NON_WORD_RE = re.compile(r"[\W_]+", re.UNICODE)
_VERSION_MARKERS = (
    "remix", "rmx", "live", "acoustic", "instrumental", "karaoke", "cover",
    "sped up", "slowed", "nightcore", "8d", "remake", "version",
)


def transliterate(text: str) -> str:
    return "".join(_TRANSLIT.get(ch, ch) for ch in text)


@lru_cache(maxsize=65536)
def normalize(text: str) -> str:
    """Нижний регистр, без диакритики и пунктуации, кириллица -> латиница."""
    text = unicodedata.normalize("NFKD", text.lower())
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.replace("&", " and ")
    text = transliterate(text)
    text = _NON_WORD_RE.sub(" ", text).strip()
    if text.startswith("the "):
        text = text[4:]
    return text


def base_title(title: str) -> str:
    """Название без feat., скобок и суффиксов вида « - Remastered 2011»."""
    base = _FEAT_RE.sub("", title)
    base = _BRACKETS_RE.sub("", base)
    base = _DASH_SUFFIX_RE.sub("", base)
    return base.strip() or title.strip()


def _version_markers(title: str) -> frozenset[str]:
    norm = normalize(title)
    return frozenset(m for m in _VERSION_MARKERS if re.search(rf"\b{m}\b", norm))


def ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def title_score(a: str, b: str) -> float:
    full = ratio(normalize(a), normalize(b))
    base = ratio(normalize(base_title(a)), normalize(base_title(b))) * 0.95
    score = max(full, base)
    if _version_markers(a) != _version_markers(b):
        score *= 0.75
    return score


def artist_score(a: list[str], b: list[str]) -> float:
    left = [normalize(x) for x in a if x]
    right = [normalize(x) for x in b if x]
    if not left or not right:
        return 0.0
    best = max(ratio(x, y) for x in left for y in right)
    # Одна сторона может хранить «A & B» одной строкой, другая — списком
    return max(best, ratio(" ".join(left), " ".join(right)))


def _duration_adjustment(a: int | None, b: int | None) -> float:
    if not a or not b:
        return 0.0
    diff = abs(a - b) / 1000
    if diff <= 3:
        return 0.05
    if diff <= 10:
        return 0.0
    if diff <= 30:
        return -0.1
    return -0.3


def match_score(track: YandexTrack, candidate: SpotifyTrack) -> float | None:
    """Оценка совпадения или None, если кандидат не подходит."""
    t = title_score(track.title, candidate.title)
    if t < TITLE_MIN:
        return None
    a = artist_score(track.artists, candidate.artists)
    if a < ARTIST_MIN:
        return None
    score = 0.6 * t + 0.4 * a + _duration_adjustment(track.duration_ms, candidate.duration_ms)
    return score if score >= ACCEPT_SCORE else None


def best_match(track: YandexTrack, candidates: list[SpotifyTrack]) -> tuple[SpotifyTrack | None, float]:
    best, best_score = None, 0.0
    for candidate in candidates:
        score = match_score(track, candidate)
        if score is not None and score > best_score:
            best, best_score = candidate, score
    return best, best_score


class PlaylistIndex:
    """Индекс треков плейлиста для быстрой (O(n)) проверки, есть ли там трек."""

    def __init__(self, tracks: list[SpotifyTrack]):
        self.uris: set[str] = {t.uri for t in tracks}
        self._by_artist: dict[str, list[SpotifyTrack]] = {}
        self._by_title: dict[str, list[SpotifyTrack]] = {}
        for t in tracks:
            for artist in t.artists:
                self._by_artist.setdefault(normalize(artist), []).append(t)
            self._by_title.setdefault(normalize(base_title(t.title)), []).append(t)

    def __len__(self) -> int:
        return len(self.uris)

    def find(self, track: YandexTrack) -> SpotifyTrack | None:
        candidates: dict[str, SpotifyTrack] = {}
        for artist in track.artists:
            for t in self._by_artist.get(normalize(artist), []):
                candidates[t.uri] = t
        for t in self._by_title.get(normalize(base_title(track.title)), []):
            candidates[t.uri] = t
        found, _ = best_match(track, list(candidates.values()))
        return found
