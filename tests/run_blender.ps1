param(
    [Parameter(Mandatory = $true)][string]$Blender,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$TimeoutSec = 180,
    [switch]$Background,
    [switch]$UserConfig
)

# Convenience wrapper for Windows: run one GUI test with a wall-clock limit,
# kill the process tree on timeout and keep all Blender/test temp files in an
# isolated folder that is removed afterwards. The tests do not depend on it.
$scriptPath = (Resolve-Path $Script).Path
$name = [IO.Path]::GetFileNameWithoutExtension($scriptPath)
$blenderTag = Split-Path (Split-Path $Blender -Parent) -Leaf

$originalTemp = $env:TEMP
$logDir = Join-Path $originalTemp "nodeatlas_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "nodeatlas-$blenderTag-$name.log"
$errLog = "$log.err"

$runTemp = Join-Path $originalTemp ("nodeatlas_run_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $runTemp | Out-Null
$env:TEMP = $runTemp
$env:TMP = $runTemp
$env:TMPDIR = $runTemp

$arguments = @("--python", $scriptPath)
if (-not $UserConfig) { $arguments = @("--factory-startup") + $arguments }
if ($Background) { $arguments = @("--background") + $arguments }

$code = 0
try {
    $proc = Start-Process -FilePath $Blender -ArgumentList $arguments -PassThru `
        -RedirectStandardOutput $log -RedirectStandardError $errLog
    if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
        taskkill /T /F /PID $proc.Id 2>&1 | Out-Null
        Write-Output "TIMEOUT after ${TimeoutSec}s (killed); log: $log"
        Get-Content $log -Tail 20
        $code = 124
    } else {
        $code = $proc.ExitCode
        if ($null -eq $code) { $code = 0 }
        Write-Output "DONE ($code); log: $log"
        Get-Content $log -Tail 25
        if ((Test-Path $errLog) -and (Get-Item $errLog).Length -gt 0) {
            Write-Output "STDERR"
            Get-Content $errLog -Tail 15
        }
    }
} finally {
    $env:TEMP = $originalTemp
    $env:TMP = $originalTemp
    $env:TMPDIR = $originalTemp
    Remove-Item $runTemp -Recurse -Force -ErrorAction SilentlyContinue
}
exit $code
