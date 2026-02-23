#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Модуль для обновления существующих плейлистов Spotify из Яндекс Музыки.
Сравнивает треки и добавляет только новые.
"""

import os
import json
import time
from typing import List, Dict, Optional, Tuple, Set
from difflib import SequenceMatcher
from music_transfer import MusicTransfer


class PlaylistUpdater(MusicTransfer):
    """
    Класс для обновления существующих плейлистов Spotify из Яндекс Музыки.
    Наследует функциональность MusicTransfer и расширяет её.
    """
    
    def __init__(self, yandex_token: str, spotify_client_id: str, 
                 spotify_client_secret: str, spotify_redirect_uri: str):
        """
        Инициализация обновлятора плейлистов
        
        Args:
            yandex_token: Токен для доступа к Яндекс Музыке
            spotify_client_id: Client ID приложения Spotify
            spotify_client_secret: Client Secret приложения Spotify
            spotify_redirect_uri: URI для перенаправления после авторизации
        """
        super().__init__(yandex_token, spotify_client_id, spotify_client_secret, spotify_redirect_uri)
    
    def get_user_playlists(self) -> List[Dict]:
        """
        Получение всех плейлистов пользователя в Spotify
        
        Returns:
            Список словарей с информацией о плейлистах
        """
        try:
            playlists = []
            offset = 0
            limit = 50
            
            while True:
                results = self.spotify_client.current_user_playlists(limit=limit, offset=offset)
                playlists.extend(results['items'])
                
                if len(results['items']) < limit:
                    break
                offset += limit
            
            return playlists
            
        except Exception as e:
            print(f"❌ Ошибка получения плейлистов: {e}")
            return []
    
    def find_playlist_by_name(self, playlist_name: str) -> Optional[Dict]:
        """
        Поиск плейлиста по названию
        
        Args:
            playlist_name: Название плейлиста для поиска
            
        Returns:
            Информация о плейлисте или None если не найден
        """
        playlists = self.get_user_playlists()
        
        for playlist in playlists:
            if playlist['name'].lower() == playlist_name.lower():
                return playlist
        
        return None
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict]:
        """
        Получение всех треков из плейлиста Spotify
        
        Args:
            playlist_id: ID плейлиста
            
        Returns:
            Список словарей с информацией о треках
        """
        try:
            tracks_info = []
            offset = 0
            limit = 100
            
            while True:
                results = self.spotify_client.playlist_items(
                    playlist_id, limit=limit, offset=offset
                )
                
                for item in results['items']:
                    track = item['track']
                    if track and track['type'] == 'track':
                        track_info = {
                            'title': track['name'],
                            'artist': ', '.join([artist['name'] for artist in track['artists']]),
                            'album': track['album']['name'],
                            'spotify_id': track['id'],
                            'spotify_uri': track['uri']
                        }
                        tracks_info.append(track_info)
                
                if len(results['items']) < limit:
                    break
                offset += limit
            
            return tracks_info
            
        except Exception as e:
            print(f"❌ Ошибка получения треков плейлиста: {e}")
            return []
    
    def normalize_track_info(self, title: str, artist: str) -> str:
        """
        Нормализация информации о треке для сравнения
        
        Args:
            title: Название трека
            artist: Исполнитель
            
        Returns:
            Нормализованная строка для сравнения
        """
        # Приводим к нижнему регистру и убираем лишние пробелы
        normalized_title = title.lower().strip()
        normalized_artist = artist.lower().strip()
        
        # Убираем специальные символы и лишние пробелы
        import re
        normalized_title = re.sub(r'[^\w\s]', '', normalized_title)
        normalized_artist = re.sub(r'[^\w\s]', '', normalized_artist)
        
        # Убираем множественные пробелы
        normalized_title = re.sub(r'\s+', ' ', normalized_title)
        normalized_artist = re.sub(r'\s+', ' ', normalized_artist)
        
        return f"{normalized_artist} - {normalized_title}"
    
    def is_track_similar(self, track1: Dict, track2: Dict, similarity_threshold: float = 0.85) -> bool:
        """
        Проверка схожести двух треков
        
        Args:
            track1: Первый трек для сравнения
            track2: Второй трек для сравнения
            similarity_threshold: Порог схожести (0.0 - 1.0)
            
        Returns:
            True если треки схожи, False иначе
        """
        normalized1 = self.normalize_track_info(track1['title'], track1['artist'])
        normalized2 = self.normalize_track_info(track2['title'], track2['artist'])
        
        similarity = SequenceMatcher(None, normalized1, normalized2).ratio()
        
        return similarity >= similarity_threshold
    
    def find_missing_tracks(self, yandex_tracks: List[Dict], 
                          spotify_tracks: List[Dict]) -> List[Dict]:
        """
        Поиск треков из Яндекс Музыки, которых нет в Spotify плейлисте
        
        Args:
            yandex_tracks: Треки из Яндекс Музыки
            spotify_tracks: Треки из Spotify плейлиста
            
        Returns:
            Список треков, которых нет в Spotify плейлисте
        """
        missing_tracks = []
        
        print(f"🔍 Сравнение треков...")
        print(f"   • Треков в Яндекс Музыке: {len(yandex_tracks)}")
        print(f"   • Треков в Spotify плейлисте: {len(spotify_tracks)}")
        
        for yandex_track in yandex_tracks:
            found_similar = False
            
            for spotify_track in spotify_tracks:
                if self.is_track_similar(yandex_track, spotify_track):
                    found_similar = True
                    break
            
            if not found_similar:
                missing_tracks.append(yandex_track)
        
        print(f"   • Найдено новых треков: {len(missing_tracks)}")
        return missing_tracks
    
    def update_spotify_playlist(self, playlist_id: str, new_tracks: List[str]) -> bool:
        """
        Добавление новых треков в существующий плейлист Spotify
        
        Args:
            playlist_id: ID плейлиста для обновления
            new_tracks: Список Spotify URI новых треков
            
        Returns:
            True если успешно обновлен, False иначе
        """
        try:
            if not new_tracks:
                print("✅ Нет новых треков для добавления")
                return True
            
            # Добавляем треки порциями (максимум 100 за раз)
            batch_size = 100
            total_added = 0
            
            for i in range(0, len(new_tracks), batch_size):
                batch = new_tracks[i:i + batch_size]
                self.spotify_client.playlist_add_items(playlist_id, batch)
                total_added += len(batch)
                print(f"📝 Добавлено {len(batch)} новых треков (всего: {total_added}/{len(new_tracks)})")
                time.sleep(0.1)  # Небольшая задержка для избежания rate limiting
            
            return True
            
        except Exception as e:
            print(f"❌ Ошибка обновления плейлиста: {e}")
            return False
    
    def update_playlist_from_yandex(self, playlist_name: str, 
                                  create_if_not_exists: bool = False) -> bool:
        """
        Основной метод обновления плейлиста из Яндекс Музыки
        
        Args:
            playlist_name: Название плейлиста в Spotify для обновления
            create_if_not_exists: Создать плейлист если не существует
            
        Returns:
            True если успешно обновлен, False иначе
        """
        print("🔄 Начинаем обновление плейлиста...")
        
        # Получаем треки из Яндекс Музыки
        print("📥 Получение треков из Яндекс Музыки...")
        yandex_tracks = self.get_yandex_liked_tracks()
        
        if not yandex_tracks:
            print("❌ Не удалось получить треки из Яндекс Музыки")
            return False
        
        # Ищем плейлист в Spotify
        print(f"🔍 Поиск плейлиста '{playlist_name}' в Spotify...")
        playlist = self.find_playlist_by_name(playlist_name)
        
        if not playlist:
            if create_if_not_exists:
                print(f"📝 Плейлист не найден, создаем новый...")
                # Используем метод из родительского класса
                spotify_uris = []
                not_found_tracks = []
                
                print("🔍 Поиск треков в Spotify...")
                for i, track in enumerate(yandex_tracks, 1):
                    print(f"[{i}/{len(yandex_tracks)}] Ищем: {track['artist']} - {track['title']}")
                    
                    spotify_uri = self.search_spotify_track(
                        track['title'], track['artist'], track['album']
                    )
                    
                    if spotify_uri:
                        spotify_uris.append(spotify_uri)
                        print(f"  ✅ Найден")
                    else:
                        not_found_tracks.append(track)
                        print(f"  ❌ Не найден")
                    
                    time.sleep(0.1)
                
                if spotify_uris:
                    self.create_spotify_playlist(
                        name=playlist_name,
                        tracks=spotify_uris,
                        description=f"Плейлист создан и синхронизирован с Яндекс Музыкой"
                    )
                    
                    if not_found_tracks:
                        self._save_not_found_tracks(not_found_tracks)
                    
                    return True
                else:
                    print("❌ Не найдено треков для создания плейлиста")
                    return False
            else:
                print(f"❌ Плейлист '{playlist_name}' не найден")
                return False
        
        # Получаем существующие треки из плейлиста
        print("📥 Получение существующих треков из плейлиста...")
        spotify_tracks = self.get_playlist_tracks(playlist['id'])
        
        # Находим недостающие треки
        missing_tracks = self.find_missing_tracks(yandex_tracks, spotify_tracks)
        
        if not missing_tracks:
            print("✅ Плейлист уже актуален, новых треков не найдено")
            return True
        
        # Ищем недостающие треки в Spotify
        print(f"🔍 Поиск {len(missing_tracks)} новых треков в Spotify...")
        new_spotify_uris = []
        not_found_tracks = []
        
        for i, track in enumerate(missing_tracks, 1):
            print(f"[{i}/{len(missing_tracks)}] Ищем: {track['artist']} - {track['title']}")
            
            spotify_uri = self.search_spotify_track(
                track['title'], track['artist'], track['album']
            )
            
            if spotify_uri:
                new_spotify_uris.append(spotify_uri)
                print(f"  ✅ Найден")
            else:
                not_found_tracks.append(track)
                print(f"  ❌ Не найден")
            
            time.sleep(0.1)
        
        # Обновляем плейлист
        if new_spotify_uris:
            success = self.update_spotify_playlist(playlist['id'], new_spotify_uris)
            
            if success:
                print(f"\n🎉 Плейлист успешно обновлен!")
                print(f"📊 Статистика обновления:")
                print(f"   • Треков было в плейлисте: {len(spotify_tracks)}")
                print(f"   • Новых треков найдено: {len(new_spotify_uris)}")
                print(f"   • Треков стало в плейлисте: {len(spotify_tracks) + len(new_spotify_uris)}")
                print(f"   • Не найдено в Spotify: {len(not_found_tracks)}")
                
                # Сохраняем список ненайденных треков
                if not_found_tracks:
                    self._save_not_found_tracks(not_found_tracks, 
                                              filename=f'update_not_found_tracks_{int(time.time())}.json')
                
                return True
        
        print("❌ Не найдено новых треков для добавления")
        return False
    
    def _save_not_found_tracks(self, tracks: List[Dict], 
                             filename: str = 'not_found_tracks.json'):
        """
        Сохранение списка ненайденных треков с указанием имени файла
        
        Args:
            tracks: Список ненайденных треков
            filename: Имя файла для сохранения
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(tracks, f, ensure_ascii=False, indent=2)
            print(f"📄 Список ненайденных треков сохранен в {filename}")
        except Exception as e:
            print(f"❌ Ошибка сохранения списка ненайденных треков: {e}")
    
    def show_playlists_menu(self) -> Optional[str]:
        """
        Показывает меню выбора плейлиста для обновления
        
        Returns:
            Название выбранного плейлиста или None
        """
        playlists = self.get_user_playlists()
        
        if not playlists:
            print("❌ Плейлисты не найдены")
            return None
        
        print("\n📋 Ваши плейлисты в Spotify:")
        print("-" * 50)
        
        for i, playlist in enumerate(playlists, 1):
            track_count = playlist['tracks']['total']
            print(f"{i:2d}. {playlist['name']} ({track_count} треков)")
        
        print(f"{len(playlists) + 1:2d}. Создать новый плейлист")
        print(" 0. Отмена")
        
        while True:
            try:
                choice = input(f"\nВыберите плейлист (1-{len(playlists) + 1}, 0 для отмены): ").strip()
                
                if choice == '0':
                    return None
                
                choice_num = int(choice)
                
                if choice_num == len(playlists) + 1:
                    # Создать новый плейлист
                    new_name = input("Введите название нового плейлиста: ").strip()
                    if new_name:
                        return new_name
                    else:
                        print("❌ Название не может быть пустым")
                        continue
                
                if 1 <= choice_num <= len(playlists):
                    return playlists[choice_num - 1]['name']
                else:
                    print("❌ Неверный выбор")
                    
            except ValueError:
                print("❌ Введите число")
            except KeyboardInterrupt:
                print("\n👋 Отменено пользователем")
                return None


def main():
    """Основная функция для запуска обновления плейлиста"""
    print("🔄 Обновление плейлиста Spotify из Яндекс Музыки")
    print("=" * 50)
    
    # Получаем конфигурацию
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
        # Создаем экземпляр обновлятора
        updater = PlaylistUpdater(
            yandex_token=yandex_token,
            spotify_client_id=spotify_client_id,
            spotify_client_secret=spotify_client_secret,
            spotify_redirect_uri=spotify_redirect_uri
        )
        
        # Показываем меню выбора плейлиста
        playlist_name = updater.show_playlists_menu()
        
        if playlist_name:
            # Запускаем обновление (создаем если не существует)
            updater.update_playlist_from_yandex(
                playlist_name=playlist_name,
                create_if_not_exists=True
            )
        else:
            print("👋 Операция отменена")
        
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()