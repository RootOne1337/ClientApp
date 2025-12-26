@echo off
REM Restart VirtBot
echo Restarting VirtBot...
timeout /t 2 /nobreak > nul
python main.py
