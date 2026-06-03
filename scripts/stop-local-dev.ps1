param(
    [string]$RedisContainerName = "devassist-redis",
    [switch]$Remove
)

$ErrorActionPreference = "Stop"

$DockerDesktopBin = "C:\Program Files\Docker\Docker\resources\bin"

if (Test-Path $DockerDesktopBin) {
    $env:Path = "$DockerDesktopBin;$env:Path"
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "Docker was not found. Nothing to stop."
    exit 0
}

$ContainerId = docker ps -aq --filter "name=^/${RedisContainerName}$"
if (-not $ContainerId) {
    Write-Host "Redis container '$RedisContainerName' was not found."
    exit 0
}

$IsRunning = docker inspect -f "{{.State.Running}}" $RedisContainerName
if ($IsRunning -eq "true") {
    docker stop $RedisContainerName | Out-Null
    Write-Host "Stopped Redis container '$RedisContainerName'."
}
else {
    Write-Host "Redis container '$RedisContainerName' is already stopped."
}

if ($Remove) {
    docker rm $RedisContainerName | Out-Null
    Write-Host "Removed Redis container '$RedisContainerName'."
}
