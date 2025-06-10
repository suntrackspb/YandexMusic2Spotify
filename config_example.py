#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Пример файла конфигурации для скрипта переноса музыки.
Скопируйте этот файл в config.py и заполните свои данные.
"""

import os

# Токен Яндекс Музыки
# Получить можно через браузер:
# 1. Откройте DevTools (F12)
# 2. На вкладке Network включите Preserve log (Chrome) или непрерывный лог (Firefox)
# 3. Перейдите по ссылке: https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d
# 4. В фильтре введите: auth?
# 5. Найдите запрос типа auth?external-domain=music.yandex.ru...
# 6. В Headers найдите X-Retpath-Y и скопируйте токен из access_token=
YANDEX_MUSIC_TOKEN = "your_yandex_token_here"

# Spotify API credentials
# Получить можно в Spotify Developer Dashboard:
# 1. Перейдите на https://developer.spotify.com/dashboard/
# 2. Создайте новое приложение
# 3. Добавьте Redirect URI: http://localhost:8888/callback
SPOTIFY_CLIENT_ID = "your_spotify_client_id_here"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret_here"
SPOTIFY_REDIRECT_URI = "http://localhost:8888/callback"

# Альтернативно, можно задать через переменные окружения:
# export YANDEX_MUSIC_TOKEN="your_token"
# export SPOTIFY_CLIENT_ID="your_client_id"
# export SPOTIFY_CLIENT_SECRET="your_client_secret"
# export SPOTIFY_REDIRECT_URI="http://localhost:8888/callback"

def setup_environment():
    """Устанавливает переменные окружения из этого файла"""
    os.environ['YANDEX_MUSIC_TOKEN'] = YANDEX_MUSIC_TOKEN
    os.environ['SPOTIFY_CLIENT_ID'] = SPOTIFY_CLIENT_ID
    os.environ['SPOTIFY_CLIENT_SECRET'] = SPOTIFY_CLIENT_SECRET
    os.environ['SPOTIFY_REDIRECT_URI'] = SPOTIFY_REDIRECT_URI


if __name__ == "__main__":
    print("Это пример файла конфигурации.")
    print("Скопируйте его в config.py и заполните своими данными.") 