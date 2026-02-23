#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Скрипт для переноса плейлиста "Мне нравится" из Яндекс Музыки в Spotify
"""

import os
import json
import time
from typing import List, Dict, Optional
from yandex_music import Client as YandexClient
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from difflib import SequenceMatcher


class MusicTransfer:
    def __init__(self, yandex_token: str, spotify_client_id: str, 
                 spotify_client_secret: str, spotify_redirect_uri: str):
        """
        Инициализация клиентов для Яндекс Музыки и Spotify
        
        Args:
            yandex_token: Токен для доступа к Яндекс Музыке
            spotify_client_id: Client ID приложения Spotify
            spotify_client_secret: Client Secret приложения Spotify
            spotify_redirect_uri: URI для перенаправления после авторизации
        """
        self.yandex_client = YandexClient(yandex_token).init()
        
        # Настройка Spotify
        scope = "playlist-modify-public playlist-modify-private"
        self.spotify_client = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=spotify_client_id,
            client_secret=spotify_client_secret,
            redirect_uri=spotify_redirect_uri,
            scope=scope
        ))
        
        # Проверка подключения
        self._verify_connections()
    
    def _verify_connections(self):
        """Проверка подключения к сервисам"""
        try:
            # Проверка Яндекс Музыки
            account = self.yandex_client.me.account
            if account:
                print(f"✅ Успешное подключение к Яндекс Музыке (пользователь: {account.display_name})")
            else:
                raise Exception("Не удалось получить информацию об аккаунте Яндекс Музыки")
            
            # Проверка Spotify
            user = self.spotify_client.current_user()
            print(f"✅ Успешное подключение к Spotify (пользователь: {user['display_name'] or user['id']})")
            
        except Exception as e:
            print(f"❌ Ошибка подключения: {e}")
            if "401" in str(e) or "Unauthorized" in str(e):
                print("🔑 Проблема с авторизацией. Проверьте правильность токенов.")
                print("📝 Инструкции по получению токена Яндекс Музыки:")
                print("   1. Откройте https://music.yandex.ru/ в браузере")
                print("   2. Войдите в свой аккаунт")
                print("   3. Откройте инструменты разработчика (F12)")
                print("   4. Перейдите во вкладку Network")
                print("   5. Обновите страницу")
                print("   6. Найдите запрос к 'music-web.yandex.net'")
                print("   7. Скопируйте ПОЛНОЕ значение заголовка 'Authorization'")
                print("   8. Вставьте его в config.py в переменную YANDEX_MUSIC_TOKEN")
            raise
    
    def get_yandex_liked_tracks(self) -> List[Dict]:
        """
        Получение списка понравившихся треков из Яндекс Музыки
        
        Returns:
            Список словарей с информацией о треках
        """
        try:
            print("🎵 Получение списка понравившихся треков из Яндекс Музыки...")
            
            # Получаем лайкнутые треки
            liked_tracks = self.yandex_client.users_likes_tracks()
            
            tracks_info = []
            for track_short in liked_tracks:
                # Получаем полную информацию о треке
                track = track_short.fetch_track()
                
                if track and track.title:  # Проверяем что трек существует
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
            # Различные варианты поискового запроса
            search_queries = [
                f'track:"{title}" artist:"{artist}"',
                f'"{title}" "{artist}"',
                f'{title} {artist}',
                f'track:"{title}"' if len(title) > 3 else None
            ]
            
            # Удаляем None значения
            search_queries = [q for q in search_queries if q]
            
            for query in search_queries:
                results = self.spotify_client.search(q=query, type='track', limit=10)
                
                if results['tracks']['items']:
                    # Ищем наиболее подходящий трек
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
            # Сравниваем название
            title_similarity = SequenceMatcher(
                None, target_title.lower(), track['name'].lower()
            ).ratio()
            
            # Сравниваем исполнителя
            track_artists = [artist['name'].lower() for artist in track['artists']]
            artist_similarity = max([
                SequenceMatcher(None, target_artist.lower(), artist).ratio() 
                for artist in track_artists
            ], default=0)
            
            # Общий скор (название важнее)
            total_score = title_similarity * 0.7 + artist_similarity * 0.3
            
            if total_score > best_score and total_score > 0.6:  # Минимальный порог
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
            
            # Создаем плейлист
            playlist = self.spotify_client.user_playlist_create(
                user=user_id,
                name=name,
                description=description or f"Плейлист перенесен из Яндекс Музыки ({len(tracks)} треков)"
            )
            
            playlist_id = playlist['id']
            print(f"✅ Создан плейлист: {name}")
            
            # Добавляем треки порциями (максимум 100 за раз)
            batch_size = 100
            for i in range(0, len(tracks), batch_size):
                batch = tracks[i:i + batch_size]
                self.spotify_client.playlist_add_items(playlist_id, batch)
                print(f"📝 Добавлено {len(batch)} треков (всего: {min(i + batch_size, len(tracks))}/{len(tracks)})")
                time.sleep(0.1)  # Небольшая задержка для избежания rate limiting
            
            return playlist_id
            
        except Exception as e:
            print(f"❌ Ошибка создания плейлиста: {e}")
            raise
    
    def transfer_playlist(self, playlist_name: str = "Мне нравится (из Яндекс Музыки)"):
        """
        Основной метод переноса плейлиста
        
        Args:
            playlist_name: Название плейлиста в Spotify
        """
        print("🚀 Начинаем перенос плейлиста...")
        
        # Получаем треки из Яндекс Музыки
        yandex_tracks = self.get_yandex_liked_tracks()
        
        if not yandex_tracks:
            print("❌ Не удалось получить треки из Яндекс Музыки")
            return
        
        # Ищем треки в Spotify
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
            
            # Небольшая задержка между запросами
            time.sleep(0.1)
        
        # Создаем плейлист
        if spotify_tracks:
            playlist_id = self.create_spotify_playlist(
                name=playlist_name,
                tracks=spotify_tracks,
                description=f"Перенесено из Яндекс Музыки. Найдено: {len(spotify_tracks)}/{len(yandex_tracks)} треков"
            )
            
            print(f"\n🎉 Плейлист успешно создан!")
            print(f"📊 Статистика:")
            print(f"   • Всего треков в Яндекс Музыке: {len(yandex_tracks)}")
            print(f"   • Найдено в Spotify: {len(spotify_tracks)}")
            print(f"   • Не найдено: {len(not_found_tracks)}")
        
        # Сохраняем список ненайденных треков
        if not_found_tracks:
            self._save_not_found_tracks(not_found_tracks)
    
    def _save_not_found_tracks(self, tracks: List[Dict]):
        """Сохранение списка ненайденных треков"""
        try:
            with open('not_found_tracks.json', 'w', encoding='utf-8') as f:
                json.dump(tracks, f, ensure_ascii=False, indent=2)
            print(f"📄 Список ненайденных треков сохранен в not_found_tracks.json")
        except Exception as e:
            print(f"❌ Ошибка сохранения списка ненайденных треков: {e}")


def main():
    """Основная функция"""
    print("🎵 Скрипт переноса плейлиста из Яндекс Музыки в Spotify")
    print("=" * 50)
    
    # Получаем конфигурацию из переменных окружения или просим ввести
    yandex_token = os.getenv('YANDEX_MUSIC_TOKEN')
    spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
    spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')
    
    # Если нет переменных окружения, просим ввести
    if not yandex_token:
        print("Получите токен Яндекс Музыки:")
        print("1. Перейдите на https://music.yandex.ru/")
        print("2. Откройте инструменты разработчика (F12)")
        print("3. Перейдите в Network -> найдите любой запрос к music-web.yandex.net")
        print("4. Скопируйте значение заголовка Authorization")
        yandex_token = input("Введите токен Яндекс Музыки: ").strip()
    
    if not spotify_client_id or not spotify_client_secret:
        print("\nДля работы со Spotify нужно создать приложение:")
        print("1. Перейдите на https://developer.spotify.com/dashboard/")
        print("2. Создайте новое приложение")
        print("3. Добавьте Redirect URI: http://127.0.0.1:8888/callback")
        
        if not spotify_client_id:
            spotify_client_id = input("Введите Spotify Client ID: ").strip()
        if not spotify_client_secret:
            spotify_client_secret = input("Введите Spotify Client Secret: ").strip()
    
    try:
        # Создаем экземпляр класса для переноса
        transfer = MusicTransfer(
            yandex_token=yandex_token,
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            spotify_redirect_uri=spotify_redirect_uri
        )
        
        # Запускаем перенос
        transfer.transfer_playlist()
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main() 