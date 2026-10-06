#!/usr/bin/env python3
"""Запуск приложения: python main.py [--debug | --selftest]"""

import argparse
import sys
from pathlib import Path


def selftest() -> int:
    """Проверка собранного артефакта без открытия окна.

    Ловит поломки, которые иначе всплывают только у пользователя: потерянные
    data-файлы, ненайденный бэкенд pywebview, неупакованные зависимости.
    Отчет дублируется в selftest.log — у windowed-сборки на Windows нет консоли.
    """
    notes, problems = [], []

    def check(label, fn):
        try:
            result = fn()
            notes.append(f"ok   {label}{': ' + str(result) if result else ''}")
        except Exception as exc:  # noqa: BLE001 - интересует любой сбой
            problems.append(f"FAIL {label}: {exc!r}")

    import webview

    from ym2sp import __version__, gui
    from ym2sp.settings import DATA_DIR

    for label, target in (("web/index.html", gui.INDEX_FILE), ("icon", gui.ICON_FILE)):
        if Path(target).is_file():
            notes.append(f"ok   resource {label}")
        else:
            problems.append(f"FAIL resource {label} not found: {target}")

    webview_js = Path(webview.__file__).resolve().parent / "js"
    if webview_js.is_dir():
        notes.append("ok   pywebview js assets")
    else:
        problems.append(f"FAIL pywebview js assets missing: {webview_js}")

    check(f"gui backend {gui.GUI_BACKEND}", lambda: __import__(f"webview.platforms.{gui.GUI_BACKEND}") and None)
    if sys.platform == "win32":
        # Загружает .NET и Python.Runtime.dll — именно это ломается на Windows
        check("pythonnet clr", lambda: __import__("clr") and None)

        def load_icon_like_winforms():
            # Тот же вызов, что делает pywebview: невалидная иконка роняет процесс
            import clr

            clr.AddReference("System.Drawing")
            from System.Drawing import Icon

            Icon(str(gui.ICON_FILE)).Dispose()

        check("window icon loads in System.Drawing", load_icon_like_winforms)
    check("yandex_music", lambda: __import__("yandex_music").__version__)
    check("spotipy", lambda: __import__("spotipy") and None)
    check("matching", lambda: __import__("ym2sp.sync") and None)

    def data_dir_writable():
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        probe = DATA_DIR / ".selftest"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return DATA_DIR

    check("data dir", data_dir_writable)

    report = "\n".join([
        f"selftest v{__version__} on {sys.platform}, frozen={getattr(sys, 'frozen', False)}",
        *notes,
        *problems,
    ])
    print(report)
    try:
        Path("selftest.log").write_text(report + "\n", encoding="utf-8")
    except OSError:
        pass
    return 1 if problems else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Перенос «Мне нравится» из Яндекс Музыки в Spotify")
    parser.add_argument("--debug", action="store_true", help="открыть инструменты разработчика в окне")
    parser.add_argument("--selftest", action="store_true", help="проверить сборку без запуска окна")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())

    from ym2sp.logs import log, setup_logging, show_fatal_error

    setup_logging()
    log.info("Запуск, platform=%s, frozen=%s", sys.platform, getattr(sys, "frozen", False))
    try:
        from ym2sp.gui import run

        run(debug=args.debug)
    except Exception as exc:
        log.exception("Не удалось запустить приложение")
        hint = ""
        if sys.platform == "win32":
            hint = (
                "\n\nПроверьте, что установлен Microsoft Edge WebView2 Runtime:\n"
                "https://developer.microsoft.com/microsoft-edge/webview2/"
            )
        show_fatal_error(f"Не удалось запустить приложение:\n{exc}{hint}")
        sys.exit(1)


if __name__ == "__main__":
    main()
