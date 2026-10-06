# Guardián del agente ALFA-Sentinel para Windows (2026-10-06).
#
# Por qué existe: en una prueba con LockBit real, el ransomware terminó el
# proceso del agente ANTES de cifrar. Sin agente no había alerta ni
# aislamiento. El guardián es un segundo proceso, independiente del agente,
# que trata esa terminación como el ataque que es:
#   1. aísla el equipo en el acto (mismas reglas que isolation_executor.py,
#      así la consola lo libera igual que cualquier otro aislamiento);
#   2. avisa al servidor con la regla "Agente Detenido Inesperadamente"
#      (peso 100 -> CRÍTICO -> incidente y orden de aislamiento);
#   3. deja estado\agente_terminado.json por si el aviso no llegó: el
#      agente lo reporta al volver a iniciarse.
#
# No actúa si el agente se cerró de forma normal (estado\detencion_limpia,
# ver guard_state.py) ni si Windows se está apagando. El instalador y el
# desinstalador detienen este guardián ANTES de tocar el agente.
#
# Es PowerShell y no Python a propósito: no depende de ningún archivo del
# agente (que el ransomware puede cifrar o bloquear en el mismo segundo);
# la configuración, la credencial y la CA se leen al arrancar y quedan en
# memoria.
#
# Lo ejecuta la tarea "ALFA-Sentinel-Guardian" (cuenta SYSTEM, al iniciar
# el equipo y cada minuto si no está corriendo).
#
#   -Simular: pruebas. Hace todo salvo tocar el firewall; en lugar de enviar
#             la alerta, comprueba la conexión TLS con el servidor.
param(
    [switch]$Simular,
    [string]$Directorio = $PSScriptRoot
)

$ErrorActionPreference = "Continue"
$Dir = $Directorio
$EstadoDir = Join-Path $Dir "estado"
$LogDir = Join-Path $Dir "logs"
$LogFile = Join-Path $LogDir "guardian.log"
$MarcaLimpia = Join-Path $EstadoDir "detencion_limpia"
$MarcaTerminado = Join-Path $EstadoDir "agente_terminado.json"
$EstadoFirewall = Join-Path $Dir "isolation_state.json"
$ReglaServidor = "Agente Detenido Inesperadamente"
$ModosReales = @("production", "controlled_test", "laboratory")

# Mismos nombres que isolation_executor.py: el agente los reconoce al liberar.
$ReglaAllowOut = "ALFA_SENTINEL_ALLOW_OUT"
$ReglaBlockIn = "ALFA_SENTINEL_BLOCK_IN"
$ReglaBlockOutOtros = "ALFA_SENTINEL_BLOCK_OUT_OTROS"
$ReglaBlockOutServidorTcp = "ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_TCP"
$ReglaBlockOutServidorUdp = "ALFA_SENTINEL_BLOCK_OUT_SERVIDOR_UDP"
$ReglaLegacyAllowIn = "ALFA_SENTINEL_ALLOW_IN"

