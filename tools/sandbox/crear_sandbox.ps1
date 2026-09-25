# Arma y abre una Windows Sandbox lista para probar ALFA-Sentinel con RanSim.
# Se ejecuta con doble clic en abrir_sandbox.bat, en la laptop (anfitrión).
#
# La Windows Sandbox se borra entera al cerrarla. Este script prepara una
# carpeta 'kit' con el agente, el instalador de Python y el de RanSim, y
# un archivo .wsb que la comparte con la sandbox en SOLO LECTURA (así nada
# de lo que pase adentro puede modificar archivos de la laptop). Al abrir
# la sandbox, preparar.ps1 instala Python y lanza el instalador del agente
# con el servidor y la carpeta de RanSim ya sugeridos: solo falta escribir
# el código de registro.
$ErrorActionPreference = "Stop"
$Aqui = $PSScriptRoot
$Repo = (Resolve-Path (Join-Path $Aqui "..\..")).Path
$Descargas = Join-Path $Aqui "descargas"
$Kit = Join-Path $Aqui "kit"
$Puerto = 8000

function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  !   $t" -ForegroundColor Yellow }
function Falla($t) { Write-Host "  X   $t" -ForegroundColor Red; Read-Host "`nPresiona ENTER para salir"; exit 1 }

Write-Host "=============================================="
Write-Host "   Windows Sandbox para ALFA-Sentinel + RanSim"
Write-Host "=============================================="

# --- 1. Requisitos en la laptop -----------------------------------------
if (-not (Test-Path "$env:windir\System32\WindowsSandbox.exe")) {
    Falla "Windows Sandbox no está activada. Actívala en 'Activar o desactivar las características de Windows' > 'Espacio aislado de Windows' y reinicia."
}
New-Item -ItemType Directory -Force -Path $Descargas | Out-Null
$InstaladorPython = Get-ChildItem $Descargas -Filter "python-3*-amd64.exe" | Sort-Object Name -Descending | Select-Object -First 1
if (-not $InstaladorPython) {
    Falla "Falta el instalador de Python. Descarga 'Windows installer (64-bit)' de Python 3.12 desde python.org y guárdalo en: $Descargas"
}
Ok "Python: $($InstaladorPython.Name)"
$InstaladorRanSim = Get-ChildItem $Descargas | Where-Object { $_.Name -match "ransim|simulator" } | Select-Object -First 1
if ($InstaladorRanSim) { Ok "RanSim: $($InstaladorRanSim.Name)" } else { Aviso "No está el instalador de RanSim en $Descargas (puedes agregarlo después)." }
if (-not (Test-Path "$Repo\agent\certs\ca.crt")) { Falla "Falta agent\certs\ca.crt (ejecuta server\generar_certificados.py)." }

# IPs incluidas en el certificado del servidor: la sandbox solo puede usar una de estas.
$CertServidor = "$Repo\server\certs\server.crt"
if (-not (Test-Path $CertServidor)) { Falla "Falta server\certs\server.crt (ejecuta server\generar_certificados.py)." }
$cert = New-Object Security.Cryptography.X509Certificates.X509Certificate2($CertServidor)
$san = ($cert.Extensions | Where-Object { $_.Oid.Value -eq "2.5.29.17" }).Format($false)
$IpsCertificado = @([regex]::Matches($san, "(\d{1,3}\.){3}\d{1,3}") | ForEach-Object { $_.Value } | Where-Object { $_ -ne "127.0.0.1" } | Select-Object -Unique)
if (-not $IpsCertificado) { Falla "El certificado del servidor no incluye ninguna IP de red. Regenera con: python generar_certificados.py --ip <IP> --force-server" }
Ok "IPs en el certificado del servidor: $($IpsCertificado -join ', ')"

if (Test-NetConnection 127.0.0.1 -Port $Puerto -InformationLevel Quiet -WarningAction SilentlyContinue) {
    Ok "El servidor está escuchando en el puerto $Puerto"
} else {
    Aviso "El servidor no responde en el puerto $Puerto. Arráncalo (server\run_server.py) antes de registrar el agente."
}

# La sandbox llega a la laptop por una red virtual que Windows considera
# 'Pública': sin esta regla, el firewall de la laptop bloquea al agente.
$NombreRegla = "ALFA-Sentinel servidor ($Puerto)"
if (-not (Get-NetFirewallRule -DisplayName $NombreRegla -ErrorAction SilentlyContinue)) {
    $r = Read-Host "  Crear una regla en el firewall de la laptop que permita conexiones entrantes al puerto $Puerto (necesaria para la sandbox)? [S/n]"
    if ($r -ne "n") {
        New-NetFirewallRule -DisplayName $NombreRegla -Direction Inbound -Protocol TCP -LocalPort $Puerto -Action Allow | Out-Null
        Ok "Regla de firewall creada"
    } else {
        Aviso "Sin la regla, el agente de la sandbox probablemente no llegue al servidor."
    }
} else {
    Ok "Regla de firewall para el puerto $Puerto presente"
}

# --- 2. Kit compartido con la sandbox ------------------------------------
if (Test-Path $Kit) { Remove-Item $Kit -Recurse -Force }
New-Item -ItemType Directory -Force -Path "$Kit\descargas" | Out-Null
robocopy "$Repo\agent" "$Kit\agent" /E /NFL /NDL /NJH /NJS /NP `
    /XD .venv __pycache__ logs honeyfiles test_endpoint test_files `
    /XF agent_credential.json agent_config.json isolation_state.json *.pyc | Out-Null
if ($LASTEXITCODE -ge 8) { Falla "No se pudo copiar el agente al kit." }
Copy-Item $InstaladorPython.FullName "$Kit\descargas\"
if ($InstaladorRanSim) { Copy-Item $InstaladorRanSim.FullName "$Kit\descargas\" }
Copy-Item (Join-Path $Aqui "preparar.ps1") "$Kit\"
Set-Content -Path "$Kit\servidor.txt" -Value ($IpsCertificado | ForEach-Object { "https://${_}:$Puerto" }) -Encoding ASCII

# Se ejecuta al iniciar sesión en la sandbox.
Set-Content -Path "$Kit\preparar.cmd" -Encoding ASCII -Value @'
@echo off
powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process powershell -Verb RunAs -ArgumentList '-NoProfile -ExecutionPolicy Bypass -NoExit -File C:\Kit\preparar.ps1'"
'@

$wsb = @"
<Configuration>
  <Networking>Enable</Networking>
  <MemoryInMB>4096</MemoryInMB>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>$Kit</HostFolder>
      <SandboxFolder>C:\Kit</SandboxFolder>
      <ReadOnly>true</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>C:\Kit\preparar.cmd</Command>
  </LogonCommand>
</Configuration>
"@
$ArchivoWsb = Join-Path $Kit "ALFA-Sentinel.wsb"
Set-Content -Path $ArchivoWsb -Value $wsb -Encoding UTF8
Ok "Kit listo en $Kit"

Write-Host "`nAbriendo la Windows Sandbox..." -ForegroundColor White
Write-Host "Adentro se abre una ventana que instala Python y luego el agente."
Write-Host "Ten a mano un código de registro (Consola > Administración > Agentes)."
Start-Process $ArchivoWsb
