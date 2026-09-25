@echo off
:: Arma y abre una Windows Sandbox con el agente ALFA-Sentinel y RanSim.
:: Pide permisos de administrador (para la regla del firewall del puerto 8000).
net session >nul 2>&1
if %errorlevel% neq 0 (
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0crear_sandbox.ps1"
pause
