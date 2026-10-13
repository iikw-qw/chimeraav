# Запуск Chimera

## Главное (одна команда)

```bash
npm run start
```

Из корня проекта `C:\chimera project`. Electron сам поднимет Python-сайдкар на порту 17842 — отдельный терминал для бэкенда **не нужен**.

Если бэкенд уже запущен (например, ты его руками стартанул для отладки) — Electron это увидит и не будет запускать второй.

---

## Режим разработки (hot-reload фронта)

```bash
npm run dev
```

Поднимает Vite-сервер + Electron с авто-обновлением UI. Любая правка в `src/` мгновенно обновляет окно. Сайдкар запускается так же автоматически.

---

## После правок кода

Только для прод-режима (`npm run start`) нужно пересобрать:

```bash
npm run build
```

(Это `vite build` + `tsc` для electron-кода.)

В режиме `npm run dev` пересборка не нужна — Vite это делает сам.

---

## Если что-то не так

| Симптом | Что делать |
|---|---|
| Чёрное окно | Не пересобрано после правок. Запусти `npm run build`, затем `npm run start`. |
| `port 17842 already in use` | Висит старый python: `taskkill /F /IM python.exe` |
| Внизу баннер «backend down» | Сайдкар не стартанул. Запусти руками `cd python-backend && py main.py` и смотри лог. |
| `Cannot find module 'electron'` | `npm install` в корне проекта |
| `ModuleNotFoundError` от Python | `cd python-backend && py -m pip install -r requirements.txt` |
| Окно открывается, но всё пустое | Открой DevTools (Ctrl+Shift+I), смотри ошибки в Console. |

---

## Полная остановка

- Закрыть окно крестиком — Electron уберёт и Python-сайдкар.
- Если что-то залипло: `taskkill /F /IM electron.exe && taskkill /F /IM python.exe`.

---

## Сборка установщика (.exe)

```bash
npm run dist:win
```

Пакетирует приложение через electron-builder в `installer/`.

---

## Полезные адреса (когда бэкенд жив)

- API: `http://127.0.0.1:17842`
- Swagger: `http://127.0.0.1:17842/docs`
- Health: `http://127.0.0.1:17842/health`
- Бэкап БД: `POST http://127.0.0.1:17842/api/settings/backup-now`

---

## Что было исправлено в этой сессии

- `npm run start` грузил Vite dev-сервер вместо собранного `dist/` (флаг `isDev` ошибочно был `true`, когда Electron не упакован) → чёрный экран. Починено: dev включается только по `--dev` или `NODE_ENV=development`.
- Сайдкар при `npm run start` пытался запустить **бандленный** python из `Local/Chimera/python/python.exe`, которого нет вне инсталлятора. Теперь fallback на системный `py` всегда, когда `app.isPackaged === false`.
- Если бэкенд уже работает — сайдкар переиспользует его, а не падает на bind.
- LoadingScreen больше не висит 30 секунд при упавшем бэкенде: тайм-аут 12с, потом UI всё равно показывается, а сайдкар поллится в фоне и подключается, как только бэкенд оживёт.
