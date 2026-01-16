# Build executable with PyInstaller

param(
    [switch]$Clean = $false
)

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

Write-Host "=== Building BetBoom Scanner EXE ===" -ForegroundColor Cyan
Write-Host ""

# Check if venv exists
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "ОШИБКА: Виртуальное окружение не найдено. Запустите bootstrap сначала." -ForegroundColor Red
    exit 1
}

# Install PyInstaller if needed
Write-Host "[1/3] Проверка PyInstaller..." -ForegroundColor Green
& $VenvPython -m pip install pyinstaller | Out-Null

# Clean previous build
if ($Clean -and (Test-Path (Join-Path $ProjectRoot "dist"))) {
    Write-Host "Очистка предыдущей сборки..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot "dist")
    Remove-Item -Recurse -Force (Join-Path $ProjectRoot "build")
}

# Build
Write-Host "[2/3] Сборка EXE..." -ForegroundColor Green

Push-Location $ProjectRoot

$PyInstallerArgs = @(
    "--name=BetBoomScanner",
    "--onefile",
    "--windowed",
    "--icon=NONE",
    "--add-data=app;app",
    "--hidden-import=asyncio",
    "--hidden-import=playwright",
    "--hidden-import=winotify",
    "--clean",
    "app/main.py"
)

& $VenvPython -m PyInstaller @PyInstallerArgs

Pop-Location

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "=== Сборка завершена! ===" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "EXE файл находится в: $ProjectRoot\dist\BetBoomScanner.exe" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "ОШИБКА: Сборка не удалась" -ForegroundColor Red
    exit 1
}

