@echo off
REM Update and restart VirtBot
echo Updating VirtBot...

REM Git pull
git pull

REM Install dependencies
pip install -r requirements.txt -q

echo Restarting...
timeout /t 2 /nobreak > nul
python main.py
