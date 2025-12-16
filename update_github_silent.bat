@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

REM Полностью автоматический режим без пауз и подтверждений
REM Используйте этот скрипт для автоматического запуска по расписанию

REM Проверка наличия Git
where git >nul 2>&1
if %errorlevel% neq 0 (
    exit /b 1
)

REM Переход в папку скрипта
cd /d "%~dp0"

REM Инициализация репозитория, если нужно
if not exist ".git" (
    git init >nul 2>&1
    git remote add origin https://github.com/ferixdi-png/5555555555.git >nul 2>&1
    git branch -M main >nul 2>&1
    set BRANCH=main
) else (
    git remote get-url origin >nul 2>&1
    if %errorlevel% neq 0 (
        git remote add origin https://github.com/ferixdi-png/5555555555.git >nul 2>&1
    )
    
    for /f "tokens=2" %%i in ('git branch --show-current 2^>nul') do set BRANCH=%%i
    if not defined BRANCH set BRANCH=main
)

REM Проверка изменений
git diff --quiet --exit-code
if %errorlevel% equ 0 (
    git diff --cached --quiet --exit-code
    if %errorlevel% equ 0 (
        REM Нет изменений, проверяем есть ли что отправить
        git log origin/%BRANCH%..HEAD --oneline >nul 2>&1
        if %errorlevel% neq 0 exit /b 0
    )
)

REM Добавление и коммит
git add . >nul 2>&1
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set DATE_STR=%%c-%%a-%%b
for /f "tokens=1-2 delims=: " %%a in ('time /t') do set TIME_STR=%%a:%%b
set COMMIT_MSG=Автообновление: %DATE_STR% %TIME_STR%

git commit -m "%COMMIT_MSG%" >nul 2>&1

REM Push
git push -u origin %BRANCH% >nul 2>&1
exit /b %errorlevel%


