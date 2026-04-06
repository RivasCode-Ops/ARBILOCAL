@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === ARBILOCAL — Configurar pesquisa web ===
echo.

if not exist ".env" (
  if exist ".env.example" (
    copy /Y ".env.example" ".env" >nul
    echo Criado .env a partir de .env.example
    echo Edite o arquivo .env e coloque BRAVE_API_KEY ou GOOGLE_API_KEY + GOOGLE_CSE_ID
  ) else (
    echo ERRO: Falta .env.example
    pause
    exit /b 1
  )
) else (
  echo Ja existe .env — abra e edite com o Bloco de Notas se precisar.
)

echo.
echo Instalando dependencias (python-dotenv)...
python -m pip install -q -r requirements.txt
echo.

python scripts\verificar_pesquisa.py
echo.
echo Depois: python dashboard_server.py  e abra http://127.0.0.1:8765/
echo Para editar .env agora:
start notepad .env
pause
