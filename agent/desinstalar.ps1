# Desinstalador del agente ALFA-Sentinel para Windows.
# Se ejecuta con doble clic en desinstalar.bat (pide permisos de administrador).
#
# Detiene y elimina la tarea del sistema, levanta el aislamiento de red si
# el equipo quedó aislado (para no dejarlo sin red) y borra el agente.
# Los honeyfiles de las carpetas del usuario (ALFA_ARCHIVOS) no se tocan.
$Dest = Join-Path $env:ProgramFiles "ALFA-Sentinel"
$TaskName = "ALFA-Sentinel"

if ((Read-Host "¿Desinstalar el agente ALFA-Sentinel de este equipo? [s/N]") -ne "s") { Write-Host "Cancelado."; exit 0 }

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
# Por si quedó algún proceso del agente vivo.
Get-CimInstance Win32_Process -Filter "Name = 'python.exe'" |
    Where-Object { $_.CommandLine -like "*ALFA-Sentinel*main.py*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

$VenvPython = Join-Path $Dest ".venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    Write-Host "Levantando el aislamiento de red (si estaba activo)..."
    Push-Location $Dest
    & $VenvPython -c "import isolation_executor as ie; print(ie.release_if_isolated())"
    Pop-Location
}

# Este script vive dentro de la carpeta que se borra; PowerShell ya lo
# cargó en memoria, solo hay que salir de esa carpeta antes de borrarla.
Set-Location $env:TEMP
Remove-Item $Dest -Recurse -Force -ErrorAction SilentlyContinue
if (Test-Path $Dest) {
    Write-Host "No se pudo borrar todo $Dest (algún archivo en uso). Bórralo a mano." -ForegroundColor Yellow
} else {
    Write-Host "Agente desinstalado." -ForegroundColor Green
}
Write-Host "El equipo sigue figurando en la consola: puedes revocarlo desde allí."
