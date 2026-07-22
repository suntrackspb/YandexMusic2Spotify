#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для получения понравившихся треков из Яндекс Музыки.
Работает независимо от Spotify — используется на шаге, где нужно
выполнять запросы к Яндексу без ВПН (гео-блокировка при подключении через ВПН).
"""

import json
from typing import List, Dict
from yandex_music import Client as YandexClient

DEFAULT_TRACKS_FILE = 'yandex_liked_tracks.json'


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

    def get_liked_tracks(self) -> List[Dict]:
        """
        Получение списка понравившихся треков из Яндекс Музыки

        Returns:
            Список словарей с информацией о треках
        """
        try:
            print("🎵 Получение списка понравившихся треков из Яндекс Музыки...")

            liked_tracks = self.yandex_client.users_likes_tracks()

            tracks_info = []
            for track_short in liked_tracks:
                track = track_short.fetch_track()

                if track and track.title:
                    track_info = {
                        'title': track.title,
                        'artist': ', '.join([artist.name for artist in track.artists]),
                        'album': track.albums[0].title if track.albums else '',
                        'duration_ms': track.duration_ms,
                        'yandex_id': track.id
                    }
                    tracks_info.append(track_info)

            print(f"📊 Найдено {len(tracks_info)} понравившихся треков")
            return tracks_info

        except Exception as e:
            print(f"❌ Ошибка при получении треков из Яндекс Музыки: {e}")
            return []


def save_tracks_to_json(tracks: List[Dict], filename: str = DEFAULT_TRACKS_FILE):
    """Сохранение списка треков в JSON-файл"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(tracks, f, ensure_ascii=False, indent=2)
    print(f"📄 Треки сохранены в {filename}")


def load_tracks_from_json(filename: str = DEFAULT_TRACKS_FILE) -> List[Dict]:
    """Загрузка списка треков из JSON-файла"""
    with open(filename, 'r', encoding='utf-8') as f:
        return json.load(f)
