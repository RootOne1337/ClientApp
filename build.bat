@echo off
REM VirtBot Nuitka Build Script for Windows
REM Создаёт standalone exe с помощью Nuitka

echo ============================================
echo   VirtBot Build Script
echo ============================================

REM Проверяем что nuitka установлена
python -m nuitka --version >nul 2>&1
if errorlevel 1 (
    echo Installing Nuitka...
    pip install nuitka ordered-set zstandard
)

echo.
echo Building VirtBot.exe...
echo.

python -m nuitka ^
    --standalone ^
    --onefile ^
    --windows-console-mode=disable ^
    --windows-icon-from-ico=icon.ico ^
    --output-dir=dist ^
    --output-filename=VirtBot.exe ^
    --include-data-files=.env.example=.env.example ^
    --enable-plugin=anti-bloat ^
    --nofollow-import-to=pytest ^
    --nofollow-import-to=unittest ^
    --nofollow-import-to=test ^
    main.py

if exist dist\VirtBot.exe (
    echo.
    echo ============================================
    echo   SUCCESS! VirtBot.exe created in dist/
    echo ============================================
    echo.
    echo File size:
    for %%A in (dist\VirtBot.exe) do echo   %%~zA bytes
) else (
    echo.
    echo BUILD FAILED!
    exit /b 1
)
