@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════
echo   ПРОВЕРКА УСТАНОВКИ PYTHON
echo ═══════════════════════════════════════════════════════════
echo.

echo Проверка Python в PATH...
python --version >nul 2>&1
if errorlevel 1 (
    echo [ОШИБКА] Python не найден в PATH!
    echo.
    echo Поиск Python в стандартных местах...
    echo.
    
    if exist "%LOCALAPPDATA%\Programs\Python\Python*\python.exe" (
        echo [НАЙДЕН] Python найден в: %LOCALAPPDATA%\Programs\Python\
        for /d %%i in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
            echo   Версия: %%i
            "%%i\python.exe" --version
        )
        echo.
        echo РЕШЕНИЕ:
        echo 1. Перезагрузите компьютер
        echo 2. Или добавьте Python в PATH вручную
        echo 3. Или используйте полный путь к python.exe
    ) else (
        echo [НЕ НАЙДЕН] Python не установлен или не в стандартном месте
        echo.
        echo Установите Python с https://www.python.org/downloads/
        echo При установке отметьте "Add Python to PATH"
    )
) else (
    echo [OK] Python найден!
    python --version
    echo.
    echo Проверка зависимостей...
    python -m pip list | findstr /i "telegram dotenv aiohttp"
    echo.
    echo Если пакеты не показаны - установите их:
    echo   python -m pip install -r requirements.txt
)

echo.
pause


