param(
    [Parameter(Mandatory = $true)][string]$Blender,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$TimeoutSec = 180,
    [int]$IdleSec = 0,
    [string]$LogDir = "D:\Temp\nodeatlas_logs",
    [switch]$Background
)

$ErrorActionPreference = "stop"
$scriptPath = (Resolve-Path $Script).Path
$blenderName = Split-Path (Split-Path $Blender -Parent) -Leaf
$testName = [IO.Path]::GetFileNameWithoutExtension($scriptPath)
$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null
$outLog = Join-Path $LogDir "$blenderName-$testName-$stamp.out.log"
$errLog = Join-Path $LogDir "$blenderName-$testName-$stamp.err.log"

$arguments = @("--factory-startup", "--python", $scriptPath)
if ($Background) { $arguments = @("--background") + $arguments }

$watch = [Diagnostics.Stopwatch]::StartNew()
$proc = Start-Process -FilePath $Blender -ArgumentList $arguments -PassThru `
    -RedirectStandardOutput $outLog -RedirectStandardError $errLog
$cpu = 0.0
$size = -1
$idleStart = $watch.Elapsed.TotalSeconds
$stalled = $false

while (-not $proc.HasExited) {
    Start-Sleep -Milliseconds 250
    $elapsed = $watch.Elapsed.TotalSeconds
    if ($elapsed -gt $TimeoutSec) { break }

    if ($IdleSec -gt 0) {
        try { $proc.Refresh() } catch { }
        $currentCpu = $proc.TotalProcessorTime.TotalSeconds
        $currentSize = (Get-Item $outLog -ErrorAction SilentlyContinue).Length
        if ([Math]::Abs($currentCpu - $cpu) -gt 0.25 -or $currentSize -ne $size) {
            $cpu = $currentCpu
            $size = $currentSize
            $idleStart = $elapsed
        } elseif (($elapsed - $idleStart) -gt $IdleSec) {
            $stalled = $true
            break
        }
    }
}

$elapsed = [int]$watch.Elapsed.TotalSeconds
if (-not $proc.HasExited) {
    taskkill /T /F /PID $proc.Id 2>&1 | Out-Null
    try { $proc.WaitForExit(10000) | Out-Null } catch { }
    $reason = if ($stalled) { "STALL (no CPU or output for ${IdleSec}s)" } else { "TIMEOUT (${TimeoutSec}s)" }
    Write-Output "RESULT $reason after ${elapsed}s"
    Write-Output "LOG $outLog"
    if (Test-Path $outLog) { Get-Content $outLog -Tail 20 }
    exit 124
}

Write-Output "RESULT EXIT $($proc.ExitCode) after ${elapsed}s"
Write-Output "LOG $outLog"
if (Test-Path $outLog) { Get-Content $outLog -Tail 25 }
if ((Test-Path $errLog) -and (Get-Item $errLog).Length -gt 0) {
    Write-Output "STDERR"
    Get-Content $errLog -Tail 15
}
exit $proc.ExitCode
