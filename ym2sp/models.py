"""Модели треков обоих сервисов."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class Cancelled(Exception):
    """Операция отменена пользователем."""


@dataclass
class YandexTrack:
    yandex_id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: str = ""
    duration_ms: int | None = None

    @property
    def artist(self) -> str:
        return ", ".join(self.artists)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "YandexTrack":
        artists = data.get("artists")
        if artists is None:
            # Формат старой версии: исполнители склеены в одну строку
            artists = [a.strip() for a in str(data.get("artist", "")).split(",") if a.strip()]
        return cls(
            yandex_id=str(data.get("yandex_id", "")),
            title=str(data.get("title", "")),
            artists=list(artists),
            album=str(data.get("album") or ""),
            duration_ms=data.get("duration_ms"),
        )


@dataclass
class SpotifyTrack:
    uri: str
    id: str
    title: str
    artists: list[str] = field(default_factory=list)
    album: str = ""
    duration_ms: int | None = None

    @property
    def artist(self) -> str:
        return ", ".join(self.artists)

    @property
    def url(self) -> str:
        return f"https://open.spotify.com/track/{self.id}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SpotifyTrack":
        return cls(
            uri=data["uri"],
            id=data.get("id") or data["uri"].rsplit(":", 1)[-1],
            title=data.get("title", ""),
            artists=list(data.get("artists", [])),
            album=data.get("album", ""),
            duration_ms=data.get("duration_ms"),
        )

    @classmethod
    def from_api(cls, item: dict[str, Any]) -> "SpotifyTrack":
        return cls(
            uri=item["uri"],
            id=item["id"],
            title=item.get("name", ""),
            artists=[a.get("name", "") for a in item.get("artists", [])],
            album=(item.get("album") or {}).get("name", ""),
            duration_ms=item.get("duration_ms"),
        )
