# Автоматическая установка Python и зависимостей
Write-Host "=== Установка Python и зависимостей для KIE Bot ===" -ForegroundColor Cyan
Write-Host ""

# Проверяем, установлен ли Python
$pythonFound = $false
$pythonExe = $null

# Список команд для проверки
$pythonCommands = @("python", "python3", "py")

foreach ($cmd in $pythonCommands) {
    try {
        $version = & $cmd --version 2>&1
        if ($version -match "Python (\d+)\.(\d+)") {
            $major = [int]$matches[1]
            $minor = [int]$matches[2]
            if ($major -ge 3 -and $minor -ge 8) {
                $pythonExe = $cmd
                $pythonFound = $true
                Write-Host "[OK] Найден Python $version" -ForegroundColor Green
                break
            }
        }
    } catch {
        continue
    }
}

if (-not $pythonFound) {
    Write-Host "[ОШИБКА] Python 3.8+ не найден в системе!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Варианты решения:" -ForegroundColor Yellow
    Write-Host "1. Установите Python с https://www.python.org/downloads/" -ForegroundColor White
    Write-Host "   При установке обязательно отметьте 'Add Python to PATH'" -ForegroundColor White
    Write-Host ""
    Write-Host "2. Или установите через Microsoft Store:" -ForegroundColor White
    Write-Host "   - Откройте Microsoft Store" -ForegroundColor White
    Write-Host "   - Найдите 'Python 3.11' или 'Python 3.12'" -ForegroundColor White
    Write-Host "   - Установите" -ForegroundColor White
    Write-Host ""
    Write-Host "После установки Python:" -ForegroundColor Cyan
    Write-Host "1. Перезапустите VS Code" -ForegroundColor White
    Write-Host "2. Запустите этот скрипт снова" -ForegroundColor White
    Write-Host "   Или выполните: python -m pip install -r requirements.txt" -ForegroundColor White
    exit 1
}

Write-Host ""
Write-Host "=== Установка зависимостей ===" -ForegroundColor Cyan

# Обновляем pip
Write-Host "Обновление pip..." -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip --quiet 2>&1 | Out-Null

# Устанавливаем зависимости
Write-Host "Установка пакетов из requirements.txt..." -ForegroundColor Yellow
& $pythonExe -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "[УСПЕХ] Все зависимости установлены!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Следующие шаги:" -ForegroundColor Cyan
    Write-Host "1. Перезапустите VS Code (Ctrl+Shift+P -> 'Reload Window')" -ForegroundColor White
    Write-Host "2. Выберите интерпретатор Python:" -ForegroundColor White
    Write-Host "   Ctrl+Shift+P -> 'Python: Select Interpreter'" -ForegroundColor White
    Write-Host "   Выберите: $pythonExe" -ForegroundColor White
    Write-Host ""
    Write-Host "Ошибки импорта должны исчезнуть после перезапуска VS Code." -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "[ОШИБКА] Не удалось установить зависимости." -ForegroundColor Red
    Write-Host "Проверьте подключение к интернету и попробуйте снова." -ForegroundColor Yellow
    exit 1
}







