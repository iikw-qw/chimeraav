# Chimera v9.0 — Руководство по установке

## Системные требования

| Компонент | Минимум | Рекомендуется |
|-----------|---------|---------------|
| ОС | Windows 10 (x64) | Windows 11 |
| Python | 3.11+ | 3.12+ |
| Node.js | 20+ | 22+ |
| RAM | 4 ГБ | 8 ГБ |
| Диск | 500 МБ | 2 ГБ |
| ADB | Опционально | Для Android |

## Установка на Windows

### Способ 1: Автоматическая установка (рекомендуется)
```powershell
cd "C:\chimera project"
powershell -ExecutionPolicy Bypass -File installer\install_chimera.ps1
```

Скрипт автоматически:
1. Проверит Python и Node.js
2. Установит все зависимости (npm + pip)
3. Создаст ярлык на рабочем столе с иконкой
4. Подготовит приложение к запуску

### Способ 2: Ручная установка
```bash
cd "C:\chimera project"
npm install
py -m pip install -r python-backend/requirements.txt
```

### Способ 3: Установщик (EXE)
1. Запустите `py installer/build_installer.py` для сборки
2. Откройте папку `build/`
3. Запустите `Chimera-9.0.0-Setup.exe`
4. Следуйте мастеру установки

## Запуск приложения

### Desktop режим (рекомендуется)
```bash
# Через ярлык на рабочем столе:
#   Дважды кликните "Chimera Desktop"

# Или через терминал:
cd "C:\chimera project"
npm run dev

# Или через BAT-файл:
run-desktop.bat
```

## Настройка Android-телефонов

### Подготовка устройства
1. **Настройки → О телефоне** → нажмите **Номер сборки** 7 раз
2. **Настройки → Для разработчиков**:
   - ✅ Отладка по USB
   - ✅ Не выключать экран при зарядке
3. Подключите к Wi-Fi (та же сеть, что и компьютер)

### Установка агента (APK)
При подключении телефона по USB агент **установится автоматически** через APK Deployer.

Для ручной установки:
```bash
adb install chimera-agent.apk
adb shell am start -n com.chimera.agent/.MainActivity
adb shell pm grant com.chimera.agent android.permission.SYSTEM_ALERT_WINDOW
```

## Настройка iOS (Jailbreak)

### Определение инструмента
| Чип | iOS | Инструмент |
|------|------|------------|
| A7-A11 (5s–X) | 12-14 | checkra1n |
| A12-A15 | 14.0-14.8 | unc0ver |
| A12+ | 15.0-16.6.1 | Dopamine |

### checkra1n (A7-A11)
1. Скачайте checkra1n с checkra.in
2. Подключите iPhone по USB
3. Переведите в DFU-режим (Power + Home 10 сек → отпустите Power)
4. Дождитесь завершения (2-3 минуты)
5. Откройте Cydia на устройстве

### unc0ver (A12-A15, iOS 14.x)
1. Установите AltStore через AltServer на ПК
2. Загрузите unc0ver.ipa через AltStore
3. Откройте unc0ver → нажмите Jailbreak
4. Дождитесь перезагрузки → откройте Cydia

### Dopamine (A12+, iOS 15-16.6.1)
1. Установите TrollStore через подходящий метод
2. Загрузите Dopamine.tipa через TrollStore
3. Запустите Dopamine → нажмите Jailbreak
4. Установите Sileo (альтернатива Cydia)

### После джейлбрейка — установите:
- **OpenSSH** — для удалённого доступа
- **WebDriverAgent** — для Appium автоматизации
- **Liberty Lite / Shadow / A-Bypass** — скрытие jailbreak

### Настройка Appium (на Mac Mini)
```bash
brew install node
npm install -g appium
appium driver install xcuitest
```

### Настройка прокси для iOS
Создайте mobileconfig профиль или настройте прокси на уровне роутера/VLAN.

## Настройка прокси

В настройках приложения → Прокси:
- **HTTP/HTTPS** — базовый вариант
- **SOCKS5** — продвинутый
- **Residential** — лучший антидетект

Рекомендуемые провайдеры: Bright Data, Smartproxy, 922proxy

## Настройка 2Captcha

1. Зарегистрируйтесь на 2captcha.com
2. Пополните баланс (~$3 на старт)
3. Скопируйте API-ключ
4. В приложении: Настройки → 2Captcha → вставьте ключ → Сохранить

Поддерживаемые капчи: reCAPTCHA v2/v3, hCaptcha, image captcha

## Telegram-бот

### Настройка
1. Создайте бота у @BotFather в Telegram, получите токен
2. Откройте `bot/chimera_bot.py`
3. Замените `ВСТАВЬТЕ_ВАШ_ТОКЕН_СЮДА` на ваш токен
4. Запустите бота:
```bash
cd "C:\chimera project"
py bot/chimera_bot.py
```

### Авторизация через бота
1. В приложении Chimera нажмите **"Получить код"**
2. Откройте бота в Telegram
3. Отправьте: `/verify КОД`
4. Приложение разблокируется автоматически

## Порты

| Компонент | Порт |
|-----------|------|
| Desktop Backend (SQLite) | 17842 |
| Vite Dev Server | 5173 |

## Troubleshooting

### Приложение не запускается
- Проверьте Python: `py --version` (нужен 3.11+)
- Проверьте Node.js: `node --version` (нужен 20+)
- Проверьте порт: `netstat -an | findstr 17842`
- Переустановите зависимости: `npm install`

### Телефон не подключается
- ✅ Телефон и компьютер в одной Wi-Fi сети
- ✅ USB-отладка включена
- ✅ Chimera Agent установлен и запущен
- ✅ Файрвол не блокирует порт

### Чёрный экран в Electron
- Удалите `node_modules` и выполните `npm install`
- Проверьте логи: F12 → Console

### Стрим не работает
- Проверьте WebSocket в DevTools → Network → WS
- Убедитесь, что Agent отправляет данные
- Проверьте разрешение MediaProjection на телефоне

### Ошибки Python
```bash
py -m pip install --upgrade pip
py -m pip install -r python-backend/requirements.txt
```
