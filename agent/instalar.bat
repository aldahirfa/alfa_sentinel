@echo off
:: Instalador del agente ALFA-Sentinel para Windows: doble clic.
:: Pide permisos de administrador y ejecuta instalar.ps1.
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar.ps1"
pause
