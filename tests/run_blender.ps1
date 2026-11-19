param(
    [Parameter(Mandatory = $true)][string]$Blender,
    [Parameter(Mandatory = $true)][string]$Script,
    [int]$TimeoutSec = 180,
    [switch]$Background,
    [switch]$UserConfig,
    [switch]$SkipContentCheck,
    [switch]$KeepTemp
)

# Convenience wrapper for Windows: run one GUI test with a wall-clock limit,
# kill the process tree on timeout and keep all Blender/test temp files in an
# isolated folder that is removed afterwards. The tests do not depend on it.
#
# After a successful run the exported PNGs are sampled cheaply: a blank or
# single-colour image passes the size checks but is never a valid node capture,
# so the wrapper fails with exit code 2 when an output has almost no content.
function Test-PngContent {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][ref]$Messages
    )
    $files = @(
        Get-ChildItem -Path $Root -Recurse -File -Filter *.png -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -notlike '*.tmp.png' }
    )
    if ($files.Count -eq 0) { return $true }

    try {
        Add-Type -AssemblyName System.Drawing -ErrorAction Stop
    } catch {
        $Messages.Value += "CONTENT SKIP: System.Drawing is unavailable"
        return $true
    }

    $ok = $true
    foreach ($file in $files) {
        $bitmap = $null
        try {
            $bitmap = [System.Drawing.Bitmap]::new($file.FullName)
            $width = $bitmap.Width
            $height = $bitmap.Height
            $stepX = [Math]::Max(1, [int][Math]::Floor($width / 96))
            $stepY = [Math]::Max(1, [int][Math]::Floor($height / 96))
            $counts = @{}
            $total = 0
            for ($y = [int]($stepY / 2); $y -lt $height; $y += $stepY) {
                for ($x = [int]($stepX / 2); $x -lt $width; $x += $stepX) {
                    $color = $bitmap.GetPixel($x, $y).ToArgb() -band 0xFFFFFF
                    if ($counts.ContainsKey($color)) {
                        $counts[$color]++
                    } else {
                        $counts[$color] = 1
                    }
                    $total++
                }
            }
            if ($total -eq 0) {
                $Messages.Value += ("CONTENT FAIL: {0} has no samples" -f $file.Name)
                $ok = $false
                continue
            }
            $modal = ($counts.Values | Measure-Object -Maximum).Maximum
            $unique = $counts.Count
            $nonModal = 1.0 - ($modal / [double]$total)
            if ($unique -lt 8 -or $nonModal -lt 0.002) {
                $Messages.Value += ("CONTENT FAIL: {0} ({1}x{2}, unique={3}, non-modal={4:P2})" -f
                    $file.Name, $width, $height, $unique, $nonModal)
                $ok = $false
            }
        } catch {
            # Decoding is best-effort: a new Blender build may write a PNG
            # variant that System.Drawing cannot read. The test's own size
            # checks still run, so do not turn this into a hard failure.
            $Messages.Value += ("CONTENT SKIP: {0} ({1})" -f $file.Name, $_.Exception.Message)
        } finally {
            if ($null -ne $bitmap) { $bitmap.Dispose() }
        }
    }
    return $ok
}

$scriptPath = (Resolve-Path $Script).Path
$name = [IO.Path]::GetFileNameWithoutExtension($scriptPath)
$blenderTag = Split-Path (Split-Path $Blender -Parent) -Leaf

$originalTemp = $env:TEMP
$logDir = Join-Path $originalTemp "nodeatlas_logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "nodeatlas-$blenderTag-$name.log"
$errLog = "$log.err"

$runTemp = Join-Path $originalTemp ("na_" + [guid]::NewGuid().ToString("N").Substring(0, 8))
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
        if ($code -eq 0) {
            # Blender can exit 0 without running the test, for example when its
            # embedded Python fails to start. Require the test's own verdict.
            $verdict = Select-String -Path $log -Pattern 'ALL PASS|"result":\s*"PASS"' -Quiet
            if (-not $verdict) {
                Write-Output "NO PASS VERDICT (exit 0 without a test result)"
                Get-Content $log -Tail 20
                $code = 3
            }
        }
        if ($code -eq 0 -and -not $SkipContentCheck) {
            $contentMessages = @()
            $contentOk = Test-PngContent -Root $runTemp -Messages ([ref]$contentMessages)
            $contentMessages | ForEach-Object { Write-Output $_ }
            if (-not $contentOk) { $code = 2 }
        }
    }
} finally {
    $env:TEMP = $originalTemp
    $env:TMP = $originalTemp
    $env:TMPDIR = $originalTemp
    if ($KeepTemp) {
        Write-Output "TEMP=$runTemp"
    } else {
        Remove-Item $runTemp -Recurse -Force -ErrorAction SilentlyContinue
    }
}
exit $code
