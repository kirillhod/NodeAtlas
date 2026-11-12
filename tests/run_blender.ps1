param(
    [Parameter(Mandatory = $true)][string]$Blender,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$TimeoutSec = 180,
    [switch]$Background
)

# Convenience wrapper for Windows: run one GUI test with a wall-clock limit and
# kill the process tree on timeout. The tests themselves do not depend on it.
$scriptPath = (Resolve-Path $Script).Path
$name = [IO.Path]::GetFileNameWithoutExtension($scriptPath)
$log = Join-Path $env:TEMP "nodeatlas-$name.log"
$errLog = "$log.err"
$arguments = @("--factory-startup", "--python", $scriptPath)
if ($Background) { $arguments = @("--background") + $arguments }

$proc = Start-Process -FilePath $Blender -ArgumentList $arguments -PassThru `
    -RedirectStandardOutput $log -RedirectStandardError $errLog
if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
    taskkill /T /F /PID $proc.Id 2>&1 | Out-Null
    Write-Output "TIMEOUT after ${TimeoutSec}s (killed); log: $log"
    Get-Content $log -Tail 20
    exit 124
}

$code = $proc.ExitCode
if ($null -eq $code) { $code = 0 }
Write-Output "DONE ($code); log: $log"
Get-Content $log -Tail 25
if ((Test-Path $errLog) -and (Get-Item $errLog).Length -gt 0) {
    Write-Output "STDERR"
    Get-Content $errLog -Tail 15
}
exit $code
