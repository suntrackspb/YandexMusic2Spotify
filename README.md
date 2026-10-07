# Yandex Music → Spotify

Десктопное приложение для переноса плейлиста «Мне нравится» из Яндекс Музыки в Spotify. Может создать новый плейлист или дописать недостающие треки в существующий.

> Старая консольная версия без графического интерфейса сохранена в ветке [`legacy-cli`](https://github.com/suntrackspb/YandexMusic2Spotify/tree/legacy-cli).

## Установка

Скачайте сборку для своей системы на странице [Releases](https://github.com/suntrackspb/YandexMusic2Spotify/releases/latest).

**macOS (Apple Silicon)** — `YandexMusic2Spotify-<версия>-macos-arm64.zip`

Распакуйте архив и перенесите `YandexMusic2Spotify.app` в «Программы». Приложение не подписано сертификатом Apple, поэтому при первом запуске macOS его заблокирует. Чтобы открыть, нажмите на приложение правой кнопкой и выберите «Открыть». Если macOS пишет, что приложение повреждено, выполните:

```bash
xattr -dr com.apple.quarantine /Applications/YandexMusic2Spotify.app
```

**Windows** — `YandexMusic2Spotify-<версия>-windows.zip`

Распакуйте архив и запустите `YandexMusic2Spotify.exe`. Если SmartScreen покажет предупреждение, нажмите «Подробнее» → «Выполнить в любом случае». Для работы нужен [Microsoft Edge WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/). В Windows 11 он уже установлен, в Windows 10 его иногда нужно поставить.

**Linux (Debian, Ubuntu и производные)** — `YandexMusic2Spotify-<версия>-linux-amd64.deb`

```bash
sudo apt install ./YandexMusic2Spotify-*-linux-amd64.deb
```

Приложение появится в меню как «Yandex Music → Spotify». Из терминала его можно запустить командой `yandexmusic2spotify`.

### Запуск из исходников

Нужен Python 3.10 или новее.

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

На Linux pywebview нужен GTK или Qt backend, подробности в [документации pywebview](https://pywebview.flowrl.com/guide/installation.html).

## Настройка

При первом запуске откроется окно «Настройки».

**Токен Яндекс Музыки**

1. Откройте DevTools (F12), вкладку Network и включите Preserve log.
2. Перейдите по [ссылке авторизации](https://oauth.yandex.ru/authorize?response_type=token&client_id=23cabbbdc6cd418abb4b39c32c41195d).
3. В фильтре запросов введите `auth?` и найдите запрос `auth?external-domain=music.yandex.ru…`.
4. В заголовке `X-Retpath-Y` скопируйте значение `access_token=`.

**Приложение Spotify**

1. Создайте приложение в [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
2. Добавьте Redirect URI `http://127.0.0.1:8888/callback`. Адрес `localhost` Spotify не принимает.
3. Скопируйте Client ID и Client Secret в настройки.

Настройки сохраняются в `data/settings.json`. Их также можно задать в `config.py` (шаблон лежит в `config_example.py`) или через переменные окружения `YANDEX_MUSIC_TOKEN`, `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI`. Если значение задано в нескольких местах, побеждает источник с наибольшим приоритетом: `data/settings.json` > `config.py` > переменные окружения.

## Как пользоваться

Яндекс Музыка не пускает к аккаунту через ВПН, а Spotify в некоторых регионах работает только через ВПН. Поэтому перенос идет в два шага.

1. **Без ВПН** нажмите «Загрузить лайки». Библиотека сохранится в `data/yandex_library.json`.
2. **С ВПН** (если он нужен для Spotify) нажмите «Подключить Spotify». При первом входе откроется браузер для авторизации. Потом выберите, создать новый плейлист или обновить существующий, и нажмите «Перенести».

Чтобы посмотреть, что получится, не меняя Spotify, включите «Пробный запуск». Результаты можно отфильтровать по статусу и найти нужный трек поиском. Отчет с ненайденными треками и ошибками сохраняется в `data/reports/`.

## Как сопоставляются треки

- Трек засчитывается, только если совпадают и название, и исполнитель. Песня с тем же названием, но другого артиста не подойдет.
- Кириллица транслитерируется, поэтому «Кино» совпадает с «Kino». Пунктуация, `feat.` и пометки вроде «Remastered» при сравнении не учитываются.
- Ремикс, live или акустическая версия не будут приняты за оригинал.
- Если длительность треков известна, она тоже учитывается в оценке.
- Найденные совпадения кэшируются в `data/matches.json`, так что повторная синхронизация проходит быстро.
- При обновлении плейлиста треки, которые в нем уже есть, не добавляются второй раз. Если несколько треков из Яндекса совпали с одним треком Spotify, он добавится один раз.
- Ошибки сети и API показываются отдельно от ненайденных треков.

## Сборка

Готовые сборки создает GitHub Actions ([build.yml](.github/workflows/build.yml)). Сборка запускается при пуше тега `vX.Y.Z` или вручную (workflow_dispatch). Для тега результаты попадают в черновик релиза.

| Платформа | Артефакт | Как собирается |
|---|---|---|
| macOS (arm64) | `.app` в zip | PyInstaller, ad-hoc подпись |
| Windows | zip с `.exe` | PyInstaller onefile, WebView2 |
| Linux | `.deb` | системный python3 + GTK/WebKit2, зависимости в `/opt/yandexmusic2spotify/vendor` |

Каждая сборка проверяется командой `--selftest`: она проверяет ресурсы, бэкенд pywebview и зависимости, не открывая окно.

Собрать локально (macOS или Windows):

```bash
pip install -r requirements-dev.txt
pyinstaller --noconfirm --clean build.spec
```

При запуске из исходников данные хранятся в `data/` рядом с проектом. Собранное приложение хранит их в папке пользователя:

- macOS: `~/Library/Application Support/YandexMusic2Spotify`
- Windows: `%APPDATA%\YandexMusic2Spotify`
- Linux: `~/.local/share/YandexMusic2Spotify`

## Структура

```
main.py              точка входа
ym2sp/
  settings.py        пути и учетные данные
  models.py          модели треков
  matching.py        нормализация и оценка совпадений
  yandex.py          загрузка лайков из Яндекс Музыки
  spotify.py         поиск и плейлисты Spotify
  sync.py            сопоставление и запись в плейлист
  gui.py             мост pywebview <-> Python
  web/               интерфейс (HTML/CSS/JS)
  assets/            иконки (png, ico, icns)
build.spec           сборка PyInstaller (macOS, Windows)
data/                данные пользователя (в git не попадают)
```

## Лицензия

[MIT](LICENSE)
