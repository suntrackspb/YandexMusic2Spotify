# -*- mode: python ; coding: utf-8 -*-
"""Спецификация сборки для macOS и Windows.

Linux собирается не через PyInstaller, а в .deb поверх системного python3
(см. .github/workflows/build.yml): PyGObject/WebKit2 плохо переносимы во frozen-бандле.

Запуск:  pyinstaller --noconfirm --clean build.spec
"""

import sys

from PyInstaller.utils.hooks import collect_all, copy_metadata

APP_NAME = "YandexMusic2Spotify"
BUNDLE_ID = "com.suntrackspb.yandexmusic2spotify"

datas = [("ym2sp/web", "ym2sp/web"), ("ym2sp/assets", "ym2sp/assets")]
binaries = []
hiddenimports = []


def _collect(package):
    """Забрать пакет целиком: data-файлы, бинарники и динамические импорты."""
    global datas, binaries, hiddenimports
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden


# pywebview грузит бэкенды динамически и везет свои webview/js/*.js
_collect("webview")
datas += copy_metadata("pywebview")
# yandex_music регистрирует модели через динамические импорты
_collect("yandex_music")

if sys.platform == "win32":
    # WebView2 через pythonnet: нативные DLL + рантайм-конфиг
    _collect("clr_loader")
    _collect("pythonnet")
    hiddenimports += ["webview.platforms.edgechromium", "webview.platforms.winforms"]
    icon = "ym2sp/assets/icon.ico"
elif sys.platform == "darwin":
    hiddenimports += ["webview.platforms.cocoa"]
    icon = "ym2sp/assets/icon.icns"
else:
    hiddenimports += ["webview.platforms.gtk"]
    icon = None

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "PySide6", "PyQt5", "PyQt6"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe_options = dict(
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

if sys.platform == "win32":
    # Windows: один exe (onefile). Распаковка во временную папку при запуске
    # заодно снимает «метку интернета» с DLL — иначе .NET/pythonnet может
    # молча отказаться их грузить из распакованного Проводником zip.
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **exe_options)
    # Консольный вариант для диагностики: все ошибки видны в терминале
    exe_console = EXE(
        pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None,
        **(exe_options | {"name": f"{APP_NAME}-console", "console": True}),
    )
else:
    # macOS: .app — и так один объект, onefile внутри бандла не нужен
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_options)
    coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, upx_exclude=[], name=APP_NAME)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name=f"{APP_NAME}.app",
        icon=icon,
        bundle_identifier=BUNDLE_ID,
        info_plist={
            "CFBundleName": "Yandex Music to Spotify",
            "CFBundleDisplayName": "Yandex Music → Spotify",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "LSApplicationCategoryType": "public.app-category.music",
        },
    )
