#Requires -Version 5.1
<#
.SYNOPSIS
  Start a usable local Vakeel-Sahayak.ai stack on Windows (Docker Desktop). The Windows twin of install.sh.

.DESCRIPTION
  Checks that Docker Desktop is installed and running, that there is free disk and that the configured localhost ports
  (FRONTEND_PORT, default 3000; BACKEND_PORT, default 8000) are free; reports an NVIDIA GPU if there is one; creates the
  untracked .env from .env.example when it is missing (no key is ever printed); seeds Docker's persistent data volume
  from the local team data bundle; starts the offline stack with `docker compose up -d`; and ends with the URL and a plain
  list of what is missing.

  `make data` and `make models` are bash and make targets. They do not run in Windows PowerShell: run them in WSL (or
  pass -UseWsl and this script runs `make setup` and `make data` there for you), then run this script again.

  The default never enables an external provider and never reads a secret from .env.

.PARAMETER SkipData
  Do not look for or seed the stores. Use only to inspect the empty API and UI.

.PARAMETER Real
  Start the separate NVIDIA/vLLM profile (http://127.0.0.1:3001 by default). Needs an NVIDIA GPU with WSL 2 GPU support.

.PARAMETER NoStart
  Run the checks and data setup, but start no containers.

.PARAMETER UseWsl
  When the team data bundle is missing, run `make setup` and `make data` inside WSL on this same checkout.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\install.ps1 -UseWsl
#>
[CmdletBinding()]
param(
    [switch]$SkipData,
    [switch]$Real,
    [switch]$NoStart,
    [switch]$UseWsl,
    [switch]$Help
)

Set-StrictMode -Version 2.0
# Native commands (docker, wsl, nvidia-smi) write progress to stderr; Windows PowerShell 5.1 turns redirected stderr into
# errors, so failures are detected from $LASTEXITCODE instead of from $ErrorActionPreference.
$ErrorActionPreference = 'Continue'

$Root = $PSScriptRoot
Set-Location -LiteralPath $Root
$Missing = New-Object System.Collections.Generic.List[string]

function Show-Usage {
    Write-Host 'Usage: powershell -ExecutionPolicy Bypass -File .\install.ps1 [-SkipData] [-Real] [-NoStart] [-UseWsl] [-Help]'
    Write-Host ''
    Write-Host 'Checks Docker Desktop, free disk and the configured localhost ports; creates .env from .env.example if it is'
    Write-Host 'missing; seeds the persistent Docker data volume from the team data bundle; then starts the offline stack at'
    Write-Host 'http://127.0.0.1:3000 (FRONTEND_PORT in .env) and lists what is missing.'
    Write-Host ''
    Write-Host '-SkipData  Do not look for or seed the stores. Use only to inspect the empty API and UI.'
    Write-Host '-Real      Start the separate NVIDIA/vLLM profile (http://127.0.0.1:3001).'
    Write-Host '-NoStart   Run the checks and data setup, but start no containers.'
    Write-Host '-UseWsl    If the data bundle is missing, run "make setup" and "make data" in WSL on this checkout.'
}

function Stop-Install([string]$Message) {
    Write-Host "error: $Message" -ForegroundColor Red
    exit 1
}

function Show-Missing {
    Write-Host ''
    if ($Missing.Count -eq 0) {
        Write-Host 'Nothing is missing.'
        return
    }
    Write-Host 'What is missing:'
    foreach ($item in $Missing) {
        Write-Host "  - $item"
    }
}

# A value from the untracked .env (ports only; never a key), else the fallback.
function Get-EnvValue([string]$Key, [string]$Fallback) {
    $value = ''
    $envFile = Join-Path $Root '.env'
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in Get-Content -LiteralPath $envFile) {
            if ($line -match ('^\s*' + [regex]::Escape($Key) + '=([^#\s]+)')) {
                $value = $Matches[1].Trim('"', "'")
            }
        }
    }
    if ([string]::IsNullOrEmpty($value)) { return $Fallback }
    return $value
}

function Test-PortBusy([int]$Port) {
    if (Get-Command Get-NetTCPConnection -ErrorAction SilentlyContinue) {
        $listening = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
        return [bool]$listening
    }
    $listener = $null
    try {
        $listener = New-Object System.Net.Sockets.TcpListener ([System.Net.IPAddress]::Loopback, $Port)
        $listener.Start()
        return $false
    } catch {
        return $true
    } finally {
        if ($null -ne $listener) { $listener.Stop() }
    }
}

function Get-FreeGb([string]$Path) {
    try {
        $drive = New-Object System.IO.DriveInfo ([System.IO.Path]::GetPathRoot($Path))
        return [math]::Floor($drive.AvailableFreeSpace / 1GB)
    } catch {
        return $null
    }
}

