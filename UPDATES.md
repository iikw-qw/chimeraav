# Распространение обновлений Chimera

Этот документ описывает, как редактор (вы) выпускает обновление через Claude
и как это обновление автоматически приезжает ко всем пользователям, у которых
установлена Chimera.

## Архитектура

Каждая копия Chimera при запуске:

1. Опрашивает сервер релизов `https://updates.chimera.app/manifest.json`
   (или ваш self-hosted URL).
2. Сравнивает локальную версию (`APP_VERSION` в `src/pages/AuthGate.tsx`)
   с серверной.
3. Если серверная новее — скачивает asar-патч и применяет его при следующем
   старте Electron-окна.
4. Параллельно бэкенд (FastAPI) подтягивает новый Python-код через `pip install`
   из приватного индекса.
5. После успешного применения — авторизация в приложении сбрасывается
   (`/api/auth/version` меняется), и каждый пользователь должен пройти
   `/start КОД` в боте заново. Это даёт вам контроль над тем, кто продолжает
   пользоваться приложением после обновления.

## Сервер релизов

Минимальный сервер — статический хостинг (S3, GitHub Pages, Cloudflare R2).
Структура каталога:

```
manifest.json
releases/
  9.0/
    chimera-9.0-electron.asar
    chimera-9.0-backend.whl
    notes.md
  9.1/
    ...
```

Пример `manifest.json`:

```json
{
  "latest": "9.1",
  "channels": {
    "stable": {
      "version": "9.1",
      "electron": "https://updates.chimera.app/releases/9.1/chimera-9.1-electron.asar",
      "electron_sha256": "abcdef...",
      "backend": "https://updates.chimera.app/releases/9.1/chimera-9.1-backend.whl",
      "backend_sha256": "123456...",
      "released_at": "2026-04-25T12:00:00Z",
      "notes_url": "https://updates.chimera.app/releases/9.1/notes.md"
    }
  }
}
```

## Релизный цикл с Claude

1. Скажите Claude: «обнови приложение, добавь X».
2. Claude правит код и собирает дистрибутив:
   ```bash
   npm run build
   cd python-backend && python -m build
   ```
3. Загрузите получившиеся файлы в `releases/<version>/` и обновите
   `manifest.json` (поднимите `latest` и SHA-суммы).
4. Поднимите `_CURRENT_VERSION` в `python-backend/app/api/auth.py` и
   `APP_VERSION` в `src/pages/AuthGate.tsx`. Это форсирует повторную
   авторизацию через бот после обновления — то поведение, которое вы
   просили.

## Автоматическое применение у пользователя

В Electron `main.js` уже есть стартовый probe бэкенда. Добавьте к нему
вызов `electron-updater` (одна из стабильных схем):

```js
// в main.js
const { autoUpdater } = require('electron-updater')
autoUpdater.setFeedURL({
  provider: 'generic',
  url: 'https://updates.chimera.app/releases/',
})
autoUpdater.checkForUpdatesAndNotify()
```

Бэкенд обновляется при следующем старте через скрипт `update_backend.py`,
который Electron вызывает после квита окна:

```python
import subprocess, sys
subprocess.check_call([
    sys.executable, "-m", "pip", "install", "--upgrade",
    "--index-url", "https://pypi.chimera.app/simple", "chimera-backend",
])
```

## Безопасность

- Все артефакты подписываются — фронтенд проверяет SHA256, который пришёл из
  manifest. Без совпадения — обновление пропускается.
- Манифест отдаётся через HTTPS с строгими CORS только из домена приложения.
- Версия `_CURRENT_VERSION` в `auth.py` синхронизирована с релизной — старые
  коды авторизации становятся недействительны после обновления, и каждый
  установленный экземпляр проходит подтверждение через бот заново.

## Откат

Если новая версия сломалась:

1. Поднимите в `manifest.json` поле `latest` обратно на стабильную версию.
2. Все запущенные клиенты при следующей проверке (раз в 30 минут) увидят
   «откат» и заново скачают предыдущий релиз.
3. SHA-сумма гарантирует, что переход безопасен.

## Чек-лист перед релизом

- [ ] `npm run build` проходит без ошибок.
- [ ] `pytest` зелёный.
- [ ] `_CURRENT_VERSION` и `APP_VERSION` подняты согласованно.
- [ ] manifest.json обновлён, sha256 пересчитаны.
- [ ] notes.md содержит понятный список изменений на русском.
- [ ] На тестовом устройстве (один из ваших телефонов или виртуалка)
      проверен полный путь: запуск → проверка обновления → авторизация
      через бот → успешный старт.
