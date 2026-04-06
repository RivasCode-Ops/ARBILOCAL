@echo off
chcp 65001 >nul
cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
  echo [ERRO] Python nao encontrado no PATH.
  echo Instale Python em https://www.python.org e marque "Add python.exe to PATH".
  pause
  exit /b 1
)

echo.
echo === ARBILOCAL Dashboard ===
echo.
echo Daqui a pouco o navegador deve abrir em http://127.0.0.1:8765/
echo Mantenha ESTA janela aberta. Para parar: Ctrl+C
echo.

start /b cmd /c "ping -n 4 127.0.0.1 >nul & start http://127.0.0.1:8765/"

python dashboard_server.py
if errorlevel 1 pause
