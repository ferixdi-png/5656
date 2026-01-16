@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

cd /d "%~dp0"

echo ========================================
echo   BetBoom Live Scanner
echo ========================================
echo.

REM Проверяем наличие uv и Python
set "RUNTIME_DIR=%~dp0.runtime"
set "UV_EXE=%RUNTIME_DIR%\uv\uv.exe"
set "VENV_PYTHON=%~dp0.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo [INFO] Первый запуск: установка зависимостей...
    echo.
    
    REM Запускаем bootstrap
    powershell.exe -ExecutionPolicy Bypass -File "%~dp0tools\bootstrap_windows.ps1"
    
    if errorlevel 1 (
        echo.
        echo ОШИБКА: Не удалось установить зависимости
        echo Нажмите любую клавишу для выхода...
        pause >nul
        exit /b 1
    )
    
    echo.
    echo Установка завершена!
    echo.
)

REM Запуск приложения
echo Запуск сканера...
echo.

"%VENV_PYTHON%" -m app.main

if errorlevel 1 (
    echo.
    echo ОШИБКА: Приложение завершилось с ошибкой
    echo Нажмите любую клавишу для выхода...
    pause >nul
    exit /b 1
)

