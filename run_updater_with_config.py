#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Запуск обновлятора плейлистов с использованием файла конфигурации
"""

import sys
import os

try:
    # Попытка импорта файла конфигурации
    import config
    
    # Установка переменных окружения
    config.setup_environment()
    print("✅ Конфигурация загружена из config.py")
    
except ImportError:
    print("❌ Файл config.py не найден!")
    print("Скопируйте config_example.py в config.py и заполните настройки.")
    sys.exit(1)

# Импорт и запуск обновлятора плейлистов
from playlist_updater import main

if __name__ == "__main__":
    main() 