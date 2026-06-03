param(
    [string]$KubernetesContext = "docker-desktop",
    [string]$RedisContainerName = "devassist-redis",
    [int]$RedisPort = 6379,
    [int]$ApiPort = 8000,
    [switch]$SkipRedis
)

$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$DockerDesktopBin = "C:\Program Files\Docker\Docker\resources\bin"

if (Test-Path $DockerDesktopBin) {
    $env:Path = "$DockerDesktopBin;$env:Path"
}

function Require-Command {
    param(
        [string]$Name,
        [string]$Help
    )

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. $Help"
    }
}

if (-not $SkipRedis) {
    Require-Command "docker" "Install Docker Desktop or add Docker to PATH."

    $ContainerId = docker ps -aq --filter "name=^/${RedisContainerName}$"
    if ($ContainerId) {
        $IsRunning = docker inspect -f "{{.State.Running}}" $RedisContainerName
        if ($IsRunning -ne "true") {
            docker start $RedisContainerName | Out-Null
        }
    }
    else {
        docker run -d --name $RedisContainerName -p "${RedisPort}:6379" redis:7 | Out-Null
    }
}

$ApiPath = Join-Path $RepoRoot "apps\api"
$CorePath = Join-Path $RepoRoot "packages\core"

if ($env:PYTHONPATH) {
    $env:PYTHONPATH = "$ApiPath;$CorePath;$env:PYTHONPATH"
}
else {
    $env:PYTHONPATH = "$ApiPath;$CorePath"
}

$env:DEVASSIST_EXECUTION_ENABLED = "true"
$env:REDIS_URL = "redis://localhost:${RedisPort}/0"
$env:KUBERNETES_CONFIG_MODE = "auto"
$env:KUBERNETES_CONTEXT = $KubernetesContext

Write-Host "Starting DevAssist API on http://127.0.0.1:$ApiPort"
Write-Host "Redis URL: $env:REDIS_URL"
Write-Host "Kubernetes context: $env:KUBERNETES_CONTEXT"
Write-Host "Press Ctrl+C to stop the API. Run scripts/stop-local-dev.ps1 to stop Redis."

python -m uvicorn devassist_api.main:app --reload --host 127.0.0.1 --port $ApiPort
