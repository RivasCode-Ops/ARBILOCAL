@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo.
echo === ARBILOCAL — Painel estatico (dados fixos) ===
echo Abrindo painel_dirigido.html no navegador (sem Python, sem servidor).
echo.

start "" "%~dp0dashboard\painel_dirigido.html"
