#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Шаг 2: перенос плейлиста "Мне нравится" из Яндекс Музыки в Spotify.
Использует треки, ранее сохраненные в JSON скриптом fetch_yandex.py.

⚠️ Запускайте этот скрипт С ВПН (если Spotify недоступен в вашем регионе напрямую) —
   доступ к Яндекс Музыке на этом шаге уже не требуется.
"""

import argparse
import json
import time
from typing import List, Dict, Optional
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from difflib import SequenceMatcher

from yandex_fetcher import load_tracks_from_json, DEFAULT_TRACKS_FILE
from credentials_input import get_spotify_credentials


class MusicTransfer:
    def __init__(self, spotify_client_id: str,
                 spotify_client_secret: str, spotify_redirect_uri: str):
        """
        Инициализация клиента Spotify

        Args:
            spotify_client_id: Client ID приложения Spotify
            spotify_client_secret: Client Secret приложения Spotify
            spotify_redirect_uri: URI для перенаправления после авторизации
        """
        scope = "playlist-modify-public playlist-modify-private"
        self.spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=spotify_client_id,
            client_secret=spotify_client_secret,
            redirect_uri=spotify_redirect_uri,
            scope=scope
        ))

        self._verify_connection()

    def _verify_connection(self):
        """Проверка подключения к Spotify"""
        try:
            user = self.spotify_client.current_user()
            print(f"✅ Успешное подключение к Spotify (пользователь: {user['display_name'] or user['id']})")
        except Exception as e:
            print(f"❌ Ошибка подключения к Spotify: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print("🔑 Проблема с авторизацией. Проверьте правильность Client ID/Secret.")
            raise

    def search_spotify_track(self, title: str, artist: str, album: str = '') -> Optional[str]:
        """
        Поиск трека в Spotify

        Args:
            title: Название трека
            artist: Исполнитель
            album: Альбом (опционально)

        Returns:
            Spotify URI трека или None если не найден
        """
        try:
            search_queries = [
                f'track:"{title}" artist:"{artist}"',
                f'"{title}" "{artist}"',
                f'{title} {artist}',
                f'track:"{title}"' if len(title) > 3 else None
            ]

            search_queries = [q for q in search_queries if q]

            for query in search_queries:
                results = self.spotify_client.search(q=query, type='track', limit=10)

                if results['tracks']['items']:
                    best_match = self._find_best_match(
                        title, artist, results['tracks']['items']
                    )

                    if best_match:
                        return best_match['uri']

            return None

        except Exception as e:
            print(f"❌ Ошибка поиска трека '{title}' - '{artist}': {e}")
            return None

    def _find_best_match(self, target_title: str, target_artist: str,
                        candidates: List[Dict]) -> Optional[Dict]:
        """
        Поиск наиболее подходящего трека среди кандидатов

        Args:
            target_title: Целевое название трека
            target_artist: Целевой исполнитель
            candidates: Список кандидатов из Spotify

        Returns:
            Наиболее подходящий трек или None
        """
        best_score = 0
        best_match = None

        for track in candidates:
            title_similarity = SequenceMatcher(
                None, target_title.lower(), track['name'].lower()
            ).ratio()

            track_artists = [artist['name'].lower() for artist in track['artists']]
            artist_similarity = max([
                SequenceMatcher(None, target_artist.lower(), artist).ratio()
                for artist in track_artists
            ], default=0)

            total_score = title_similarity * 0.7 + artist_similarity * 0.3

            if total_score > best_score and total_score > 0.6:
                best_score = total_score
                best_match = track

        return best_match

    def create_spotify_playlist(self, name: str, tracks: List[str],
                              description: str = None) -> str:
        """
        Создание плейлиста в Spotify

        Args:
            name: Название плейлиста
            tracks: Список Spotify URI треков
            description: Описание плейлиста

        Returns:
            ID созданного плейлиста
        """
        try:
            user_id = self.spotify_client.current_user()['id']

            playlist = self.spotify_client.user_playlist_create(
                user=user_id,
                name=name,
                description=description or f"Плейлист перенесен из Яндекс Музыки ({len(tracks)} треков)"
            )

            playlist_id = playlist['id']
            print(f"✅ Создан плейлист: {name}")

            batch_size = 100
            for i in range(0, len(tracks), batch_size):
                batch = tracks[i:i + batch_size]
                self.spotify_client.playlist_add_items(playlist_id, batch)
                print(f"📝 Добавлено {len(batch)} треков (всего: {min(i + batch_size, len(tracks))}/{len(tracks)})")
                time.sleep(0.1)

            return playlist_id

        except Exception as e:
            print(f"❌ Ошибка создания плейлиста: {e}")
            raise

    def transfer_playlist(self, yandex_tracks: List[Dict],
                         playlist_name: str = "Мне нравится (из Яндекс Музыки)",
                         dry_run: bool = False):
        """
        Основной метод переноса плейлиста

        Args:
            yandex_tracks: Треки из Яндекс Музыки (загруженные из JSON)
            playlist_name: Название плейлиста в Spotify
            dry_run: Если True, только ищет треки и выводит статистику,
                     не создавая плейлист в Spotify
        """
        print("🚀 Начинаем перенос плейлиста...")
        if dry_run:
            print("🧪 Режим dry-run: плейлист создан не будет")

        if not yandex_tracks:
            print("❌ Список треков из Яндекс Музыки пуст")
            return

        spotify_tracks = []
        not_found_tracks = []

        print("🔍 Поиск треков в Spotify...")
        for i, track in enumerate(yandex_tracks, 1):
            print(f"[{i}/{len(yandex_tracks)}] Ищем: {track['artist']} - {track['title']}")

            spotify_uri = self.search_spotify_track(
                track['title'], track['artist'], track['album']
            )

            if spotify_uri:
                spotify_tracks.append(spotify_uri)
                print(f"  ✅ Найден")
            else:
                not_found_tracks.append(track)
                print(f"  ❌ Не найден")

            time.sleep(0.1)

        if spotify_tracks:
            if dry_run:
                print(f"\n🧪 Dry-run: плейлист '{playlist_name}' НЕ создан")
            else:
                self.create_spotify_playlist(
                    name=playlist_name,
                    tracks=spotify_tracks,
                    description=f"Перенесено из Яндекс Музыки. Найдено: {len(spotify_tracks)}/{len(yandex_tracks)} треков"
                )
                print(f"\n🎉 Плейлист успешно создан!")

            print(f"📊 Статистика:")
            print(f"   • Всего треков в Яндекс Музыке: {len(yandex_tracks)}")
            print(f"   • Найдено в Spotify: {len(spotify_tracks)}")
            print(f"   • Не найдено: {len(not_found_tracks)}")

        if not_found_tracks:
            self._save_not_found_tracks(not_found_tracks)

    def _save_not_found_tracks(self, tracks: List[Dict], filename: str = 'not_found_tracks.json'):
        """Сохранение списка ненайденных треков"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, ensure_ascii=False, indent=2)
            print(f"📄 Список ненайденных треков сохранен в {filename}")
        except Exception as e:
            print(f"❌ Ошибка сохранения списка ненайденных треков: {e}")


def main():
    """Основная функция"""
    parser = argparse.ArgumentParser(description="Перенос плейлиста из Яндекс Музыки в Spotify")
    parser.add_argument(
        '--dry-run', action='store_true',
        help="Только найти треки в Spotify и вывести статистику, не создавая плейлист"
    )
    args = parser.parse_args()

    print("🎵 Шаг 2/2: Перенос плейлиста из Яндекс Музыки в Spotify")
    print("=" * 50)

    try:
        yandex_tracks = load_tracks_from_json(DEFAULT_TRACKS_FILE)
    except FileNotFoundError:
        print(f"❌ Файл {DEFAULT_TRACKS_FILE} не найден.")
        print("👉 Сначала запустите fetch_yandex.py (без ВПН), чтобы получить треки из Яндекс Музыки.")
        return

    spotify_client_id, spotify_client_secret, spotify_redirect_uri = get_spotify_credentials()

    try:
        transfer = MusicTransfer(
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            spotify_redirect_uri=spotify_redirect_uri
        )

        transfer.transfer_playlist(yandex_tracks, dry_run=args.dry_run)

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
