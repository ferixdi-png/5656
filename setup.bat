@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   УСТАНОВКА KIE TELEGRAM BOT
echo ========================================
echo.

:: Проверка наличия Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    echo.
    echo Пожалуйста, установите Python 3.8 или выше:
    echo https://www.python.org/downloads/
    echo.
    echo После установки Python перезапустите этот скрипт.
    pause
    exit /b 1
)

echo [✓] Python найден
python --version

:: Проверка pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] pip не найден!
    echo Пожалуйста, переустановите Python с опцией "Add Python to PATH"
    pause
    exit /b 1
)

echo [✓] pip найден
echo.

:: Установка зависимостей
echo ========================================
echo   УСТАНОВКА ЗАВИСИМОСТЕЙ
echo ========================================
echo.

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo [ОШИБКА] Не удалось установить зависимости!
    echo Проверьте подключение к интернету и попробуйте снова.
    pause
    exit /b 1
)

echo.
echo [✓] Все зависимости установлены!
echo.

:: Создание .env файла
echo ========================================
echo   НАСТРОЙКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
echo ========================================
echo.
echo Сейчас вам нужно будет ввести необходимые данные для работы бота.
echo Если какое-то поле необязательно, просто нажмите Enter.
echo.

:: Проверка существующего .env
if exist .env (
    echo [!] Файл .env уже существует!
    set /p OVERWRITE="Перезаписать существующий .env? (y/n): "
    if /i not "!OVERWRITE!"=="y" (
        echo Установка отменена.
        pause
        exit /b 0
    )
    echo.
)

:: Обязательные параметры
echo --- ОБЯЗАТЕЛЬНЫЕ ПАРАМЕТРЫ ---
echo.

set /p BOT_TOKEN="[1/9] TELEGRAM_BOT_TOKEN (токен бота от @BotFather): "
if "!BOT_TOKEN!"=="" (
    echo [ОШИБКА] Токен бота обязателен!
    pause
    exit /b 1
)

set /p KIE_API_KEY="[2/9] KIE_API_KEY (API ключ от KIE AI): "
if "!KIE_API_KEY!"=="" (
    echo [ОШИБКА] API ключ KIE обязателен!
    pause
    exit /b 1
)

echo.
echo --- ОПЦИОНАЛЬНЫЕ ПАРАМЕТРЫ ---
echo.

set /p KIE_API_URL="[3/9] KIE_API_URL (по умолчанию: https://api.kie.ai): "
if "!KIE_API_URL!"=="" set KIE_API_URL=https://api.kie.ai

set /p KIE_TIMEOUT="[4/9] KIE_TIMEOUT_SECONDS (по умолчанию: 30): "
if "!KIE_TIMEOUT!"=="" set KIE_TIMEOUT=30

set /p ADMIN_ID="[5/9] ADMIN_ID (ваш Telegram ID, по умолчанию: 6913446846): "
if "!ADMIN_ID!"=="" set ADMIN_ID=6913446846

echo.
echo --- ПАРАМЕТРЫ ОПЛАТЫ (для проверки скриншотов) ---
echo.

set /p PAYMENT_CARD_HOLDER="[6/9] PAYMENT_CARD_HOLDER (имя получателя): "
set /p PAYMENT_PHONE="[7/9] PAYMENT_PHONE (номер телефона для СБП): "
set /p PAYMENT_BANK="[8/9] PAYMENT_BANK (название банка): "

echo.
echo --- КОНТАКТЫ ПОДДЕРЖКИ ---
echo.

set /p SUPPORT_TELEGRAM="[9/9] SUPPORT_TELEGRAM (Telegram для связи, например: @username): "
set /p SUPPORT_TEXT="[10/10] SUPPORT_TEXT (текст поддержки, можно оставить пустым): "

:: Создание .env файла
echo.
echo ========================================
echo   СОЗДАНИЕ ФАЙЛА .env
echo ========================================
echo.

(
echo # Telegram Bot Configuration
echo TELEGRAM_BOT_TOKEN=!BOT_TOKEN!
echo.
echo # KIE AI API Configuration
echo KIE_API_KEY=!KIE_API_KEY!
echo KIE_API_URL=!KIE_API_URL!
echo KIE_TIMEOUT_SECONDS=!KIE_TIMEOUT!
echo.
echo # Admin Configuration
echo ADMIN_ID=!ADMIN_ID!
echo.
echo # Payment Configuration
) > .env

if not "!PAYMENT_CARD_HOLDER!"=="" (
    echo PAYMENT_CARD_HOLDER=!PAYMENT_CARD_HOLDER! >> .env
)
if not "!PAYMENT_PHONE!"=="" (
    echo PAYMENT_PHONE=!PAYMENT_PHONE! >> .env
)
if not "!PAYMENT_BANK!"=="" (
    echo PAYMENT_BANK=!PAYMENT_BANK! >> .env
)

(
echo.
echo # Support Configuration
) >> .env

if not "!SUPPORT_TELEGRAM!"=="" (
    echo SUPPORT_TELEGRAM=!SUPPORT_TELEGRAM! >> .env
)
if not "!SUPPORT_TEXT!"=="" (
    echo SUPPORT_TEXT=!SUPPORT_TEXT! >> .env
)

echo [✓] Файл .env создан успешно!
echo.

:: Проверка Tesseract OCR
echo ========================================
echo   ПРОВЕРКА TESSERACT OCR
echo ========================================
echo.

python -c "import pytesseract; print('[✓] pytesseract установлен')" 2>nul
if errorlevel 1 (
    echo [!] pytesseract не установлен, но это не критично
    echo     OCR для проверки скриншотов будет недоступен
) else (
    :: Проверка наличия Tesseract
    where tesseract >nul 2>&1
    if errorlevel 1 (
        echo [!] Tesseract OCR не найден в PATH
        echo     Установите Tesseract для работы OCR:
        echo     https://github.com/UB-Mannheim/tesseract/wiki
        echo     Или укажите путь вручную в bot_kie.py
    ) else (
        echo [✓] Tesseract OCR найден
    )
)

echo.
echo ========================================
echo   УСТАНОВКА ЗАВЕРШЕНА!
echo ========================================
echo.
echo Все готово! Теперь вы можете запустить бота:
echo.
echo   1. Запустите: run_bot_simple.bat
echo   2. Или используйте: python run_bot.py
echo.
echo Файл .env создан с вашими настройками.
echo При необходимости вы можете отредактировать его вручную.
echo.
pause


