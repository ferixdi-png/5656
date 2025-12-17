# Автоматический поиск и установка Python через winget
Write-Host "=== Поиск и установка Python ===" -ForegroundColor Cyan
Write-Host ""

# Проверяем, установлен ли уже Python
$pythonFound = $false
$pythonExe = $null

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
                Write-Host "[OK] Python уже установлен: $version" -ForegroundColor Green
                Write-Host "Используется: $cmd" -ForegroundColor Green
                break
            }
        }
    } catch {
        continue
    }
}

if ($pythonFound) {
    Write-Host ""
    Write-Host "=== Установка зависимостей ===" -ForegroundColor Cyan
    & $pythonExe -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    & $pythonExe -m pip install -r requirements.txt
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[УСПЕХ] Все зависимости установлены!" -ForegroundColor Green
        Write-Host "Перезапустите VS Code для применения изменений." -ForegroundColor Cyan
        exit 0
    } else {
        Write-Host ""
        Write-Host "[ОШИБКА] Не удалось установить зависимости." -ForegroundColor Red
        exit 1
    }
}

# Python не найден - пробуем установить через winget
Write-Host "[ИНФО] Python не найден. Пробуем установить через winget..." -ForegroundColor Yellow
Write-Host ""

# Проверяем наличие winget
try {
    $wingetVersion = winget --version 2>&1
    Write-Host "[OK] winget найден: $wingetVersion" -ForegroundColor Green
} catch {
    Write-Host "[ОШИБКА] winget не найден!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Альтернативные способы установки Python:" -ForegroundColor Yellow
    Write-Host "1. Скачайте с https://www.python.org/downloads/ (файл .exe, НЕ MSIX!)" -ForegroundColor White
    Write-Host "2. При установке отметьте 'Add Python to PATH'" -ForegroundColor White
    Write-Host "3. Перезапустите VS Code и запустите этот скрипт снова" -ForegroundColor White
    exit 1
}

# Устанавливаем Python через winget
Write-Host "Установка Python 3.12 через winget..." -ForegroundColor Yellow
Write-Host "Это может занять несколько минут..." -ForegroundColor Yellow
Write-Host ""

try {
    winget install Python.Python.3.12 --silent --accept-package-agreements --accept-source-agreements
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host ""
        Write-Host "[УСПЕХ] Python установлен!" -ForegroundColor Green
        Write-Host ""
        Write-Host "ВАЖНО: Перезапустите VS Code и терминал!" -ForegroundColor Yellow
        Write-Host "После перезапуска запустите этот скрипт снова для установки зависимостей." -ForegroundColor Yellow
    } else {
        Write-Host ""
        Write-Host "[ОШИБКА] Не удалось установить Python через winget." -ForegroundColor Red
        Write-Host ""
        Write-Host "Установите Python вручную:" -ForegroundColor Yellow
        Write-Host "1. Скачайте с https://www.python.org/downloads/" -ForegroundColor White
        Write-Host "2. При установке отметьте 'Add Python to PATH'" -ForegroundColor White
        exit 1
    }
} catch {
    Write-Host ""
    Write-Host "[ОШИБКА] Ошибка при установке Python: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Установите Python вручную с https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}




