@echo off
cd /d C:\Users\ALFADMIN\Documents\apartmentleasefinders\alf-bot
call conda activate robocorp

REM === Start ngrok in separate window ===
start cmd /k "ngrok http --url=levo-cytotropic-amal.ngrok-free.dev 5000"

:restart_server
echo Starting server.py...
python server.py
echo server.py stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto restart_server