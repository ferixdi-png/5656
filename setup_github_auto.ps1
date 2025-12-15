# PowerShell скрипт для настройки автоматического обновления GitHub
# Запуск: powershell -ExecutionPolicy Bypass -File setup_github_auto.ps1

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  НАСТРОЙКА АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ GITHUB" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Проверка Git
try {
    $gitVersion = git --version
    Write-Host "✅ Git найден: $gitVersion" -ForegroundColor Green
} catch {
    Write-Host "❌ Git не найден!" -ForegroundColor Red
    Write-Host "Установите Git: https://git-scm.com/download/win" -ForegroundColor Yellow
    exit 1
}

# Переход в папку скрипта
$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptPath
Write-Host "📁 Рабочая папка: $scriptPath" -ForegroundColor Cyan
Write-Host ""

# Инициализация Git репозитория
if (-not (Test-Path ".git")) {
    Write-Host "📦 Инициализация Git репозитория..." -ForegroundColor Yellow
    git init
    git remote add origin https://github.com/ferixdi-png/5555555555.git
    git branch -M main
    Write-Host "✅ Репозиторий инициализирован" -ForegroundColor Green
} else {
    Write-Host "✅ Git репозиторий найден" -ForegroundColor Green
    
    # Проверка remote
    $remoteUrl = git remote get-url origin 2>$null
    if (-not $remoteUrl) {
        git remote add origin https://github.com/ferixdi-png/5555555555.git
        Write-Host "✅ Remote репозиторий добавлен" -ForegroundColor Green
    } else {
        Write-Host "✅ Remote репозиторий: $remoteUrl" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  НАСТРОЙКА ЗАВЕРШЕНА" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Доступные скрипты:" -ForegroundColor Cyan
Write-Host "  1. update_github.bat - Интерактивное обновление" -ForegroundColor White
Write-Host "  2. update_github_auto.bat - Автоматическое обновление с выводом" -ForegroundColor White
Write-Host "  3. update_github_silent.bat - Тихий режим (для планировщика)" -ForegroundColor White
Write-Host ""
Write-Host "💡 Для автоматического запуска по расписанию:" -ForegroundColor Yellow
Write-Host "  1. Откройте Планировщик заданий Windows" -ForegroundColor White
Write-Host "  2. Создайте новое задание" -ForegroundColor White
Write-Host "  3. Укажите действие: $scriptPath\update_github_silent.bat" -ForegroundColor White
Write-Host "  4. Установите расписание (например, каждый час)" -ForegroundColor White
Write-Host ""

# Проверка статуса
Write-Host "📊 Текущий статус репозитория:" -ForegroundColor Cyan
git status --short
Write-Host ""

Read-Host "Нажмите Enter для выхода"

