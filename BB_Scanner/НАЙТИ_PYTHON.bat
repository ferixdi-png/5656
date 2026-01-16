@echo off
echo Searching for Python...
echo.

dir /s /b "C:\Users\%USERNAME%\AppData\Local\Programs\Python\python.exe" 2>nul
dir /s /b "C:\Python*\python.exe" 2>nul
dir /s /b "C:\Program Files\Python*\python.exe" 2>nul

echo.
echo Done. Press any key...
pause >nul






