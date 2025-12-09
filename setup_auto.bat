@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   АВТОМАТИЧЕСКАЯ УСТАНОВКА KIE BOT
echo ========================================
echo.

:: Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python не найден!
    echo.
    echo [АВТОМАТИЧЕСКАЯ УСТАНОВКА PYTHON]
    echo.
    echo Скачиваю Python 3.11...
    echo.
    
    :: Создаем временную папку
    if not exist "%TEMP%\python_installer" mkdir "%TEMP%\python_installer"
    cd "%TEMP%\python_installer"
    
    :: Скачиваем Python (прямая ссылка на последнюю версию)
    echo Скачивание установщика Python...
    echo Это может занять несколько минут...
    powershell -Command "Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile 'python-installer.exe'"
    
    if not exist "python-installer.exe" (
        echo.
        echo [ОШИБКА] Не удалось скачать Python автоматически.
        echo.
        echo Пожалуйста, установите Python вручную:
        echo 1. Откройте: https://www.python.org/downloads/
        echo 2. Скачайте Python 3.8 или выше
        echo 3. При установке ОБЯЗАТЕЛЬНО отметьте "Add Python to PATH"
        echo 4. После установки перезапустите этот скрипт
        echo.
        pause
        exit /b 1
    )
    
    echo.
    echo Устанавливаю Python с опцией "Add Python to PATH"...
    echo Пожалуйста, подождите...
    echo.
    :: Установка Python с автоматическими параметрами
    python-installer.exe /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
    
    :: Ждем завершения установки
    timeout /t 10 /nobreak >nul
    
    :: Очистка
    cd /d "%~dp0"
    rmdir /s /q "%TEMP%\python_installer" 2>nul
    
    :: Проверка после установки
    python --version >nul 2>&1
    if errorlevel 1 (
        echo.
        echo [!] Python установлен, но не найден в PATH.
        echo Перезапустите командную строку или перезагрузите компьютер.
        echo Затем запустите setup.bat снова.
        pause
        exit /b 1
    )
)

echo [✓] Python найден
python --version
echo.

:: Обновление pip
echo [1/4] Обновление pip...
python -m pip install --upgrade pip --quiet
echo [✓] pip обновлен
echo.

:: Установка зависимостей
echo [2/4] Установка зависимостей...
python -m pip install -r requirements.txt --quiet

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить зависимости!
    echo Попробуйте запустить: python -m pip install -r requirements.txt
    pause
    exit /b 1
)

echo [✓] Зависимости установлены
echo.

:: Создание .env
echo [3/4] Настройка .env файла...
echo.

if exist .env (
    echo [!] Файл .env уже существует!
    set /p OVERWRITE="Перезаписать? (y/n): "
    if /i not "!OVERWRITE!"=="y" (
        echo Установка отменена.
        pause
        exit /b 0
    )
    echo.
)

:: Запрос данных
echo Введите необходимые данные (можно оставить пустым для опциональных):
echo.

set /p BOT_TOKEN="[ОБЯЗАТЕЛЬНО] TELEGRAM_BOT_TOKEN: "
if "!BOT_TOKEN!"=="" (
    echo [ОШИБКА] Токен бота обязателен!
    pause
    exit /b 1
)

set /p KIE_API_KEY="[ОБЯЗАТЕЛЬНО] KIE_API_KEY: "
if "!KIE_API_KEY!"=="" (
    echo [ОШИБКА] API ключ обязателен!
    pause
    exit /b 1
)

set /p KIE_API_URL="KIE_API_URL (Enter для https://api.kie.ai): "
if "!KIE_API_URL!"=="" set KIE_API_URL=https://api.kie.ai

set /p ADMIN_ID="ADMIN_ID (Enter для 6913446846): "
if "!ADMIN_ID!"=="" set ADMIN_ID=6913446846

set /p PAYMENT_PHONE="PAYMENT_PHONE (номер для СБП): "
set /p PAYMENT_BANK="PAYMENT_BANK (название банка): "
set /p PAYMENT_CARD_HOLDER="PAYMENT_CARD_HOLDER (имя получателя): "
set /p SUPPORT_TELEGRAM="SUPPORT_TELEGRAM (@username): "

:: Создание .env
(
echo # Telegram Bot Configuration
echo TELEGRAM_BOT_TOKEN=!BOT_TOKEN!
echo.
echo # KIE AI API Configuration
echo KIE_API_KEY=!KIE_API_KEY!
echo KIE_API_URL=!KIE_API_URL!
echo KIE_TIMEOUT_SECONDS=30
echo.
echo # Admin Configuration
echo ADMIN_ID=!ADMIN_ID!
) > .env

if not "!PAYMENT_PHONE!"=="" (
    echo PAYMENT_PHONE=!PAYMENT_PHONE! >> .env
)
if not "!PAYMENT_BANK!"=="" (
    echo PAYMENT_BANK=!PAYMENT_BANK! >> .env
)
if not "!PAYMENT_CARD_HOLDER!"=="" (
    echo PAYMENT_CARD_HOLDER=!PAYMENT_CARD_HOLDER! >> .env
)
if not "!SUPPORT_TELEGRAM!"=="" (
    echo SUPPORT_TELEGRAM=!SUPPORT_TELEGRAM! >> .env
)

echo.
echo [✓] Файл .env создан
echo.

:: Создание автозапуска
echo [4/4] Настройка автозапуска...
echo.

set /p AUTO_START="Добавить бота в автозагрузку Windows? (y/n): "
if /i "!AUTO_START!"=="y" (
    :: Создаем VBS скрипт для скрытого запуска
    (
        echo Set WshShell = CreateObject^("WScript.Shell"^)
        echo WshShell.Run "cmd /c cd /d ""%~dp0"" ^&^& run_bot_simple.bat", 0, False
        echo Set WshShell = Nothing
    ) > start_bot_hidden.vbs
    
    :: Добавляем в автозагрузку
    set STARTUP=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup
    copy /y "%~dp0start_bot_hidden.vbs" "%STARTUP%\kie_bot_start.vbs" >nul 2>&1
    
    if exist "%STARTUP%\kie_bot_start.vbs" (
        echo [✓] Бот добавлен в автозагрузку
    ) else (
        echo [!] Не удалось добавить в автозагрузку (можно добавить вручную)
    )
)

echo.
echo ========================================
echo   УСТАНОВКА ЗАВЕРШЕНА!
echo ========================================
echo.
echo Бот готов к запуску!
echo.
echo Запустить сейчас? (y/n)
set /p START_NOW="> "
if /i "!START_NOW!"=="y" (
    echo.
    echo Запуск бота...
    call run_bot_simple.bat
) else (
    echo.
    echo Для запуска бота используйте: run_bot_simple.bat
    echo.
    pause
)

