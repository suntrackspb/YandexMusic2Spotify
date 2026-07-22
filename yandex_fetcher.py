#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для получения понравившихся треков из Яндекс Музыки.
Работает независимо от Spotify — используется на шаге, где нужно
выполнять запросы к Яндексу без ВПН (гео-блокировка при подключении через ВПН).
"""

import json
import time
from typing import List, Dict, Optional
from yandex_music import Client as YandexClient

DEFAULT_TRACKS_FILE = 'yandex_liked_tracks.json'
MAX_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5


class YandexFetcher:
    def __init__(self, yandex_token: str):
        """
        Инициализация клиента Яндекс Музыки

        Args:
            yandex_token: Токен для доступа к Яндекс Музыке
        """
        self.yandex_client = YandexClient(yandex_token).init()
        self._verify_connection()

    def _verify_connection(self):
        """Проверка подключения к Яндекс Музыке"""
        try:
            account = self.yandex_client.me.account
            if account:
                print(f"✅ Успешное подключение к Яндекс Музыке (пользователь: {account.display_name})")
            else:
                raise Exception("Не удалось получить информацию об аккаунте Яндекс Музыки")
        except Exception as e:
            print(f"❌ Ошибка подключения к Яндекс Музыке: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print("🔑 Проблема с авторизацией. Проверьте правильность токена.")
            print("🌐 Если вы подключаетесь через ВПН, отключите его — Яндекс Музыка")
            print("   блокирует доступ к аккаунту при подключении из-за рубежа.")
            raise

    def _fetch_track_with_retry(self, track_short) -> Optional[object]:
        """
        Получение полной информации о треке с повторными попытками при rate limit (429)

        Args:
            track_short: Короткая информация о треке из списка лайков

        Returns:
            Объект трека или None, если не удалось получить после всех попыток
        """
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return track_short.fetch_track()
            except Exception as e:
                is_rate_limit = 'too-many-requests' in str(e) or '429' in str(e)

                if is_rate_limit and attempt < MAX_RETRIES:
                    wait_time = RETRY_BACKOFF_SECONDS * attempt
                    print(f"   ⏳ Превышен лимит запросов, ждем {wait_time} сек. "
                          f"(попытка {attempt}/{MAX_RETRIES})...")
                    time.sleep(wait_time)
                    continue

                print(f"   ❌ Не удалось получить трек: {e}")
                return None

        return None

    def get_liked_tracks(self) -> List[Dict]:
        """
        Получение списка понравившихся треков из Яндекс Музыки

        Returns:
            Список словарей с информацией о треках
        """
        print("🎵 Получение списка понравившихся треков из Яндекс Музыки...")

        try:
            liked_tracks = list(self.yandex_client.users_likes_tracks())
        except Exception as e:
            print(f"❌ Ошибка при получении списка лайков из Яндекс Музыки: {e}")
            return []

        total = len(liked_tracks)
        print(f"📥 Загрузка информации о {total} треках...")

        tracks_info = []
        for i, track_short in enumerate(liked_tracks, 1):
            track = self._fetch_track_with_retry(track_short)

            if track and track.title:
                track_info = {
                    'title': track.title,
                    'artist': ', '.join([artist.name for artist in track.artists]),
                    'album': track.albums[0].title if track.albums else '',
                    'duration_ms': track.duration_ms,
                    'yandex_id': track.id
                }
                tracks_info.append(track_info)

            if i % 25 == 0 or i == total:
                print(f"   [{i}/{total}]")

            time.sleep(0.05)

        print(f"📊 Найдено {len(tracks_info)} понравившихся треков")
        return tracks_info


def save_tracks_to_json(tracks: List[Dict], filename: str = DEFAULT_TRACKS_FILE):
    """Сохранение списка треков в JSON-файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"📄 Треки сохранены в {filename}")


def load_tracks_from_json(filename: str = DEFAULT_TRACKS_FILE) -> List[Dict]:
    """Загрузка списка треков из JSON-файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