# C:\Users\me\repo -> /mnt/c/Users/me/repo (the default WSL mount of a Windows drive).
function ConvertTo-WslPath([string]$Path) {
    $full = [System.IO.Path]::GetFullPath($Path)
    if ($full -notmatch '^([A-Za-z]):\\(.*)$') { return $null }
    return '/mnt/' + $Matches[1].ToLower() + '/' + ($Matches[2] -replace '\\', '/')
}

if ($Help) {
    Show-Usage
    exit 0
}

# ---------------------------------------------------------------- Docker
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-Install 'Docker is not installed. Install Docker Desktop for Windows with the WSL 2 backend (https://docs.docker.com/desktop/setup/install/windows-install/), start it, then run this script again.'
}
$null = & docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-Install 'Docker Compose v2 is required. Update Docker Desktop (it ships "docker compose").'
}
$null = & docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-Install 'Docker is installed but not running. Start Docker Desktop, wait until it shows "Engine running", then run this script again.'
}
Write-Host 'Docker Desktop is installed and running.'

# ---------------------------------------------------------------- free disk
$minGb = 8
if ($env:VS_INSTALL_MIN_FREE_GB) { $minGb = [int]$env:VS_INSTALL_MIN_FREE_GB }
# The checkout's drive holds the data bundle; Docker Desktop keeps images and volumes on the system drive by default.
$drives = @($Root)
if ($env:SystemDrive) { $drives += ($env:SystemDrive + '\') }
foreach ($path in $drives) {
    $freeGb = Get-FreeGb $path
    if ($null -eq $freeGb) {
        Write-Host "could not read the free space of $path; make sure at least $minGb GB are free." -ForegroundColor Yellow
        continue
    }
    if ($freeGb -lt $minGb) {
        Stop-Install "only $freeGb GB free on $([System.IO.Path]::GetPathRoot($path)); need at least $minGb GB for images, the data volume and case files. Free disk space, or set VS_INSTALL_MIN_FREE_GB only if you understand the reduced safety margin."
    }
}

# ---------------------------------------------------------------- .env
$envFile = Join-Path $Root '.env'
$envExample = Join-Path $Root '.env.example'
if (-not (Test-Path -LiteralPath $envFile) -and (Test-Path -LiteralPath $envExample)) {
    Copy-Item -LiteralPath $envExample -Destination $envFile
    Write-Host 'created the untracked .env from .env.example (external services stay off; add keys there only if you turn one on).'
}

# ---------------------------------------------------------------- ports
$frontendPort = Get-EnvValue 'FRONTEND_PORT' '3000'
$backendPort = Get-EnvValue 'BACKEND_PORT' '8000'
$existingBackend = (& docker compose ps -q backend 2>$null | Out-String).Trim()
foreach ($port in @($frontendPort, $backendPort)) {
    if (Test-PortBusy ([int]$port)) {
        if ([string]::IsNullOrEmpty($existingBackend)) {
            Stop-Install "port $port is already in use. Stop the program that uses it, or set FRONTEND_PORT / BACKEND_PORT in .env, then run this script again."
        }
        Write-Host "port $port is already used by the existing Compose stack; it will be reused."
    }
}

# ---------------------------------------------------------------- GPU (optional)
$gpu = ''
if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
    $names = & nvidia-smi --query-gpu=name --format=csv,noheader 2>$null
    if ($LASTEXITCODE -eq 0 -and $names) { $gpu = (@($names)[0]).Trim() }
}
if ($gpu) {
    Write-Host "NVIDIA GPU detected: $gpu"
} elseif ($Real) {
    Stop-Install 'no NVIDIA GPU found (nvidia-smi). The -Real profile needs an NVIDIA GPU, a current NVIDIA Windows driver and Docker Desktop with the WSL 2 backend.'
} else {
    Write-Host 'no NVIDIA GPU found; the offline stack does not need one.'
    $Missing.Add('(optional) an NVIDIA GPU: without one the -Real model profile cannot start; the offline stack works.')
}

# ---------------------------------------------------------------- data
$hostData = Join-Path $Root 'data'
if ($env:VS_DATA_DIR) { $hostData = $env:VS_DATA_DIR }
$statutes = Join-Path $hostData 'stores\law\statutes.sqlite'

function Test-Stores {
    if (-not (Test-Path -LiteralPath $statutes)) { return $false }
    return ((Get-Item -LiteralPath $statutes).Length -gt 0)
}

$wslRoot = ConvertTo-WslPath $Root
if (-not $SkipData -and -not (Test-Stores)) {
    $crlf = $false
    $probe = Join-Path $Root 'scripts\data_ensure.sh'
    if (Test-Path -LiteralPath $probe) { $crlf = (Get-Content -LiteralPath $probe -Raw).Contains("`r`n") }
    if ($crlf) {
        Write-Host 'the bash scripts in this checkout have Windows line endings, so "make data" fails in WSL. Clone again with "git config --global core.autocrlf false" (or clone inside WSL).' -ForegroundColor Yellow
    }
    if ($UseWsl -and (Get-Command wsl -ErrorAction SilentlyContinue) -and $wslRoot -and -not $crlf) {
        Write-Host 'the team data bundle is missing; running "make setup" and "make data" in WSL (needs HF_TOKEN in .env or "hf auth login" in WSL, Python 3.11+ and make) ...'
        & wsl -e bash -lc "set -e; cd '$wslRoot'; make setup; make data"
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'make setup / make data failed in WSL; see the messages above.' -ForegroundColor Yellow
        }
    }
    if (-not (Test-Stores)) {
        Write-Host 'the team data bundle (stores) is missing; the stack will start, but it cannot work on a case until the data is installed.' -ForegroundColor Yellow
        $where = '<this folder>'
        if ($wslRoot) { $where = $wslRoot }
        $Missing.Add("the team data bundle (stores, about 1 GB): open WSL (Ubuntu), run  cd '$where'  then  make setup  then  make data  (needs HF_TOKEN in .env or 'hf auth login', and read access to the Vakeel-Sahayak Hugging Face organisation); then run this script again. Or run this script with -UseWsl.")
    }
}
if ($SkipData) {
    $Missing.Add('the stores were not checked or seeded (-SkipData): the API and UI start empty.')
}

