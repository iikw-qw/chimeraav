# Chimera

Desktop-приложение для управления парком Android-устройств и автоматизации соц.сетей.
Electron 28 + React 18 + Vite UI, FastAPI sidecar на Python 3.11.

## Для пользователей

1. Скачайте `Chimera-Setup.exe` со страницы релизов.
2. Запустите установщик → пройдите шаги мастера. На последнем шаге автоматически скачается Python 3.11 embedded и необходимые зависимости (~200 МБ) в `%LOCALAPPDATA%\Chimera\python`.
3. Дважды кликните по ярлыку **Chimera** на рабочем столе.

При первом запуске откроется мастер настройки: подключите телефоны по USB, включите отладку, добавьте аккаунты и первый датасет фото.

## Для разработчиков

Требования: Node.js 18+, Python 3.11, npm, Git.

```bash
git clone <repo-url> chimera
cd chimera
npm install
pip install -r python-backend/requirements.txt
npm run dev
```

`npm run dev` поднимает Vite на `http://localhost:5173`, компилирует Electron main (`electron/` → `dist-electron/`) и запускает Chimera вместе с локальным Python-сайдкаром на порту `17842`. Готовность сайдкара определяется по `GET /health`.

### Сборка инсталлятора

```powershell
npm run dist:win
# или полный пайплайн
powershell -ExecutionPolicy Bypass -File scripts/build.ps1
```

Результат — `build/Chimera-<version>-Setup.exe` (NSIS) и portable-`.exe`. Инсталлятор non-one-click, с выбором папки и созданием ярлыка **Chimera** на рабочем столе и в меню Пуск.

### Embedded Python

При первом запуске установщик вызывает `installer/download-deps.ps1`, который:

- скачивает `python-3.11.9-embed-amd64.zip` в `%LOCALAPPDATA%\Chimera\python`;
- включает `site-packages` в `python311._pth`;
- ставит pip и `resources/backend/requirements.txt`;
- создаёт `%APPDATA%\Chimera\{datasets,cleaned,exports,backups}`.

Запустить провижининг вручную:

```powershell
powershell -ExecutionPolicy Bypass -File installer\download-deps.ps1 -InstallDir "C:\Program Files\Chimera"
```

### Генерация иконок

После замены `src/assets/logo.jfif`:

```bash
python scripts/convert-icon.py
```

Создаст `resources/icon.ico` (16–256px), `resources/icon.png` (512×512) и `resources/tray-icon.png` (16×16).

## Структура проекта

```
electron/         Electron main: main, preload, sidecar, browser-view, tray, menu, store, ipc
src/              React renderer (Vite, Tailwind, zustand, react-query)
python-backend/   FastAPI + SQLAlchemy 2 + APScheduler
scripts/          convert-icon.py, build.ps1
installer/        download-deps.ps1 (provisioning Python runtime)
resources/        иконки, графика для electron-builder
```

## Папка данных

- Windows: `%APPDATA%\Chimera`
- macOS: `~/Library/Application Support/Chimera`
- Linux: `$XDG_DATA_HOME/Chimera` (или `~/.local/share/Chimera`)

Переопределяется переменной окружения `CHIMERA_DATA_DIR`. Сайдкар создаёт `datasets/`, `cleaned/`, `exports/`, `backups/` и `chimera.db` (SQLite, WAL).

## Заметки

- `resources/icon.ico`, `resources/icon.png`, `resources/tray-icon.png` генерируются из `src/assets/logo.jfif` скриптом `scripts/convert-icon.py`.
- Сайдкар завершает работу корректно: SIGTERM (3 с grace) → SIGKILL.
