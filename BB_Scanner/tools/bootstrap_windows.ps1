# BetBoom Live Scanner - Bootstrap Script
# Автоматически устанавливает uv, Python и зависимости

param(
    [switch]$Force = $false
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$RuntimeDir = Join-Path $ProjectRoot ".runtime"
$UvDir = Join-Path $RuntimeDir "uv"
$UvExe = Join-Path $UvDir "uv.exe"
$PythonDir = Join-Path $RuntimeDir "python"
$VenvDir = Join-Path $ProjectRoot ".venv"

Write-Host "=== BetBoom Live Scanner Bootstrap ===" -ForegroundColor Cyan
Write-Host ""

# Функция для скачивания файла
function Download-File {
    param([string]$Url, [string]$Path)
    
    try {
        Write-Host "Скачивание: $Url" -ForegroundColor Yellow
        $ProgressPreference = "Continue"
        Invoke-WebRequest -Uri $Url -OutFile $Path -UseBasicParsing -ErrorAction Stop
        $ProgressPreference = "SilentlyContinue"
        return $true
    } catch {
        Write-Host "Ошибка скачивания: $_" -ForegroundColor Red
        return $false
    }
}

# 1. Проверка/установка uv
if (-not (Test-Path $UvExe) -or $Force) {
    Write-Host "[1/5] Установка uv..." -ForegroundColor Green
    
    New-Item -ItemType Directory -Force -Path $UvDir | Out-Null
    
    # Определяем архитектуру
    $arch = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "x86" }
    $uvUrl = "https://github.com/astral-sh/uv/releases/latest/download/uv-${arch}-pc-windows-msvc.zip"
    
    $uvZip = Join-Path $env:TEMP "uv.zip"
    
    if (-not (Download-File -Url $uvUrl -Path $uvZip)) {
        Write-Host "ОШИБКА: Не удалось скачать uv" -ForegroundColor Red
        exit 1
    }
    
    # Распаковка
    Write-Host "Распаковка uv..." -ForegroundColor Yellow
    Expand-Archive -Path $uvZip -DestinationPath $UvDir -Force
    Remove-Item $uvZip -Force
    
    Write-Host "✓ uv установлен" -ForegroundColor Green
} else {
    Write-Host "[1/5] uv уже установлен" -ForegroundColor Gray
}

# 2. Установка Python через uv
$PythonExe = $null
$PythonFound = Get-ChildItem -Path $PythonDir -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1

if (-not $PythonFound -or $Force) {
    Write-Host "[2/5] Установка Python 3.12..." -ForegroundColor Green
    
    New-Item -ItemType Directory -Force -Path $PythonDir | Out-Null
    
    & $UvExe python install --output-dir $PythonDir "3.12"
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ОШИБКА: Не удалось установить Python" -ForegroundColor Red
        exit 1
    }
    
    # Находим установленный Python
    $PythonFound = Get-ChildItem -Path $PythonDir -Recurse -Filter "python.exe" | Select-Object -First 1
    if ($PythonFound) {
        $PythonExe = $PythonFound.FullName
        Write-Host "✓ Python установлен: $PythonExe" -ForegroundColor Green
    } else {
        Write-Host "ОШИБКА: Python.exe не найден после установки" -ForegroundColor Red
        exit 1
    }
} else {
    $PythonExe = $PythonFound.FullName
    Write-Host "[2/5] Python уже установлен: $PythonExe" -ForegroundColor Gray
}

if (-not $PythonExe) {
    Write-Host "ОШИБКА: Python.exe не найден" -ForegroundColor Red
    exit 1
}

# 3. Создание venv
if (-not (Test-Path (Join-Path $VenvDir "Scripts\python.exe")) -or $Force) {
    Write-Host "[3/5] Создание виртуального окружения..." -ForegroundColor Green
    
    & $PythonExe -m venv $VenvDir
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ОШИБКА: Не удалось создать venv" -ForegroundColor Red
        exit 1
    }
    
    Write-Host "✓ venv создано" -ForegroundColor Green
} else {
    Write-Host "[3/5] venv уже существует" -ForegroundColor Gray
}

$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$VenvPip = Join-Path $VenvDir "Scripts\pip.exe"

# 4. Установка зависимостей
Write-Host "[4/5] Установка зависимостей..." -ForegroundColor Green

Push-Location $ProjectRoot

# Обновляем pip
& $VenvPip install --upgrade pip setuptools wheel

# Устанавливаем зависимости через pip
& $VenvPip install playwright winotify

if ($LASTEXITCODE -ne 0) {
    Write-Host "ОШИБКА: Не удалось установить зависимости" -ForegroundColor Red
    Pop-Location
    exit 1
}

Pop-Location

Write-Host "✓ Зависимости установлены" -ForegroundColor Green

# 5. Установка Playwright браузеров
Write-Host "[5/5] Установка Playwright браузеров..." -ForegroundColor Green

$PlaywrightExe = Join-Path $VenvDir "Scripts\playwright.exe"
if (Test-Path $PlaywrightExe) {
    & $PlaywrightExe install chromium
    & $PlaywrightExe install-deps chromium
} else {
    & $VenvPython -m playwright install chromium
    & $VenvPython -m playwright install-deps chromium
}

Write-Host "✓ Playwright готов" -ForegroundColor Green

Write-Host ""
Write-Host "=== Bootstrap завершён! ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Запустите сканер:" -ForegroundColor Yellow
Write-Host "  .\start_scanner.bat" -ForegroundColor White
Write-Host ""