function Log([string]$texto) {
    try {
        New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
        if ((Test-Path $LogFile) -and (Get-Item $LogFile).Length -gt 5MB) {
            Move-Item $LogFile "$LogFile.1" -Force
        }
        Add-Content -Path $LogFile -Value ("{0} {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $texto) -Encoding UTF8
    } catch { }
}

Add-Type -TypeDefinition @"
using System;
using System.Net.Security;
using System.Runtime.InteropServices;
using System.Security.Cryptography.X509Certificates;

public static class AlfaGuardian {
    [DllImport("user32.dll")]
    static extern int GetSystemMetrics(int index);

    // SM_SHUTTINGDOWN: distinto de 0 mientras Windows se apaga o reinicia.
    public static bool ShuttingDown() { return GetSystemMetrics(0x2000) != 0; }

    // Misma política que agent/transport.py: solo se confía en la CA propia
    // de ALFA-Sentinel y el nombre/IP tiene que coincidir con el certificado.
    public static X509Certificate2 Ca;

    public static bool Validate(object sender, X509Certificate cert, X509Chain chain, SslPolicyErrors errors) {
        if (cert == null || Ca == null) return false;
        if ((errors & (SslPolicyErrors.RemoteCertificateNameMismatch | SslPolicyErrors.RemoteCertificateNotAvailable)) != 0) return false;
        using (X509Chain own = new X509Chain()) {
            own.ChainPolicy.RevocationMode = X509RevocationMode.NoCheck;
            own.ChainPolicy.VerificationFlags = X509VerificationFlags.AllowUnknownCertificateAuthority;
            own.ChainPolicy.ExtraStore.Add(Ca);
            if (!own.Build(new X509Certificate2(cert))) return false;
            X509Certificate2 root = own.ChainElements[own.ChainElements.Count - 1].Certificate;
            return root.Thumbprint == Ca.Thumbprint;
        }
    }

    public static RemoteCertificateValidationCallback Callback = Validate;
}
"@

# --- Configuración (queda en memoria) ------------------------------------
function Leer-Configuracion {
    $cfg = Get-Content (Join-Path $Dir "agent_config.json") -Raw -ErrorAction Stop | ConvertFrom-Json
    $cred = (Get-Content (Join-Path $Dir "agent_credential.json") -Raw -ErrorAction Stop | ConvertFrom-Json).credential
    if (-not $cred) { throw "agent_credential.json no tiene credencial." }
    $uri = [Uri]$cfg.server_url
    $ips = @()
    $directa = $null
    if ([Net.IPAddress]::TryParse($uri.Host, [ref]$directa)) {
        $ips = @($directa)
    } else {
        $ips = @([Net.Dns]::GetHostAddresses($uri.Host))
    }
    # Solo IPv4, como en la práctica (SERVER_URL con la IP del servidor).
    $ips = @($ips | Where-Object { $_.AddressFamily -eq "InterNetwork" } | ForEach-Object { $_.ToString() } | Sort-Object -Unique)
    if ($ips.Count -eq 0) { throw "El servidor $($uri.Host) no resolvió a ninguna IPv4." }
    [AlfaGuardian]::Ca = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2 (Join-Path $Dir "certs\ca.crt")
    return [pscustomobject]@{
        Url        = $cfg.server_url.TrimEnd("/")
        Puerto     = $uri.Port
        Ips        = $ips
        Credencial = $cred
        Real       = ($ModosReales -contains "$($cfg.env_mode)".ToLower()) -and -not $Simular
    }
}

# --- Aislamiento (equivalente a isolation_executor.py::_isolate_windows) --
function A-Numero([string]$ip) {
    $b = ([Net.IPAddress]::Parse($ip)).GetAddressBytes()
    return ([uint64]$b[0] -shl 24) + ([uint64]$b[1] -shl 16) + ([uint64]$b[2] -shl 8) + [uint64]$b[3]
}

function A-Ip([uint64]$n) {
    return "{0}.{1}.{2}.{3}" -f (($n -shr 24) -band 255), (($n -shr 16) -band 255), (($n -shr 8) -band 255), ($n -band 255)
}

function Rango-A-Cidr([uint64]$a, [uint64]$b) {
    $bloques = @()
    while ($a -le $b) {
        $prefijo = 32
        while ($prefijo -gt 0) {
            $tam = [uint64]1 -shl (33 - $prefijo)
            if (($a % $tam) -ne 0 -or ($a + $tam - 1) -gt $b) { break }
            $prefijo--
        }
        $bloques += "$(A-Ip $a)/$prefijo"
        $a += [uint64]1 -shl (32 - $prefijo)
    }
    return $bloques
}

# Todas las direcciones salvo las del servidor (netsh no tiene "todas menos X").
function Otras-Direcciones([string[]]$ips) {
    $redes = @()
    $inicio = [uint64]0
    foreach ($n in ($ips | ForEach-Object { A-Numero $_ } | Sort-Object -Unique)) {
        if ($n -gt $inicio) { $redes += Rango-A-Cidr $inicio ($n - 1) }
        $inicio = $n + 1
    }
    if ($inicio -le 4294967295) { $redes += Rango-A-Cidr $inicio 4294967295 }
    # Todo IPv6. No "::/0": netsh rechaza los prefijos /0 ("One or more of
    # the address prefixes is invalid"); estas dos mitades cubren lo mismo.
    $redes += "::/1"
    $redes += "8000::/1"
    return ($redes -join ",")
}

function Puertos-Excepto([int]$puerto) {
    $rangos = @()
    if ($puerto -gt 1) { $rangos += $(if ($puerto -gt 2) { "1-$($puerto - 1)" } else { "1" }) }
    if ($puerto -lt 65535) { $rangos += $(if ($puerto -lt 65534) { "$($puerto + 1)-65535" } else { "65535" }) }
    return ($rangos -join ",")
}

function Netsh([string[]]$argumentos) {
    $salida = & netsh.exe @argumentos 2>&1
    if ($LASTEXITCODE -ne 0) {
        # Solo la línea del error: netsh imprime además toda su ayuda.
        $linea = @($salida | ForEach-Object { "$_".Trim() } | Where-Object { $_ }) | Select-Object -First 1
        throw "netsh $($argumentos[0..4] -join ' '): $linea"
    }
}

# Perfiles del firewall leídos del REGISTRO, no con Get-NetFirewallProfile:
# en Windows Sandbox esa clase no existe ("Clase no válida") y la verificación
# no comprobaba nada. Mismos valores que isolation_executor.py::_win_read_profiles.
$ClavePoliticas = "HKLM:\SYSTEM\CurrentControlSet\Services\SharedAccess\Parameters\FirewallPolicy"
$PerfilesRegistro = [ordered]@{ Domain = "DomainProfile"; Private = "StandardProfile"; Public = "PublicProfile" }

function Valor-Perfil($valor, [string]$siUno, [string]$siCero) {
    if ($null -eq $valor) { return "NotConfigured" }
    if ($valor -eq 1) { return $siUno }
    if ($valor -eq 0) { return $siCero }
    return "NotConfigured"
}

function Leer-Perfiles {
    $perfiles = [ordered]@{}
    foreach ($nombre in $PerfilesRegistro.Keys) {
        $v = Get-ItemProperty -Path (Join-Path $ClavePoliticas $PerfilesRegistro[$nombre]) -ErrorAction Stop
        $perfiles[$nombre] = [ordered]@{
            Enabled = Valor-Perfil $v.EnableFirewall "True" "False"
            In      = Valor-Perfil $v.DefaultInboundAction "Block" "Allow"
            Out     = Valor-Perfil $v.DefaultOutboundAction "Block" "Allow"
        }
    }
    return $perfiles
}

function Aislar($cfg) {
    $servidores = $cfg.Ips -join ","
    $otrosPuertos = Puertos-Excepto $cfg.Puerto
    $pasos = @(
        @("advfirewall", "firewall", "add", "rule", "name=$ReglaAllowOut", "dir=out", "action=allow", "protocol=TCP", "remoteip=$servidores", "remoteport=$($cfg.Puerto)"),
        @("advfirewall", "firewall", "add", "rule", "name=$ReglaBlockIn", "dir=in", "action=block", "remoteip=any")
    )
    if ($otrosPuertos) {
        $pasos += , @("advfirewall", "firewall", "add", "rule", "name=$ReglaBlockOutServidorTcp", "dir=out", "action=block", "protocol=TCP", "remoteip=$servidores", "remoteport=$otrosPuertos")
    }
    $pasos += , @("advfirewall", "firewall", "add", "rule", "name=$ReglaBlockOutOtros", "dir=out", "action=block", "remoteip=$(Otras-Direcciones $cfg.Ips)")
    $pasos += , @("advfirewall", "firewall", "add", "rule", "name=$ReglaBlockOutServidorUdp", "dir=out", "action=block", "protocol=UDP", "remoteip=$servidores")
    $pasos += , @("advfirewall", "set", "allprofiles", "state", "on")
    $pasos += , @("advfirewall", "set", "allprofiles", "firewallpolicy", "blockinbound,blockoutbound")

    if (-not $cfg.Real) {
        return "SIMULADO: se habrían aplicado $($pasos.Count) cambios de firewall dejando solo $($servidores):$($cfg.Puerto)/tcp."
    }

    # Estado previo del firewall, en el mismo formato que isolation_executor.py,
    # para que la liberación desde la consola lo restaure.
    if (-not (Test-Path $EstadoFirewall)) {
        $perfiles = Leer-Perfiles
        [IO.File]::WriteAllText($EstadoFirewall, (@{ windows_profiles = $perfiles } | ConvertTo-Json -Depth 4 -Compress))
    }

    foreach ($nombre in @($ReglaBlockIn, $ReglaBlockOutOtros, $ReglaBlockOutServidorTcp, $ReglaBlockOutServidorUdp, $ReglaAllowOut, $ReglaLegacyAllowIn)) {
        & netsh.exe advfirewall firewall delete rule "name=$nombre" 2>&1 | Out-Null
    }
    foreach ($paso in $pasos) { Netsh $paso }

    $perfiles = Leer-Perfiles
    $mal = @($perfiles.Keys | Where-Object { $perfiles[$_].Enabled -ne "True" -or $perfiles[$_].In -ne "Block" -or $perfiles[$_].Out -ne "Block" })
    if ($mal.Count -gt 0) { throw "los perfiles del firewall no quedaron bloqueados: $($mal -join ', ')" }
    return "aplicado por el guardián: solo se permite $($servidores):$($cfg.Puerto)/tcp."
}

# --- Aviso al servidor ---------------------------------------------------
function Pedido-Servidor($cfg, [string]$metodo, [string]$ruta, $cuerpo) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $req = [Net.HttpWebRequest]::Create("$($cfg.Url)$ruta")
    $req.Method = $metodo
    $req.Timeout = 10000
    $req.ServerCertificateValidationCallback = [AlfaGuardian]::Callback
    $req.Headers.Add("X-Agent-Credential", $cfg.Credencial)
    if ($cuerpo) {
        $bytes = [Text.Encoding]::UTF8.GetBytes(($cuerpo | ConvertTo-Json -Compress))
        $req.ContentType = "application/json; charset=utf-8"
        $req.ContentLength = $bytes.Length
        $flujo = $req.GetRequestStream()
        $flujo.Write($bytes, 0, $bytes.Length)
        $flujo.Close()
    }
    try {
        $resp = $req.GetResponse()
        $codigo = [int]$resp.StatusCode
        $resp.Close()
        return $codigo
    } catch [Net.WebException] {
        if ($_.Exception.Response) { return [int]$_.Exception.Response.StatusCode }
        throw
    }
}

