param(
    [string]$VpsHost = 'my-vps',
    [int]$LocalPort = 18790,
    [string]$DatasetPath = '',
    [string]$ForestPython = "$env:USERPROFILE\miniconda3\envs\forest_gpu\python.exe"
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $ForestPython)) { throw 'GPU Python not found. Specify -ForestPython.' }
if ($VpsHost -notmatch '^[a-zA-Z0-9_.-]+$' -or $LocalPort -lt 1024 -or $LocalPort -gt 65535) { throw 'Invalid SSH host or port.' }
Push-Location $PSScriptRoot
$forwardProcess = $null
try {
    if (!$DatasetPath) { $DatasetPath = Join-Path $PSScriptRoot 'datasets/fire-smoke-v1' }
    foreach ($split in @('train','val')) {
        foreach ($label in @('normal','fire','smoke')) {
            New-Item -ItemType Directory -Force -Path (Join-Path $DatasetPath "$split/$label") | Out-Null
        }
    }
    $DatasetPath = (Resolve-Path -LiteralPath $DatasetPath).Path
    # Credentials stay on the VPS. Only the existing SSH identity is used on the PC.
    & ssh $VpsHost 'systemctl --user is-active --quiet forest-ml-private-ssh || systemd-run --user --unit=forest-ml-private-ssh --property=Restart=on-failure --working-directory=/home/ubuntu/lab/forest_dcon2027/ml /usr/bin/python3 -m forest_ml.ssh_bridge --secret-file /home/ubuntu/lab/forest_dcon2027/.env.ml'
    if ($LASTEXITCODE -ne 0) { throw 'Could not start private VPS bridge.' }
    $alreadyForwarded = $false
    try {
        $health = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:$LocalPort/api/health" -TimeoutSec 2
        if ($health.Headers['X-FOREST-Transport'] -eq 'private-ssh') { $alreadyForwarded = $true }
        else { throw 'Port is used by another service. Choose -LocalPort.' }
    } catch [System.Net.WebException] { }
    if (!$alreadyForwarded) {
        $forwardArguments = @('-N','-o','ExitOnForwardFailure=yes','-L',"127.0.0.1:${LocalPort}:127.0.0.1:18090",$VpsHost)
        $forwardProcess = Start-Process -FilePath 'ssh.exe' -ArgumentList $forwardArguments -WindowStyle Hidden -PassThru
        Start-Sleep -Milliseconds 800
        if ($forwardProcess.HasExited) { throw 'SSH forwarding failed. Check authentication or choose another port.' }
    }
    Start-Process "http://127.0.0.1:$LocalPort/#training"
    Write-Host 'FOREST training monitor is open. Ctrl+C stops this worker and its SSH forward.'
    & $ForestPython -m forest_ml.worker --server "http://127.0.0.1:$LocalPort/api/ml" --worker-id forest-rtx5050 --ssh-session --dataset "fire-smoke-v1=$DatasetPath"
} finally {
    if ($forwardProcess -and !$forwardProcess.HasExited) { Stop-Process -Id $forwardProcess.Id }
    Pop-Location
}
