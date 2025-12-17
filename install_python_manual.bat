@echo off
chcp 65001 >nul
echo.
echo ========================================
echo   УСТАНОВКА PYTHON (РУЧНАЯ)
echo ========================================
echo.
echo Этот скрипт поможет вам установить Python вручную.
echo.
echo ШАГ 1: Скачайте Python
echo.
echo Откройте в браузере:
echo https://www.python.org/downloads/
echo.
echo Нажмите большую желтую кнопку "Download Python 3.x.x"
echo Это скачает файл .exe (НЕ MSIX!)
echo.
echo ШАГ 2: Установите Python
echo.
echo 1. Запустите скачанный .exe файл
echo 2. ВАЖНО: В самом начале установки отметьте галочку
echo    "Add Python to PATH" (внизу окна установки)
echo 3. Нажмите "Install Now"
echo 4. Дождитесь завершения установки
echo.
echo ШАГ 3: После установки
echo.
echo 1. ЗАКРОЙТЕ этот терминал
echo 2. Откройте НОВЫЙ терминал в VS Code
echo 3. Выполните: python --version
echo    (должна показаться версия Python)
echo 4. Если версия показалась - выполните:
echo    python -m pip install -r requirements.txt
echo.
echo ========================================
echo.
pause







