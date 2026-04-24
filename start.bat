@echo off
echo 🚀 Training Coach Community starten...

echo Starte OAuth Server...
start "OAuth Server" cmd /k "cd /d %~dp0 && python oauth_server.py"

echo Starte Telegram Bot...
start "Training Bot" cmd /k "cd /d %~dp0 && python bot.py"

echo ✅ Beide Server gestartet!
echo Schliesse dieses Fenster oder druecke eine Taste.
pause >nul
