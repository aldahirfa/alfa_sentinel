# Instalador del agente ALFA-Sentinel para Windows.
# Se ejecuta con doble clic en instalar.bat (pide permisos de administrador).
#
# Pregunta la dirección del servidor y el código de registro, y hace el
# resto: copia el agente a C:\Program Files\ALFA-Sentinel (solo
# administradores pueden modificarlo), instala dependencias, registra el
# agente, guarda la configuración y lo deja como tarea del sistema que
# arranca con el equipo (cuenta SYSTEM) y se reinicia si se detiene.
$ErrorActionPreference = "Stop"
$Dest = Join-Path $env:ProgramFiles "ALFA-Sentinel"
$TaskName = "ALFA-Sentinel"
$Src = $PSScriptRoot

function Paso($n, $texto) { Write-Host "`n[$n] $texto" -ForegroundColor White }
function Ok($texto) { Write-Host "  OK  $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "  !   $texto" -ForegroundColor Yellow }
function Falla($texto) { Write-Host "  X   $texto" -ForegroundColor Red; Read-Host "`nPresiona ENTER para salir"; exit 1 }
function Preguntar($texto, $defecto) {
    $r = Read-Host "  $texto [$defecto]"
    if ([string]::IsNullOrWhiteSpace($r)) { return $defecto } else { return $r.Trim() }
}

Write-Host "=============================================="
Write-Host "   Instalación del agente ALFA-Sentinel"
Write-Host "=============================================="

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Falla "Ejecuta instalar.bat (pide permisos de administrador)."
}

# --- 1. Requisitos -------------------------------------------------------
Paso "1/6" "Verificando requisitos"
$Python = $null
$Candidatos = @(
    @{ Cmd = "py"; Args = @("-3") },
    @{ Cmd = "python"; Args = @() }
)
foreach ($candidato in $Candidatos) {
    try {
        $exe = & $candidato.Cmd @($candidato.Args) -c "import sys; print(sys.executable if sys.version_info >= (3, 10) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe -and (Test-Path $exe) -and $exe -notmatch "WindowsApps") { $Python = $exe.Trim(); break }
    } catch { }
}
if (-not $Python) { Falla "Falta Python 3.10 o superior. Instálalo desde python.org (marcando 'Add python.exe to PATH') y vuelve a ejecutar el instalador." }
if (-not (Test-Path (Join-Path $Src "certs\ca.crt"))) { Falla "Falta certs\ca.crt junto al instalador. Cópialo desde server\certs\ca.crt." }
Ok "Python: $Python"

# --- 2. Datos ------------------------------------------------------------
Paso "2/6" "Datos de instalación"
$ConfigFile = Join-Path $Dest "agent_config.json"
$CredFile = Join-Path $Dest "agent_credential.json"
$Conservar = $false
if (Test-Path $CredFile) {
    $Conservar = (Read-Host "  Este equipo ya está registrado. ¿Conservar el registro actual? [S/n]") -ne "n"
}
$ServidorActual = "https://192.168.81.1:8000"
if (Test-Path $ConfigFile) {
    try { $ServidorActual = (Get-Content $ConfigFile -Raw | ConvertFrom-Json).server_url } catch { }
}
do {
    $Servidor = (Preguntar "Dirección del servidor" $ServidorActual).TrimEnd("/")
    $valido = $Servidor -match "^https://[^/]+$"
    if (-not $valido) { Aviso "Debe ser https://IP:puerto, por ejemplo https://192.168.81.1:8000" }
} until ($valido)

# Usuario con la sesión abierta (el que se protege), aunque el instalador
# se haya elevado con otra cuenta de administrador.
$UsuarioDefecto = ((Get-CimInstance Win32_ComputerSystem).UserName -split "\\")[-1]
if (-not $UsuarioDefecto) { $UsuarioDefecto = $env:USERNAME }
$Perfiles = Get-CimInstance Win32_UserProfile | Where-Object { -not $_.Special } | ForEach-Object { Split-Path $_.LocalPath -Leaf }
do {
    $Usuario = Preguntar "Usuario del equipo a proteger" $UsuarioDefecto
    $valido = $Perfiles -contains $Usuario
    if (-not $valido) { Aviso "No hay un perfil '$Usuario' en este equipo. Perfiles: $($Perfiles -join ', ')" }
} until ($valido)

