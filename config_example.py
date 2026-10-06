"""Необязательный файл с учетными данными.

Обычно токены удобнее ввести в окне «Настройки» (они сохранятся в data/settings.json).
Этот файл нужен, если хотите хранить их отдельно: скопируйте его в config.py
и заполните. config.py исключен из git.

Приоритет источников: переменные окружения < config.py < data/settings.json.
"""

# Токен Яндекс Музыки (как получить — см. README или окно «Настройки»)
YANDEX_MUSIC_TOKEN = "your_yandex_token_here"

# Приложение Spotify: https://developer.spotify.com/dashboard/
# Redirect URI в приложении должен совпадать с указанным здесь
SPOTIFY_CLIENT_ID = "your_spotify_client_id_here"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret_here"
SPOTIFY_REDIRECT_URI = "http://127.0.0.1:8888/callback"
