#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Общие функции для получения токенов и ключей API: сначала из переменных
окружения, а если их нет — запросом ввода у пользователя.
"""

import os


def get_yandex_token() -> str:
    """Получение токена Яндекс Музыки из окружения или ввода"""
    yandex_token = os.getenv('YANDEX_MUSIC_TOKEN')

    if not yandex_token:
        print("Получите токен Яндекс Музыки:")
        print("1. Перейдите на https://music.yandex.ru/")
        print("2. Откройте инструменты разработчика (F12)")
        print("3. Перейдите в Network -> найдите любой запрос к music-web.yandex.net")
        print("4. Скопируйте значение заголовка Authorization")
        yandex_token = input("Введите токен Яндекс Музыки: ").strip()

    return yandex_token


def get_spotify_credentials() -> tuple:
    """Получение учетных данных Spotify из окружения или ввода"""
    spotify_client_id = os.getenv('SPOTIFY_CLIENT_ID')
    spotify_client_secret = os.getenv('SPOTIFY_CLIENT_SECRET')
    spotify_redirect_uri = os.getenv('SPOTIFY_REDIRECT_URI', 'http://127.0.0.1:8888/callback')

    if not spotify_client_id or not spotify_client_secret:
        print("\nДля работы со Spotify нужно создать приложение:")
        print("1. Перейдите на https://developer.spotify.com/dashboard/")
        print("2. Создайте новое приложение")
        print("3. Добавьте Redirect URI: http://127.0.0.1:8888/callback")

        if not spotify_client_id:
            spotify_client_id = input("Введите Spotify Client ID: ").strip()
        if not spotify_client_secret:
            spotify_client_secret = input("Введите Spotify Client Secret: ").strip()

    return spotify_client_id, spotify_client_secret, spotify_redirect_uri
