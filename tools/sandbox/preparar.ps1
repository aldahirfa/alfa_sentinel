# Se ejecuta DENTRO de la Windows Sandbox al iniciar sesión (lo lanza
# preparar.cmd). Instala Python, ofrece instalar RanSim y lanza el
# instalador del agente con el servidor y la carpeta de RanSim sugeridos.
$ErrorActionPreference = "Stop"
$Kit = "C:\Kit"
$Puerto = 8000

function Ok($t) { Write-Host "  OK  $t" -ForegroundColor Green }
function Aviso($t) { Write-Host "  !   $t" -ForegroundColor Yellow }

Write-Host "=============================================="
Write-Host "   Preparando la sandbox para ALFA-Sentinel"
Write-Host "=============================================="

# --- Python ----------------------------------------------------------------
$py = Get-ChildItem "$Kit\descargas" -Filter "python-3*-amd64.exe" | Select-Object -First 1
Write-Host "`nInstalando $($py.Name) (1-2 minutos)..."
Start-Process -FilePath $py.FullName -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait
if (-not (Get-Command py -ErrorAction SilentlyContinue)) { Aviso "No se pudo instalar Python."; return }
Ok "Python instalado"

# --- Servidor: la primera IP del certificado que responda desde acá ----------
$Servidor = $null
foreach ($url in Get-Content "$Kit\servidor.txt") {
    $ip = ([uri]$url).Host
    if (Test-NetConnection $ip -Port $Puerto -InformationLevel Quiet -WarningAction SilentlyContinue) { $Servidor = $url; break }
}
if ($Servidor) {
    Ok "Servidor alcanzable: $Servidor"
} else {
    $gateway = (Get-NetRoute -DestinationPrefix "0.0.0.0/0" | Sort-Object RouteMetric | Select-Object -First 1).NextHop
    Aviso "Ninguna IP del certificado del servidor responde desde la sandbox."
    Aviso "Desde aquí la laptop se ve como $gateway. En la laptop ejecuta:"
    Aviso "  python generar_certificados.py --ip <IP actual> --ip $gateway --force-server"
    Aviso "reinicia el servidor y vuelve a abrir la sandbox."
    $Servidor = "https://${gateway}:$Puerto"
}

# --- RanSim ----------------------------------------------------------------
$ransim = Get-ChildItem "$Kit\descargas" | Where-Object { $_.Name -match "ransim|simulator" } | Select-Object -First 1
if ($ransim) {
    Write-Host "`nSe abre el instalador de RanSim: complétalo y vuelve a esta ventana."
    Start-Process -FilePath $ransim.FullName -Wait
    Ok "RanSim instalado (C:\KB4\Newsim)"
}

# --- Agente ------------------------------------------------------------------
Write-Host "`nInstalando el agente. Deja los valores sugeridos (ENTER) y escribe el código de registro."
& "$Kit\agent\instalar.ps1" -ServidorSugerido $Servidor -CarpetasSugeridas "C:\KB4\Newsim\DataDir"
