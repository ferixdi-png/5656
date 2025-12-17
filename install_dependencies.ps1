# Скрипт для автоматической установки зависимостей
Write-Host "Поиск Python..." -ForegroundColor Cyan

# Список возможных путей к Python
$pythonPaths = @(
    "python",
    "python3",
    "py",
    "$env:LOCALAPPDATA\Programs\Python\Python*\python.exe",
    "$env:LOCALAPPDATA\Microsoft\WindowsApps\python.exe",
    "$env:PROGRAMFILES\Python*\python.exe",
    "C:\Python*\python.exe",
    "C:\Program Files\Python*\python.exe",
    "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python*\python.exe"
)

$pythonExe = $null

# Попробуем найти Python
foreach ($path in $pythonPaths) {
    try {
        if ($path -match "python|python3|py") {
            # Попробуем выполнить команду напрямую
            $result = & $path --version 2>&1
            if ($LASTEXITCODE -eq 0 -or $result -match "Python") {
                $pythonExe = $path
                Write-Host "Найден Python: $path" -ForegroundColor Green
                Write-Host "Версия: $result" -ForegroundColor Green
                break
            }
        } else {
            # Проверяем файл
            $found = Get-ChildItem -Path $path -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($found) {
                $pythonExe = $found.FullName
                Write-Host "Найден Python: $pythonExe" -ForegroundColor Green
                $version = & $pythonExe --version 2>&1
                Write-Host "Версия: $version" -ForegroundColor Green
                break
            }
        }
    } catch {
        continue
    }
}

# Если не нашли через команды, попробуем через реестр
if (-not $pythonExe) {
    Write-Host "Поиск через реестр Windows..." -ForegroundColor Yellow
    $regPaths = @(
        "HKLM:\SOFTWARE\Python\PythonCore\*\InstallPath",
        "HKCU:\SOFTWARE\Python\PythonCore\*\InstallPath"
    )
    
    foreach ($regPath in $regPaths) {
        try {
            $paths = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
            if ($paths) {
                $pythonExe = Join-Path $paths.ExecutablePath "python.exe"
                if (Test-Path $pythonExe) {
                    Write-Host "Найден Python через реестр: $pythonExe" -ForegroundColor Green
                    break
                }
            }
        } catch {
            continue
        }
    }
}

if (-not $pythonExe) {
    Write-Host "`n[ОШИБКА] Python не найден!" -ForegroundColor Red
    Write-Host "Пожалуйста, установите Python 3.8 или выше:" -ForegroundColor Yellow
    Write-Host "1. Скачайте с https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "2. При установке отметьте 'Add Python to PATH'" -ForegroundColor Yellow
    Write-Host "3. Перезапустите VS Code после установки" -ForegroundColor Yellow
    exit 1
}

Write-Host "`nУстановка зависимостей..." -ForegroundColor Cyan

# Обновляем pip
Write-Host "Обновление pip..." -ForegroundColor Yellow
& $pythonExe -m pip install --upgrade pip --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ПРЕДУПРЕЖДЕНИЕ] Не удалось обновить pip, продолжаем..." -ForegroundColor Yellow
}

# Устанавливаем зависимости
Write-Host "Установка пакетов из requirements.txt..." -ForegroundColor Yellow
& $pythonExe -m pip install -r requirements.txt

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[УСПЕХ] Все зависимости установлены!" -ForegroundColor Green
    Write-Host "Перезапустите VS Code для применения изменений." -ForegroundColor Cyan
} else {
    Write-Host "`n[ОШИБКА] Не удалось установить некоторые зависимости." -ForegroundColor Red
    Write-Host "Проверьте подключение к интернету и попробуйте снова." -ForegroundColor Yellow
    exit 1
}







