@echo off
REM === Change to project directory ===
cd /d C:\Users\ALFADMIN\Documents\apartmentleasefinders\alf-bot

REM === Activate Conda environment ===
call conda activate robocorp

REM === Start Python server ===
start cmd /k "python server.py"

REM === Wait a few seconds for the server to start ===
timeout /t 5 /nobreak >nul

REM === Start ngrok with custom domain ===
start cmd /k "ngrok http --url=levo-cytotropic-amal.ngrok-free.dev 5000"

REM === Keep main window open ===
echo All processes started successfully.
pause
