@echo off
chcp 65001 >nul
title Chimera Desktop v9.0
color 0A

echo.
echo  ╔══════════════════════════════════════╗
echo  ║     CHIMERA DESKTOP v9.0            ║
echo  ╚══════════════════════════════════════╝
echo.

cd /d "C:\chimera project"

echo  [1/3] Проверка Python...
py --version >nul 2>&1
if %errorlevel% neq 0 (
    color 0C
    echo  ОШИБКА: Python не найден!
    echo  Установите Python 3.11+ с python.org
    pause
    exit /b 1
)
echo        Python OK

echo  [2/3] Запуск backend (порт 17842)...
start /min "Chimera Backend" py python-backend/main.py

echo  [3/3] Запуск Electron...
timeout /t 3 /nobreak >nul
npx electron . 2>nul

echo.
echo  Chimera закрыта.
taskkill /f /fi "WINDOWTITLE eq Chimera Backend" >nul 2>&1