function Avisar-Servidor($cfg, [string]$detalle) {
    $hora = Get-Date -Format "HH:mm:ss"
    $alerta = @{
        title         = "Agente detenido de forma inesperada"
        description   = "El guardián del equipo detectó que el agente fue terminado sin un cierre normal a las $hora (no fue un apagado, una actualización ni una desinstalación). Aislamiento local: $detalle"
        matched_rules = @($ReglaServidor)
    }
    if ($Simular) {
        # Sin crear datos: solo se comprueba que el canal TLS con la CA propia funciona.
        $codigo = Pedido-Servidor $cfg "GET" "/agent/test" $null
        Log "SIMULADO: conexión TLS con el servidor OK (HTTP $codigo); no se envió la alerta."
        return $true
    }
    $codigo = Pedido-Servidor $cfg "POST" "/agent/alerts" $alerta
    return ($codigo -ge 200 -and $codigo -lt 300)
}

function Guardar-Marca($datos) {
    try {
        New-Item -ItemType Directory -Force -Path $EstadoDir | Out-Null
        [IO.File]::WriteAllText($MarcaTerminado, ($datos | ConvertTo-Json -Compress))
    } catch { Log "No se pudo guardar $($MarcaTerminado): $_" }
}

# --- Vigilancia del agente -----------------------------------------------
function Buscar-Agente {
    $dirMin = $Dir.ToLower()
    return @(Get-CimInstance Win32_Process -Filter "Name LIKE 'python%'" -ErrorAction SilentlyContinue | Where-Object {
        $linea = "$($_.CommandLine)".ToLower()
        $linea.Contains($dirMin) -and $linea.Contains("main.py") -and $linea.Contains("--service")
    })
}

