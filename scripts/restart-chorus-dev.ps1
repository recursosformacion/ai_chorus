# restart-chorus-dev.ps1 — Reinicia el servicio Chorus y comprueba su sintaxis.
#
# Chorus NO tiene build de frontend: web/ son ficheros estaticos (HTML/CSS/JS
# sin React) que Apache sirve en http://chorus-app con Cache-Control: no-store,
# asi que los cambios de interfaz se ven recargando el navegador. Lo unico que
# requiere "compilacion" es Python: se comprueba con compileall.
#
# Qué hace:
#   1. Comprueba la sintaxis de Chorus con compileall (falla rápido si hay error).
#   2. Mata el proceso que escucha en el puerto 9600 (servicio chorus de dev).
#   3. Lo vuelve a arrancar con el mismo entorno que restart-dev.ps1
#      (CHORUS_CONFIG=osap.toml y CHORUS_DATABASE_URL del token de dev).
#   4. Espera a http://127.0.0.1:9600/health.
#
# No toca osap-api, ni Apache, ni la base de datos de pruebas (osap_chorus_test).
#
# ATENCION: Chorus NO aplica migraciones al arrancar (initialise_database sólo
# contempla 001 y 004-007). Para actualizar el esquema (dev/test/prod):
#   python scripts/upgrade_dev_db.py --env dev --verify-only
#   python scripts/upgrade_dev_db.py --env dev
#   python scripts/upgrade_dev_db.py --env dev --apply
#
# Uso:
#   pwsh scripts/restart-chorus-dev.ps1
#   pwsh scripts/restart-chorus-dev.ps1 -SkipCompile
#   pwsh scripts/restart-chorus-dev.ps1 -WaitSeconds 60
#   pwsh scripts/restart-chorus-dev.ps1 -NoWait

[CmdletBinding()]
param(
    [switch]$SkipCompile,
    [switch]$NoWait,
    [switch]$NoElevate,
    [string]$DatabaseUrl = "",
    [int]$Port = 9600,
    [int]$WaitSeconds = 60
)

$ErrorActionPreference = "Stop"

$RepoRoot   = Split-Path -Parent $PSScriptRoot
$LogDir     = Join-Path $env:LOCALAPPDATA "osap-dev\logs"
$TokenFile  = Join-Path $env:LOCALAPPDATA "osap-dev\chorus-db-url.txt"
$Health     = "http://127.0.0.1:$Port/health"

function Write-Step([string]$Message) {
    Write-Host ("[{0:HH:mm:ss}] {1}" -f (Get-Date), $Message)
}

function Test-Admin {
    $principal = [Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Resolve-Python {
    $venv = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) {
        & $venv -c "import sys" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $venv }
        Write-Host "  aviso: venv invalido en $RepoRoot (se usa Python del sistema)" -ForegroundColor DarkYellow
    }
    $candidates = @()
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }
    $py = & py -3.12 -c "import sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $py) { $candidates += $py }
    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) { return $c }
    }
    throw "No hay interprete Python valido para $RepoRoot"
}

function Get-PortPids([int]$TargetPort) {
    $found = @()
    $ErrorActionPreference = "SilentlyContinue"
    $found += (Get-NetTCPConnection -LocalPort $TargetPort -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess)
    $lines = netstat -ano | Select-String -Pattern ":$TargetPort\s+\S+\s+LISTENING"
    foreach ($line in $lines) { $found += [int](($line -split '\s+')[-1]) }
    $ErrorActionPreference = "Stop"
    return @($found | Where-Object { $_ -gt 0 } | Sort-Object -Unique)
}

function Wait-Health([string]$Url, [int]$Timeout) {
    $deadline = (Get-Date).AddSeconds($Timeout)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -Uri $Url -TimeoutSec 5 -SkipHttpErrorCheck -UseBasicParsing
            if ($r.StatusCode -ge 200 -and $r.StatusCode -lt 300) { return [int]$r.StatusCode }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $null
}

Write-Host "=== Chorus dev: recompilar y reiniciar ===" -ForegroundColor Cyan
$exitCode = 0

# ---------------------------------------------------------------- 1. Compilar
if ($SkipCompile) {
    Write-Host "[1/4] Compilacion omitida (-SkipCompile)" -ForegroundColor DarkGray
} else {
    $python = Resolve-Python
    Write-Step "[1/4] Comprobando sintaxis de Chorus con $([IO.Path]::GetFileName($python))..."
    & $python -m compileall -q -f (Join-Path $RepoRoot "app") (Join-Path $RepoRoot "scripts")
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: compileall ha fallado. No se reinicia el servicio." -ForegroundColor Red
        Write-Host "  Corrige los errores de sintaxis y vuelve a ejecutar." -ForegroundColor Yellow
        exit 1
    }
    Write-Host "  sintaxis OK" -ForegroundColor Green
}

# ---------------------------------------------------------------- 2. Matar
Write-Step "[2/4] Deteniendo el servicio chorus (puerto $Port)..."
$targets = New-Object System.Collections.Generic.HashSet[int]
foreach ($procId in (Get-PortPids $Port)) { [void]$targets.Add([int]$procId) }

# Procesos uvicorn de Chorus que no esten escuchando todavia
$stray = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | Where-Object {
    $_.CommandLine -and
    $_.CommandLine -match "(?i)uvicorn" -and
    $_.CommandLine -match "(?i)app\.main:app" -and
    $_.CommandLine -match "--port\s+$Port"
}
foreach ($p in $stray) { [void]$targets.Add([int]$p.ProcessId) }

