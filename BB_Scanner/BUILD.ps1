$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\User\Desktop\BB_Scanner"
Set-Location $ProjectRoot

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  BUILD BB_SCANNER.EXE" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Быстрый поиск Python
Write-Host "[1/4] Searching for Python..." -ForegroundColor Green

$PythonExe = $null
$username = $env:USERNAME

# Проверяем самые частые места
$quickPaths = @(
    "C:\Users\$username\AppData\Local\Programs\Python\Python314\python.exe",
    "C:\Users\$username\AppData\Local\Programs\Python\Python313\python.exe",
    "C:\Users\$username\AppData\Local\Programs\Python\Python312\python.exe",
    "C:\Users\$username\AppData\Local\Programs\Python\Python311\python.exe",
    "C:\Users\$username\AppData\Local\Programs\Python\Python310\python.exe",
    "$ProjectRoot\.venv\Scripts\python.exe"
)

foreach ($path in $quickPaths) {
    if (Test-Path $path) {
        $PythonExe = $path
        Write-Host "OK: Found Python: $path" -ForegroundColor Green
        break
    }
}

# Если не нашли - ищем в подпапках Python314
if (-not $PythonExe) {
    $pythonBase = "C:\Users\$username\AppData\Local\Programs\Python\Python314"
    if (Test-Path $pythonBase) {
        $found = Get-ChildItem -Path $pythonBase -Recurse -Filter "python.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($found) {
            $PythonExe = $found.FullName
            Write-Host "OK: Found Python: $PythonExe" -ForegroundColor Green
        }
    }
}

if (-not $PythonExe) {
    Write-Host ""
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install Python 3.10+ from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Python version:" -ForegroundColor Yellow
& $PythonExe --version
Write-Host ""

# Установка зависимостей
Write-Host "[2/4] Installing dependencies..." -ForegroundColor Green

& $PythonExe -m pip install --upgrade pip --quiet
& $PythonExe -m pip install pyinstaller playwright winotify pyperclip --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to install dependencies" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "OK: Dependencies installed" -ForegroundColor Green
Write-Host ""

# Установка Chromium
Write-Host "[3/4] Installing Chromium..." -ForegroundColor Green
& $PythonExe -m playwright install chromium --with-deps
Write-Host "OK: Chromium installed" -ForegroundColor Green
Write-Host ""

# Сборка EXE
Write-Host "[4/4] Building EXE..." -ForegroundColor Green
Write-Host "This may take 3-5 minutes..." -ForegroundColor Yellow
Write-Host ""

$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"

if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir -ErrorAction SilentlyContinue }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue }

Push-Location $ProjectRoot

$args = @(
    "--name=BB_Scanner",
    "--onefile",
    "--windowed",
    "--add-data=app;app",
    "--hidden-import=playwright",
    "--hidden-import=playwright.async_api",
    "--hidden-import=winotify",
    "--hidden-import=pyperclip",
    "--collect-all=playwright",
    "run_scanner.py"
)

& $PythonExe -m PyInstaller $args
$result = $LASTEXITCODE

Pop-Location

Write-Host ""

$ExePath = Join-Path $DistDir "BB_Scanner.exe"

if ($result -eq 0 -and (Test-Path $ExePath)) {
    Write-Host "========================================" -ForegroundColor Green
    Write-Host "  BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "EXE file: $ExePath" -ForegroundColor Cyan
    Write-Host ""
} else {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  BUILD FAILED" -ForegroundColor Red
    Write-Host "========================================" -ForegroundColor Red
}

Read-Host "Press Enter to exit"