# El agente escribe estado\latido cada 10 s (guard_state.py). Si el proceso
# sigue vivo pero el latido (o, si todavía no escribió ninguno, su hora de
# arranque) tiene más de este tiempo, está congelado.
$LimiteSinLatido = 90
$MarcaLatido = Join-Path $EstadoDir "latido"

function Agente-Congelado($vigilados) {
    $referencias = @()
    foreach ($proceso in $vigilados.Values) {
        try { if (-not $proceso.HasExited) { $referencias += $proceso.StartTime } } catch { }
    }
    if ($referencias.Count -eq 0) { return $false }
    try { if (Test-Path $MarcaLatido) { $referencias += (Get-Item $MarcaLatido).LastWriteTime } } catch { }
    $masReciente = $referencias | Sort-Object | Select-Object -Last 1
    return ((Get-Date) - $masReciente).TotalSeconds -gt $LimiteSinLatido
}

function Responder-Terminacion($cfg) {
    Log "ALERTA: el agente fue terminado de forma inesperada. Aislando el equipo y avisando al servidor."
    try {
        $detalle = Aislar $cfg
        Log "Aislamiento: $detalle"
    } catch {
        $detalle = "FALLÓ ($_)"
        Log "Aislamiento FALLÓ: $_"
    }
    $marca = @{ detected_at = (Get-Date -Format "yyyy-MM-dd HH:mm:ss"); isolation = $detalle; reported = $false }
    Guardar-Marca $marca
    try {
        if (Avisar-Servidor $cfg $detalle) {
            $marca.reported = $true
            Guardar-Marca $marca
            if (-not $Simular) { Log "Alerta CRÍTICA enviada al servidor." }
        } else {
            Log "El servidor no aceptó la alerta; el agente la enviará al volver a iniciarse."
        }
    } catch {
        Log "No se pudo avisar al servidor ($_); el agente lo hará al volver a iniciarse."
    }
    # Sin esto, Windows recién lo vuelve a iniciar en la próxima repetición
    # de su tarea (hasta 5 minutos), y mientras tanto el equipo no tiene
    # quien confirme el aislamiento ni vigile los archivos.
    if (-not $Simular) {
        try {
            Start-ScheduledTask -TaskName "ALFA-Sentinel" -ErrorAction Stop
            Log "Agente reiniciado."
        } catch {
            Log "No se pudo reiniciar el agente ($_); Windows lo hará en la próxima repetición de su tarea."
        }
    }
}

