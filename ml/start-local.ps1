param(
    [int]$Port = 8090,
    [string]$DatasetPath = '',
    [string]$ForestPython = "$env:USERPROFILE\miniconda3\envs\forest_gpu\python.exe"
)
$ErrorActionPreference = 'Stop'
if (!(Test-Path -LiteralPath $ForestPython)) { throw 'forest_gpu environment not found. Specify -ForestPython with your GPU Python path.' }
Push-Location $PSScriptRoot
try {
    @'
import json, secrets
from pathlib import Path
p = Path('.ml-state/local-tokens.json')
p.parent.mkdir(exist_ok=True)
if not p.exists():
    p.write_text(json.dumps({'monitor': secrets.token_urlsafe(32), 'worker': secrets.token_urlsafe(32)}), encoding='utf-8')
    p.chmod(0o600)
'@ | & $ForestPython -
    if ($LASTEXITCODE -ne 0) { throw 'Could not initialize local credentials.' }
    $credentials = Get-Content -LiteralPath '.ml-state/local-tokens.json' -Raw | ConvertFrom-Json
    Set-Clipboard -Value $credentials.monitor
    Write-Host 'Monitor key copied. Paste it into the authentication field in the browser. Ctrl+C stops the app.'
    $workerArguments = @('-m','forest_ml.local','--port',"$Port",'--with-worker','--open-browser')
    if ($DatasetPath) { $workerArguments += @('--dataset',"fire-smoke=$DatasetPath") }
    & $ForestPython @workerArguments
} finally {
    Pop-Location
}
