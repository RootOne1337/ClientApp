@echo off
REM Update and restart VirtBot
echo ========================================
echo          VirtBot Updater
echo ========================================
echo.

cd /d "%~dp0"

REM Git pull
echo [1/3] Pulling latest code...
git pull
if errorlevel 1 (
    echo WARNING: Git pull failed, continuing anyway...
)

REM Upgrade pip first (silently)
echo [2/3] Updating pip...
python -m pip install --upgrade pip --user -q 2>nul

REM Install dependencies with --user flag to avoid permission issues
echo [3/3] Installing dependencies...
pip install -r requirements.txt --user -q --disable-pip-version-check 2>nul
if errorlevel 1 (
    echo WARNING: Some packages failed to install, trying alternative method...
    pip install -r requirements.txt --user --ignore-installed -q --disable-pip-version-check 2>nul
)

echo.
echo ========================================
echo          Update complete!
echo ========================================
echo.
echo Restarting in 2 seconds...
timeout /t 2 /nobreak > nul

REM Start the bot
python main.py