Log "Guardián iniciado (PID $PID)$(if ($Simular) { ' en modo SIMULADO' })."
$cfg = $null
while (-not $cfg) {
    try {
        $cfg = Leer-Configuracion
        Log "Configuración cargada: servidor $($cfg.Url) ($($cfg.Ips -join ', ')), aislamiento $(if ($cfg.Real) { 'REAL' } else { 'SIMULADO' })."
    } catch {
        Log "Todavía no se puede leer la configuración del agente ($_). Reintento en 30 s."
        Start-Sleep -Seconds 30
    }
}

while ($true) {
    $encontrados = Buscar-Agente
    if ($encontrados.Count -eq 0) { Start-Sleep -Seconds 2; continue }

    $vigilados = @{}
    foreach ($p in $encontrados) {
        try { $vigilados[[int]$p.ProcessId] = [Diagnostics.Process]::GetProcessById([int]$p.ProcessId) } catch { }
    }
    if ($vigilados.Count -eq 0) { Start-Sleep -Seconds 1; continue }
    Log "Vigilando el agente (PID $(@($vigilados.Keys) -join ', '))."

    $vueltas = 0
    $revisionesSinLatido = 0
    $reinicioPropio = $false
    while (@($vigilados.Values | Where-Object { -not $_.HasExited }).Count -gt 0) {
        Start-Sleep -Milliseconds 500
        $vueltas++
        # Agente congelado: vivo pero sin latido (ver guard_state.py). Dos
        # revisiones seguidas, para no reiniciarlo al volver de una suspensión.
        if ($vueltas % 20 -eq 0) {
            if (Agente-Congelado $vigilados) { $revisionesSinLatido++ } else { $revisionesSinLatido = 0 }
            if ($revisionesSinLatido -ge 2) {
                Log "El agente sigue vivo pero no responde hace más de $LimiteSinLatido s (congelado). Se reinicia; no es un ataque, no se aísla."
                foreach ($proceso in $vigilados.Values) {
                    try { if (-not $proceso.HasExited) { $proceso.Kill() } } catch { }
                }
                $reinicioPropio = $true
                break
            }
        }
        # El python.exe del .venv arranca el intérprete real como proceso hijo.
        if ($vueltas % 10 -eq 0) {
            foreach ($p in Buscar-Agente) {
                $id = [int]$p.ProcessId
                if (-not $vigilados.ContainsKey($id)) {
                    try { $vigilados[$id] = [Diagnostics.Process]::GetProcessById($id) } catch { }
                }
            }
        }
    }

    if ($reinicioPropio) {
        Start-Sleep -Seconds 2
        try { Start-ScheduledTask -TaskName "ALFA-Sentinel" -ErrorAction Stop; Log "Agente reiniciado." } catch { Log "No se pudo reiniciar el agente ($_)." }
        continue
    }

    if ([AlfaGuardian]::ShuttingDown()) { Log "El agente se detuvo porque Windows se está apagando."; exit 0 }

    $pidLimpio = 0
    try { $pidLimpio = [int]("$(Get-Content $MarcaLimpia -TotalCount 1 -ErrorAction Stop)".Trim()) } catch { }
    if ($pidLimpio -and $vigilados.ContainsKey($pidLimpio)) {
        Log "El agente se cerró de forma normal (PID $pidLimpio)."
        continue
    }

    # Segunda comprobación: el apagado pudo empezar un instante después.
    Start-Sleep -Milliseconds 1500
    if ([AlfaGuardian]::ShuttingDown()) { Log "El agente se detuvo porque Windows se está apagando."; exit 0 }

    Responder-Terminacion $cfg
    Start-Sleep -Seconds 3
}
