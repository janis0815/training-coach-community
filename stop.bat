@echo off
echo Stoppe Training Coach Prozesse...

:: Nur die Fenster mit unseren Titeln schliessen
taskkill /FI "WINDOWTITLE eq OAuth Server*" /F 2>nul
taskkill /FI "WINDOWTITLE eq Training Bot*" /F 2>nul

echo ✅ Training Coach gestoppt!
pause >nul