# --- 3. Copia ------------------------------------------------------------
Paso "3/6" "Copiando el agente a $Dest"
Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
robocopy $Src $Dest /E /NFL /NDL /NJH /NJS /NP `
    /XD .venv __pycache__ logs honeyfiles test_endpoint test_files `
    /XF agent_credential.json agent_config.json isolation_state.json *.pyc | Out-Null
if ($LASTEXITCODE -ge 8) { Falla "No se pudieron copiar los archivos del agente." }
$config = [ordered]@{ server_url = $Servidor; env_mode = "production"; protected_user = $Usuario } | ConvertTo-Json -Compress
[IO.File]::WriteAllText($ConfigFile, $config, (New-Object Text.UTF8Encoding($false)))
Ok "Agente copiado"

# --- 4. Dependencias -----------------------------------------------------
Paso "4/6" "Instalando dependencias (puede tardar un minuto)"
$VenvPython = Join-Path $Dest ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) { & $Python -m venv (Join-Path $Dest ".venv") }
& $VenvPython -m pip install --quiet --disable-pip-version-check -r (Join-Path $Dest "requirements.txt")
if ($LASTEXITCODE -ne 0) { Falla "No se pudieron instalar las dependencias (¿hay conexión a internet?)." }
Ok "Dependencias instaladas"

# --- 5. Registro ---------------------------------------------------------
Paso "5/6" "Registrando el equipo en el servidor"
if ($Conservar) {
    Ok "Se conserva el registro existente"
} else {
    Remove-Item $CredFile -Force -ErrorAction SilentlyContinue
    $Log = Join-Path $env:TEMP "alfa-registro.log"
    for ($intento = 1; $intento -le 3; $intento++) {
        $Codigo = Read-Host "  Código de registro (Consola > Administración > Agentes, ej. ABCD-EFGH)"
        Push-Location $Dest
        & $VenvPython main.py --enroll $Codigo *> $Log
        $resultado = $LASTEXITCODE
        Pop-Location
        if ($resultado -eq 0) { Ok "Equipo registrado"; break }
        $motivo = Select-String -Path $Log -Pattern "rechazó|contactar|certificado|⚠" | Select-Object -Last 1
        Aviso "No se pudo registrar: $($motivo.Line)"
        if ($intento -eq 3) { Falla "No se pudo registrar el equipo. Detalle en $Log" }
        Write-Host "  Genera un código nuevo en la consola e inténtalo otra vez."
    }
}
# Credencial y configuración: solo SYSTEM y Administradores (SID, no el
# nombre del grupo, que cambia según el idioma de Windows).
foreach ($f in @($CredFile, $ConfigFile)) {
    icacls $f /inheritance:r /grant:r "*S-1-5-18:F" "*S-1-5-32-544:F" | Out-Null
}

# --- 6. Servicio ---------------------------------------------------------
Paso "6/6" "Instalando el servicio"
$action = New-ScheduledTaskAction -Execute $VenvPython -Argument "`"$Dest\main.py`" --service" -WorkingDirectory $Dest
# Al iniciar el equipo, y además cada 5 minutos: si el agente se cerró por
# cualquier motivo, vuelve a arrancar (nunca corren dos a la vez).
$triggers = @(
    (New-ScheduledTaskTrigger -AtStartup),
    (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 5))
)
$taskPrincipal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Principal $taskPrincipal `
    -Settings $settings -Description "Agente ALFA-Sentinel (detección temprana de ransomware)" -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 5
if ((Get-ScheduledTask -TaskName $TaskName).State -eq "Running") {
    Ok "Servicio en ejecución"
} else {
    Falla "El agente no arrancó. Revisa $Dest\logs\agente.log"
}

Write-Host "`n==============================================" -ForegroundColor Green
Write-Host "   Instalación completa" -ForegroundColor Green
Write-Host "==============================================" -ForegroundColor Green
Write-Host "El equipo aparecerá 'En línea' en la consola en unos segundos."
Write-Host "  Registro:    $Dest\logs\agente.log"
Write-Host "  Desinstalar: $Dest\desinstalar.bat"
