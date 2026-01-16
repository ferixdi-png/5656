$ErrorActionPreference = "Continue"
$ProjectRoot = "C:\Users\User\Desktop\BB_Scanner"
Set-Location $ProjectRoot

Write-Host "РђР’РўРћРњРђРўРР§Р•РЎРљРђРЇ РЎР‘РћР РљРђ BB_SCANNER.EXE" -ForegroundColor Cyan
Write-Host ""

$PythonExe = $null
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
    Write-Host "OK: РќР°Р№РґРµРЅ Python РІ .venv" -ForegroundColor Green
}

if (-not $PythonExe) {
    $username = $env:USERNAME
    $paths = @(
        "C:\Users\$username\AppData\Local\Programs\Python\Python314\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python313\python.exe",
        "C:\Users\$username\AppData\Local\Programs\Python\Python312\python.exe"
    )
    foreach ($path in $paths) {
        if (Test-Path $path) {
            $PythonExe = $path
            Write-Host "OK: РќР°Р№РґРµРЅ СЃРёСЃС‚РµРјРЅС‹Р№ Python" -ForegroundColor Green
            break
        }
    }
}

if (-not $PythonExe) {
    Write-Host "РћРЁРР‘РљРђ: Python РЅРµ РЅР°Р№РґРµРЅ!" -ForegroundColor Red
    Read-Host "РќР°Р¶РјРёС‚Рµ Enter РґР»СЏ РІС‹С…РѕРґР°"
    exit 1
}

& $PythonExe --version
Write-Host "[1/3] РЈСЃС‚Р°РЅРѕРІРєР° Р·Р°РІРёСЃРёРјРѕСЃС‚РµР№..." -ForegroundColor Green
& $PythonExe -m pip install --upgrade pip --quiet
& $PythonExe -m pip install pyinstaller playwright winotify pyperclip --quiet
& $PythonExe -m playwright install chromium
Write-Host "OK: Р—Р°РІРёСЃРёРјРѕСЃС‚Рё СѓСЃС‚Р°РЅРѕРІР»РµРЅС‹" -ForegroundColor Green

Write-Host "[2/3] РћС‡РёСЃС‚РєР°..." -ForegroundColor Green
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"
if (Test-Path $DistDir) { Remove-Item -Recurse -Force $DistDir -ErrorAction SilentlyContinue }
if (Test-Path $BuildDir) { Remove-Item -Recurse -Force $BuildDir -ErrorAction SilentlyContinue }

Write-Host "[3/3] РЎР±РѕСЂРєР° EXE..." -ForegroundColor Green
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
    Write-Host "РЎР‘РћР РљРђ Р—РђР’Р•Р РЁР•РќРђ РЈРЎРџР•РЁРќРћ!" -ForegroundColor Green
    Write-Host "EXE: $ExePath" -ForegroundColor Cyan
} else {
    Write-Host "РћРЁРР‘РљРђ РџР Р РЎР‘РћР РљР•" -ForegroundColor Red
}
Read-Host "РќР°Р¶РјРёС‚Рµ Enter РґР»СЏ РІС‹С…РѕРґР°"
