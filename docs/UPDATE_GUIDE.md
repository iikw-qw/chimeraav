# Chimera v9.0 — Руководство по обновлению

## Версионирование

Chimera использует семантическое версионирование: **MAJOR.MINOR.PATCH**
- **MAJOR** — несовместимые изменения, требуется повторный вход
- **MINOR** — новый функционал (обратно совместимый)
- **PATCH** — исправления багов

Текущая версия: **9.0.0**

## Обновление Desktop-версии

### Шаг 1: Получите новую версию
```bash
cd "C:\chimera project"
git pull origin main
```

### Шаг 2: Обновите зависимости
```bash
npm install
py -m pip install -r python-backend/requirements.txt
```

### Шаг 3: Перезапустите
Закройте приложение и запустите заново:
- Через ярлык на рабочем столе
- Или `npm run dev`

### Шаг 4 (опционально): Пересоберите установщик
```bash
py installer/build_installer.py
```

## Миграция базы данных

SQLite-база мигрирует **автоматически** при запуске:
- Новые таблицы создаются через `Base.metadata.create_all`
- Новые колонки добавляются через миграции в `database.py`
- Существующие данные сохраняются

Расположение БД:
- Windows: `%APPDATA%\Chimera\chimera.db`
- macOS: `~/Library/Application Support/Chimera/chimera.db`
- Linux: `~/.local/share/Chimera/chimera.db`

## Инвалидация токенов

При обновлении MAJOR-версии:
- Все JWT-токены инвалидируются
- Пользователи получают уведомление о повторном входе
- Telegram-верификация сохраняется

## Сборка обновлённого установщика

```bash
# Полный цикл сборки
py installer/build_installer.py
```

Скрипт выполняет:
1. Проверку зависимостей (Python, Node.js)
2. `npm install` + `pip install`
3. Генерацию иконок из chimerafoto
4. `vite build` (фронтенд)
5. `electron-builder` (установщик)

Результат: `build/Chimera-9.0.0-Setup.exe`

## Уведомление через бота

После обновления Telegram-бот уведомляет подключённых пользователей:
- Номер новой версии
- Список изменений
- Инструкции (если нужен повторный вход)

## Откат

При проблемах после обновления:
```bash
git log --oneline -10     # найти предыдущий коммит
git checkout <commit>     # откатиться
npm install               # обновить зависимости
```

## Бэкапы

### Ручной бэкап
```powershell
# Windows
copy "$env:APPDATA\Chimera\chimera.db" "chimera_backup.db"
```

### Автоматический бэкап
Рекомендуется настроить регулярное копирование файла `chimera.db`.
