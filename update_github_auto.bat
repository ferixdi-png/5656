@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================================
echo  АВТОМАТИЧЕСКОЕ ОБНОВЛЕНИЕ GITHUB РЕПОЗИТОРИЯ
echo ============================================================
echo.

REM Проверка наличия Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Git не найден!
    echo.
    echo Установите Git: https://git-scm.com/download/win
    echo Или используйте GitHub Desktop: https://desktop.github.com/
    pause
    exit /b 1
)

echo ✅ Git найден
echo.

REM Переход в папку скрипта
cd /d "%~dp0"

REM Проверка, является ли папка Git репозиторием
if not exist ".git" (
    echo 📦 Инициализация Git репозитория...
    git init
    echo.
    
    echo 🔗 Добавление remote репозитория...
    git remote add origin https://github.com/ferixdi-png/5555555555.git
    echo ✅ Remote добавлен
    echo.
    
    REM Установка ветки по умолчанию
    git branch -M main 2>nul
    if %errorlevel% neq 0 (
        git branch -M master 2>nul
        set BRANCH=master
    ) else (
        set BRANCH=main
    )
    echo.
) else (
    echo ✅ Git репозиторий найден
    echo.
    
    REM Проверка remote
    git remote get-url origin >nul 2>&1
    if %errorlevel% neq 0 (
        echo 🔗 Добавление remote репозитория...
        git remote add origin https://github.com/ferixdi-png/5555555555.git
        echo ✅ Remote добавлен
        echo.
    ) else (
        echo ✅ Remote репозиторий настроен
        echo.
    )
    
    REM Определение текущей ветки
    for /f "tokens=2" %%i in ('git branch --show-current 2^>nul') do set BRANCH=%%i
    if not defined BRANCH (
        REM Попытка определить ветку из git status
        for /f "tokens=3" %%i in ('git status -b --porcelain 2^>nul ^| findstr /C:"##"') do set BRANCH=%%i
        if not defined BRANCH set BRANCH=main
    )
)

REM Получение изменений с удаленного репозитория (если есть)
echo 🔄 Проверка удаленного репозитория...
git fetch origin %BRANCH% 2>nul
if %errorlevel% equ 0 (
    echo ✅ Удаленный репозиторий доступен
    echo.
) else (
    echo ⚠️  Удаленный репозиторий недоступен или ветка не существует
    echo    Будет создана новая ветка
    echo.
)

REM Показать статус
echo 📊 Текущий статус:
git status --short
echo.

REM Проверка наличия изменений
git diff --quiet --exit-code
set HAS_CHANGES=%errorlevel%

git diff --cached --quiet --exit-code
set HAS_STAGED=%errorlevel%

if %HAS_CHANGES% equ 0 if %HAS_STAGED% equ 0 (
    echo ℹ️  Нет изменений для коммита
    echo    Все файлы уже закоммичены
    echo.
    
    REM Попытка push, если есть коммиты, которые не отправлены
    git log origin/%BRANCH%..HEAD --oneline >nul 2>&1
    if %errorlevel% equ 0 (
        echo 🔄 Найдены локальные коммиты, отправка на GitHub...
        goto :push
    ) else (
        echo ✅ Все синхронизировано с GitHub
        pause
        exit /b 0
    )
)

echo 📦 Добавление всех изменений...
git add .
echo ✅ Файлы добавлены
echo.

REM Создание сообщения коммита с датой и временем
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE_STR=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME_STR=%%a:%%b
set COMMIT_MSG=Автоматическое обновление: %DATE_STR% %TIME_STR%

echo 📝 Создание коммита...
git commit -m "%COMMIT_MSG%"
if %errorlevel% neq 0 (
    echo ⚠️  Ошибка при создании коммита
    echo    Возможно, нет изменений для коммита
    echo.
) else (
    echo ✅ Коммит создан: %COMMIT_MSG%
    echo.
)

:push
echo 🔄 Отправка на GitHub...
echo.

REM Попытка push
git push -u origin %BRANCH% 2>&1
set PUSH_ERROR=%errorlevel%

if %PUSH_ERROR% neq 0 (
    REM Попытка определить причину ошибки
    git push -u origin %BRANCH% 2>&1 | findstr /C:"Authentication" >nul
    if %errorlevel% equ 0 (
        echo.
        echo ⚠️  ОШИБКА АУТЕНТИФИКАЦИИ
        echo.
        echo 💡 РЕШЕНИЕ:
        echo    1. Создайте Personal Access Token:
        echo       https://github.com/settings/tokens
        echo    2. При запросе пароля введите токен
        echo    3. Или используйте GitHub Desktop
        echo.
    ) else (
        git push -u origin %BRANCH% 2>&1 | findstr /C:"rejected" >nul
        if %errorlevel% equ 0 (
            echo.
            echo ⚠️  ОТКЛОНЕНО: Удаленный репозиторий имеет изменения
            echo.
            echo 💡 РЕШЕНИЕ:
            echo    git pull origin %BRANCH% --rebase
            echo    git push -u origin %BRANCH%
            echo.
        ) else (
            echo.
            echo ⚠️  Ошибка при отправке
            echo    Проверьте настройки аутентификации
            echo.
        )
    )
) else (
    echo.
    echo ✅ УСПЕШНО! Файлы отправлены на GitHub!
    echo.
    echo 🔗 Ваш репозиторий:
    echo    https://github.com/ferixdi-png/5555555555
    echo.
    echo 📊 Ветка: %BRANCH%
    echo.
)

echo ============================================================
pause

