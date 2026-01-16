$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\User\Desktop\BB_Scanner"
Set-Location $ProjectRoot

Write-Host "AUTOMATIC BUILD BB_SCANNER.EXE" -ForegroundColor Cyan
Write-Host ""

$PythonExe = $null
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Host "OK: Found Python in .venv" -ForegroundColor Green
}

if (-not $PythonExe) {
    $username = $env:USERNAME
    $paths = @(
        "C:\Users\$username\AppData\Local\Programs\Python\Python314\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python313\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python312\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python311\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python310\python.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            $PythonExe = $path
            Write-Host "OK: Found system Python" -ForegroundColor Green
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "ERROR: Python not found!" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

& $PythonExe --version
Write-Host "[1/3] Installing dependencies..." -ForegroundColor Green
& $PythonExe -m pip install --upgrade pip --quiet 2>&1 | Out-Null
& $PythonExe -m pip install pyinstaller playwright winotify pyperclip --quiet 2>&1 | Out-Null
Write-Host "OK: Dependencies installed" -ForegroundColor Green

Write-Host "Installing Chromium..." -ForegroundColor Yellow
& $PythonExe -m playwright install chromium 2>&1 | Out-Null
Write-Host "OK: Chromium installed" -ForegroundColor Green

Write-Host "[2/3] Cleaning..." -ForegroundColor Green
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir -ErrorAction SilentlyContinue }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue }

Write-Host "[3/3] Building EXE..." -ForegroundColor Green
Write-Host "This may take 3-5 minutes..." -ForegroundColor Yellow
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

$ExePath = Join-Path $DistDir "BB_Scanner.exe"
if ($result -eq 0 -and (Test-Path $ExePath)) {
    Write-Host ""
    Write-Host "BUILD SUCCESSFUL!" -ForegroundColor Green
    Write-Host "EXE file: $ExePath" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "You can now run BB_Scanner.exe without Python!" -ForegroundColor Yellow
} else {
    Write-Host ""
    Write-Host "BUILD ERROR" -ForegroundColor Red
}
Read-Host "Press Enter to exit"






