#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Шаг 1: получение понравившихся треков из Яндекс Музыки и сохранение в JSON.

⚠️ Запускайте этот скрипт БЕЗ ВПН — Яндекс Музыка блокирует доступ
при подключении через ВПН (гео-блокировка).
"""

from yandex_fetcher import YandexFetcher, save_tracks_to_json, DEFAULT_TRACKS_FILE
from credentials_input import get_yandex_token

try:
    import config
    config.setup_environment()
    print("✅ Конфигурация загружена из config.py")
except ImportError:
    pass


def main():
    print("🎵 Шаг 1/2: Получение треков из Яндекс Музыки")
    print("⚠️  Убедитесь, что ВПН ВЫКЛЮЧЕН перед запуском этого шага")
    print("=" * 50)

    yandex_token = get_yandex_token()

    try:
        fetcher = YandexFetcher(yandex_token=yandex_token)
        tracks = fetcher.get_liked_tracks()

        if not tracks:
            print("❌ Не удалось получить треки из Яндекс Музыки")
            return

        save_tracks_to_json(tracks, DEFAULT_TRACKS_FILE)

        print(f"\n✅ Готово! Сохранено {len(tracks)} треков в {DEFAULT_TRACKS_FILE}")
        print("👉 Теперь включите ВПН и запустите music_transfer.py или playlist_updater.py")

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")


if __name__ == "__main__":
    main()