if ($targets.Count -eq 0) {
    Write-Host "  (no habia proceso chorus activo)" -ForegroundColor DarkGray
} else {
    foreach ($procId in $targets) {
        if ($procId -eq $PID) { continue }
        $out = taskkill /PID $procId /T /F 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  matado PID $procId" -ForegroundColor DarkGray
        } elseif ($out -match "(?i)no se encontro|no se encontr|not found|unable to find") {
            # El puerto ya estaba liberado: el PID era obsoleto.
            Write-Host "  PID $procId ya no existe" -ForegroundColor DarkGray
        } else {
            Write-Host "  ERROR al matar PID $procId : $out" -ForegroundColor Yellow
            Write-Host "  Ejecuta el script como administrador o usa restart-dev.ps1." -ForegroundColor Yellow
            $exitCode = 1
        }
    }
    for ($i = 0; $i -lt 30; $i++) {
        if ((Get-PortPids $Port).Count -eq 0) { break }
        Start-Sleep -Milliseconds 500
    }
    if ((Get-PortPids $Port).Count -gt 0) {
        # El proceso esta elevado (lo arranco restart-dev.ps1): reintentar como admin.
        if (-not (Test-Admin) -and -not $NoElevate) {
            Write-Host "  El proceso esta elevado: se reintenta como administrador..." -ForegroundColor Yellow
            $relaunch = @(
                "-NoProfile", "-ExecutionPolicy", "Bypass", "-NoExit",
                "-File", "`"$PSCommandPath`"", "-NoElevate"
            )
            if ($SkipCompile) { $relaunch += "-SkipCompile" }
            if ($NoWait)      { $relaunch += "-NoWait" }
            if ($DatabaseUrl) { $relaunch += @("-DatabaseUrl", $DatabaseUrl) }
            $relaunch += @("-Port", "$Port")
            $relaunch += @("-WaitSeconds", "$WaitSeconds")
            Start-Process -FilePath "pwsh" -Verb RunAs -ArgumentList $relaunch
            exit 0
        }
        Write-Host "  ERROR: el puerto $Port sigue ocupado; no se puede arrancar Chorus." -ForegroundColor Red
        Write-Host "  Cierra el proceso o ejecuta restart-dev.ps1 como administrador." -ForegroundColor Yellow
        exit 1
    }
}

# ---------------------------------------------------------------- 3. Arrancar
Write-Step "[3/4] Arrancando chorus..."
$python = Resolve-Python

$chorusDbUrl = $DatabaseUrl
$chorusDbOrigin = "parametro -DatabaseUrl"
if (-not $chorusDbUrl) {
    $chorusDbOrigin = "token de dev ($TokenFile)"
    if (Test-Path -LiteralPath $TokenFile) {
        $chorusDbUrl = (Get-Content -LiteralPath $TokenFile -Raw).Trim()
    }
}
if (-not $chorusDbUrl) {
    Write-Host "  aviso: no hay CHORUS_DATABASE_URL en $TokenFile" -ForegroundColor Yellow
    Write-Host "  Chorus arrancara con la configuracion de osap.toml." -ForegroundColor Yellow
} else {
    Write-Host "  base de datos: $chorusDbUrl  (origen: $chorusDbOrigin)" -ForegroundColor DarkGray
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$env:CHORUS_CONFIG = "osap.toml"
$env:CHORUS_DATABASE_URL = $chorusDbUrl
try {
    Start-Process -FilePath $python `
        -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$Port") `
        -WorkingDirectory $RepoRoot -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $LogDir "chorus.out.log") `
        -RedirectStandardError  (Join-Path $LogDir "chorus.err.log")
    Write-Host "  uvicorn lanzado (pid del proceso en el log)" -ForegroundColor Green
} catch {
    Write-Host "  ERROR al arrancar chorus: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
} finally {
    Remove-Item -Path "Env:CHORUS_CONFIG" -ErrorAction SilentlyContinue
    Remove-Item -Path "Env:CHORUS_DATABASE_URL" -ErrorAction SilentlyContinue
}

# ---------------------------------------------------------------- 4. Healthcheck
if ($NoWait) {
    Write-Step "[4/4] Healthcheck omitido (-NoWait)"
    Write-Host ""
    Write-Host "Chorus arrancado en http://127.0.0.1:$Port" -ForegroundColor Cyan
    Write-Host "Web (frontend estatico via Apache): http://chorus-app" -ForegroundColor Cyan
    Write-Host "Logs: $LogDir" -ForegroundColor Cyan
    exit $exitCode
}

Write-Step "[4/4] Esperando $Health (hasta $WaitSeconds s)..."
$code = Wait-Health $Health $WaitSeconds
Write-Host ""
if ($code) {
    Write-Host "  OK chorus responde ($code)" -ForegroundColor Green
    Write-Host "API: http://127.0.0.1:$Port   (proxy Apache: http://chorus-app/api/)" -ForegroundColor Cyan
    Write-Host "Web: http://chorus-app   (frontend estatico, sin build)" -ForegroundColor Cyan
    Write-Host "Logs: $LogDir\chorus.out.log / chorus.err.log" -ForegroundColor Cyan
    exit $exitCode
}

Write-Host "  FALLO: chorus no responde en $Health" -ForegroundColor Red
Write-Host "  Revisa $LogDir\chorus.err.log" -ForegroundColor Yellow
exit 1