@echo off
REM Start VirtBot
cd /d "%~dp0"

echo ========================================
echo          VirtBot Starter
echo ========================================
echo.

REM Check if dependencies are installed by trying to import httpx
python -c "import httpx" 2>nul
if errorlevel 1 (
    echo Dependencies not installed, installing...
    pip install -r requirements.txt --user -q --disable-pip-version-check 2>nul
    echo Done!
    echo.
)

echo Starting VirtBot...
python main.py
