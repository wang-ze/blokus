# Builds the Blokus Arena image and runs it in Docker at http://127.0.0.1:7870.
# A running Blokus Arena container is stopped first. Set BLOKUS_PORT to use another port.
# 7870 leaves Gradio's usual 7860 free for other apps and for `uv run blokus`.
# API keys are read from .env, and game history is kept in data\, both in the repository root.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\start_pc.ps1

$Root = Split-Path -Parent $PSScriptRoot
$Image = 'blokus-arena'
$Container = 'blokus-arena'
$Port = if ($env:BLOKUS_PORT) { $env:BLOKUS_PORT } else { '7870' }
$Url = "http://127.0.0.1:$Port"

function Stop-WithError([string]$Message) {
    Write-Host $Message -ForegroundColor Red
    exit 1
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Stop-WithError 'Docker is not installed. Install Docker Desktop, then try again.'
}
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'Docker is not running. Start Docker Desktop, then try again.'
}

& (Join-Path $PSScriptRoot 'stop_pc.ps1')
if ($LASTEXITCODE -ne 0) {
    Stop-WithError "Could not stop the running $Container container."
}

# Some Docker setups don't report a port that is already taken, and the app would then be
# unreachable while another program answers on its port. So check first.
if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
    Stop-WithError ("Port $Port is already in use by another program. Close it, or pick another " +
        "port: `$env:BLOKUS_PORT = '7871'; then run this script again.")
}

Write-Host "Building the $Image image..."
docker build --tag $Image $Root
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'The image did not build. See the messages above.'
}
# Each build leaves the previous image untagged, so remove those leftovers.
docker image prune --force --filter "label=org.opencontainers.image.title=$Image" | Out-Null

$Data = Join-Path $Root 'data'
New-Item -ItemType Directory -Force -Path $Data | Out-Null
$RunArgs = @(
    'run', '--detach',
    '--name', $Container,
    '--publish', "127.0.0.1:${Port}:7860",
    '--mount', "type=bind,source=$Data,target=/data",
    # LLM players can use an Ollama server running on this computer.
    '--add-host', 'host.docker.internal:host-gateway',
    '--env', 'OLLAMA_BASE_URL=http://host.docker.internal:11434/v1'
)
$EnvFile = Join-Path $Root '.env'
if (Test-Path -LiteralPath $EnvFile -PathType Leaf) {
    $RunArgs += @('--mount', "type=bind,source=$EnvFile,target=/app/.env,readonly")
} else {
    Write-Host 'No .env file, so LLM players can only use Ollama (see README.md).'
}
$RunArgs += $Image
docker @RunArgs | Out-Null
if ($LASTEXITCODE -ne 0) {
    Stop-WithError 'The container did not start. See the messages above.'
}

Write-Host "Starting $Container..."
for ($i = 0; $i -lt 60; $i++) {
    try {
        $null = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2
        Write-Host "Blokus Arena is running at $Url" -ForegroundColor Green
        Write-Host "Logs: docker logs --follow $Container"
        Write-Host 'Stop: powershell -ExecutionPolicy Bypass -File scripts\stop_pc.ps1'
        exit 0
    } catch {
        # Not answering yet.
    }
    $Running = docker inspect --format '{{.State.Running}}' $Container
    if ($Running -ne 'true') {
        docker logs $Container
        Stop-WithError 'The container stopped while starting. Its log is above.'
    }
    Start-Sleep -Seconds 1
}
Stop-WithError "Blokus Arena did not answer at $Url within 60 seconds. See: docker logs $Container"
