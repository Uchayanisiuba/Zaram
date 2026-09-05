# Start Zaram the way it actually runs.
#
# Replaces `npm run dev`, which launches the wrong things: `dev:desktop` starts
# `desktop/src/main/index.ts` — the parallel TypeScript tree `docs/RUNNING.md`
# marks unverified — rather than the `electron/main.js` that ships, and
# `dev:backend` starts a backend by hand, which then holds 8420 without the
# per-launch API secret that Electron mints. Everything 401s and it reads as a
# broken product.
#
# Order matters and is the whole point:
#   1. clear leftovers   — a stale tree from a previous session holds 8420
#   2. TabbyAPI          — an inference server Zaram discovers but never starts
#   3. Vite              — must be listening before Electron loads the renderer
#   4. Electron          — spawns its own backend and mints the secret
#
# Zaram does not launch inference servers, deliberately: an auto-started
# TabbyAPI claims ~9.5 GB the moment Zaram opens, and the residency budget has
# to stay the user's decision. This script is a *developer convenience* that
# does it explicitly, which is a different thing from the product doing it
# silently.

param(
    # Skip TabbyAPI and run Ollama-only. Useful when you want the card free.
    [switch]$NoTabby,
    # Where TabbyAPI lives. Override if yours is elsewhere.
    [string]$TabbyPath = "$env:USERPROFILE\tabbyAPI"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

function Test-Port([int]$Port) {
    $null -ne (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Port([int]$Port, [int]$TimeoutSeconds, [string]$What) {
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Port $Port) { Write-Host "  $What is up on $Port" -ForegroundColor Green; return $true }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "  $What did not come up on $Port within ${TimeoutSeconds}s" -ForegroundColor Yellow
    return $false
}

# --- 1. Leftovers ------------------------------------------------------------
#
# The failure this exists for: a 14-hour-old Electron tree from a previous
# session still running, its backend holding 8420 on the *system* Python. A new
# launch is dead on arrival and the error names something else entirely.
#
# Filtered by path, never by process name. The Claude desktop app is also
# Electron, and `Stop-Process -Name electron` would take it with them.

Write-Host "[1/4] Clearing leftovers" -ForegroundColor Cyan

$stale = Get-Process electron -ErrorAction SilentlyContinue |
    Where-Object { $_.Path -like "$RepoRoot\*" }
if ($stale) {
    Write-Host "  stopping $($stale.Count) stale Zaram Electron process(es)"
    $stale | Stop-Process -Force -ErrorAction SilentlyContinue
}

Get-NetTCPConnection -LocalPort 8420 -State Listen -ErrorAction SilentlyContinue | ForEach-Object {
    Write-Host "  freeing port 8420 (pid $($_.OwningProcess))"
    Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

# --- 2. TabbyAPI -------------------------------------------------------------
#
# Zaram probes 127.0.0.1:1234 for any OpenAI-compatible server. Not running is
# not an error — it means those models are genuinely unavailable, and Zaram is
# right to offer nothing from it. Started here so that is a choice rather than
# something you discover from a short model list.

Write-Host "[2/4] TabbyAPI" -ForegroundColor Cyan

if ($NoTabby) {
    Write-Host "  skipped (-NoTabby)"
} elseif (Test-Port 1234) {
    Write-Host "  already listening on 1234"
} elseif (Test-Path "$TabbyPath\start.bat") {
    Write-Host "  starting $TabbyPath\start.bat"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/c", "start.bat" -WorkingDirectory $TabbyPath
    # Not waited on. Loading an exl3 model takes far longer than Vite, and
    # Zaram rediscovers providers rather than snapshotting them at launch, so
    # blocking here would cost a minute for nothing.
    Write-Host "  launched (models appear once it finishes loading)"
} else {
    Write-Host "  not found at $TabbyPath — skipping. Ollama models still work." -ForegroundColor Yellow
}

# --- 3. Vite -----------------------------------------------------------------
#
# `--strictPort` on purpose: the backend's CORS allow-list names 5173 exactly,
# so a Vite that silently moved to 5174 produces a renderer that loads and can
# talk to nothing.

Write-Host "[3/4] Renderer" -ForegroundColor Cyan

if (Test-Port 5173) {
    Write-Host "  already listening on 5173"
} else {
    Write-Host "  starting vite"
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c", "npx vite --port 5173 --strictPort" `
        -WorkingDirectory "$RepoRoot\frontend"
    if (-not (Wait-Port 5173 60 "vite")) {
        Write-Host "Renderer did not start. Electron would load a blank window; stopping." -ForegroundColor Red
        exit 1
    }
}

# --- 4. Electron -------------------------------------------------------------
#
# Two environment details, both of which cost this repository a session:
#
# ELECTRON_RUN_AS_NODE is set by VSCode's own Electron host and inherited by
# every terminal it opens. Electron tests for the variable's *presence*, so it
# must be REMOVED — setting it to "" still re-execs as plain Node and fails
# with `Cannot read properties of undefined (reading 'isPackaged')`, an error
# that names a line in main.js and reads like a code bug.
#
# ZARAM_PYTHON is not optional. Unset, backendLauncher resolves `../.venv` —
# which exists, as a second complete environment — so you get a silently
# different interpreter rather than an error.

Write-Host "[4/4] Zaram" -ForegroundColor Cyan

Remove-Item Env:\ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
$env:ZARAM_PYTHON = "$RepoRoot\backend\venv\Scripts\python.exe"

if (-not (Test-Path $env:ZARAM_PYTHON)) {
    Write-Host "No interpreter at $env:ZARAM_PYTHON" -ForegroundColor Red
    exit 1
}

Write-Host "  python:   $env:ZARAM_PYTHON"
Write-Host "  electron: $RepoRoot\electron\main.js"
Write-Host ""
Write-Host "  Verify: curl http://127.0.0.1:8420/health should return 401." -ForegroundColor DarkGray
Write-Host "  A 401 is success — the per-launch secret is being enforced." -ForegroundColor DarkGray
Write-Host ""

Set-Location $RepoRoot
& "$RepoRoot\node_modules\.bin\electron.cmd" "electron\main.js"
