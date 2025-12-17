@echo off
chcp 65001 >nul
cls
echo.
echo ═══════════════════════════════════════════════════════════
echo   ПОЛНАЯ ПРОВЕРКА УСТАНОВКИ
echo ═══════════════════════════════════════════════════════════
echo.

echo [1/4] Проверка Python...
python --version
if errorlevel 1 (
    echo [ОШИБКА] Python не найден!
    pause
    exit /b 1
)
echo [OK] Python работает
echo.

echo [2/4] Проверка основных модулей...
python -c "import telegram; print('  ✓ telegram')" 2>nul || echo "  ✗ telegram - НЕ УСТАНОВЛЕН"
python -c "import dotenv; print('  ✓ dotenv')" 2>nul || echo "  ✗ dotenv - НЕ УСТАНОВЛЕН"
python -c "import aiohttp; print('  ✓ aiohttp')" 2>nul || echo "  ✗ aiohttp - НЕ УСТАНОВЛЕН"
python -c "import aiofiles; print('  ✓ aiofiles')" 2>nul || echo "  ✗ aiofiles - НЕ УСТАНОВЛЕН"
python -c "from PIL import Image; print('  ✓ Pillow (PIL)')" 2>nul || echo "  ✗ Pillow - НЕ УСТАНОВЛЕН"
python -c "import pytesseract; print('  ✓ pytesseract')" 2>nul || echo "  ✗ pytesseract - НЕ УСТАНОВЛЕН (опционально)"
echo.

echo [3/4] Проверка локальных модулей...
python -c "import kie_client; print('  ✓ kie_client')" 2>nul || echo "  ✗ kie_client - файл не найден"
python -c "import kie_models; print('  ✓ kie_models')" 2>nul || echo "  ✗ kie_models - файл не найден"
python -c "import translations; print('  ✓ translations')" 2>nul || echo "  ✗ translations - файл не найден"
python -c "import knowledge_storage; print('  ✓ knowledge_storage')" 2>nul || echo "  ✗ knowledge_storage - файл не найден"
echo.

echo [4/4] Проверка импортов bot_kie.py...
python -c "import sys; sys.path.insert(0, '.'); from bot_kie import *; print('  ✓ bot_kie.py импортируется успешно!')" 2>nul
if errorlevel 1 (
    echo "  ⚠ bot_kie.py имеет ошибки импорта (проверьте выше)"
) else (
    echo "  ✓ Все импорты работают!"
)
echo.

echo ═══════════════════════════════════════════════════════════
echo   РЕЗУЛЬТАТ ПРОВЕРКИ
echo ═══════════════════════════════════════════════════════════
echo.
echo Если все модули отмечены как ✓ - всё готово!
echo.
echo Если есть ✗ - установите недостающие:
echo   python -m pip install -r requirements.txt
echo.
echo Если bot_kie.py импортируется - бот готов к запуску!
echo.
pause







