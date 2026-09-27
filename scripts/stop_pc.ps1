# Stops the Blokus Arena container and removes it. Game history stays in data\.
# Usage: powershell -ExecutionPolicy Bypass -File scripts\stop_pc.ps1

$Container = 'blokus-arena'

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host 'Docker is not installed, so there is no container to stop.'
    exit 0
}
$null = docker info 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host 'Docker is not running, so there is no container to stop.'
    exit 0
}

$Existing = docker ps --all --quiet --filter ('name=^' + $Container + '$')
if ($Existing) {
    Write-Host "Stopping $Container..."
    docker stop $Container | Out-Null
    docker rm $Container | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Could not remove $Container." -ForegroundColor Red
        exit 1
    }
    Write-Host "Stopped $Container."
} else {
    Write-Host "$Container is not running."
}
exit 0