$modelsDir = Join-Path $Root 'models\hf'
if (-not (Test-Path -LiteralPath $modelsDir)) {
    $Missing.Add('(optional) helper model weights (BGE-M3, DeBERTa NLI, MiniCheck, Whisper; about 5.5 GB) for real-model runs outside Docker: run  make models  in WSL. The offline stack does not need them.')
}

if ($NoStart) {
    Write-Host 'checks complete; no containers started (-NoStart).'
    Show-Missing
    exit 0
}

# ---------------------------------------------------------------- start
if ($Real) {
    & docker compose --profile real up -d --build --wait vllm backend-real frontend-real
    if ($LASTEXITCODE -ne 0) {
        Stop-Install 'the real profile did not start; see the messages above, or run: docker compose --profile real logs vllm backend-real'
    }
    Write-Host "Vakeel-Sahayak.ai real profile is ready at http://127.0.0.1:$(Get-EnvValue 'FRONTEND_REAL_PORT' '3001')"
    Show-Missing
    exit 0
}

& docker compose up -d --build --wait
if ($LASTEXITCODE -ne 0) {
    Stop-Install 'the stack did not start; see the messages above, or run: docker compose logs backend frontend'
}

$volume = ''
if (-not $SkipData -and (Test-Stores)) {
    $backendId = (& docker compose ps -q backend 2>$null | Out-String).Trim()
    $mountsJson = (& docker inspect --format '{{json .Mounts}}' $backendId 2>$null | Out-String).Trim()
    if ($mountsJson) {
        # Assign first: Windows PowerShell 5.1 emits a JSON array as one object, and foreach over the variable enumerates it.
        $mounts = $mountsJson | ConvertFrom-Json
        foreach ($mount in $mounts) {
            if ($mount.Destination -eq '/app/data') { $volume = [string]$mount.Name }
        }
    }
    if ([string]::IsNullOrEmpty($volume)) {
        Stop-Install 'could not find the backend data volume (docker inspect).'
    }
    $null = & docker run --rm -v "${volume}:/target" alpine sh -c 'test -s /target/stores/law/statutes.sqlite' 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "seeding the persistent Docker volume from $hostData ..."
        & docker run --rm -u 0 -v "${volume}:/target" --mount "type=bind,source=$hostData,target=/source,readonly" alpine sh -c 'for d in interim stores testsets gaps eval; do if [ -e /source/$d ]; then cp -a /source/$d /target/; fi; done; chown -R 10001:10001 /target'
        if ($LASTEXITCODE -ne 0) {
            Stop-Install "seeding the data volume from $hostData failed; see the messages above."
        }
        & docker compose restart backend frontend
    }
}

Write-Host ''
Write-Host "Vakeel-Sahayak.ai is ready at http://127.0.0.1:$frontendPort"
if ($volume) {
    Write-Host "Persistent cases are in Docker volume '$volume'. Stop with: docker compose down (do not add -v unless you mean to erase cases)."
}
Show-Missing
