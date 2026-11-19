param(
    [ValidateSet('smoke', 'full')][string]$Tier = 'smoke',
    [Parameter(Mandatory = $true)][string[]]$Blender,
    [int]$TimeoutSec = 180,
    [switch]$Parallel,
    [switch]$IncludeArtifact
)

# Tiered test matrix for Windows.
#
#   smoke  - the eight cheap cross-cutting tests (export, trees, texture,
#            selected, repeat, estimate, group, UI options). Use this after
#            every change.
#   full   - every source GUI test plus the 120 dpi and maximized variants.
#            Use this for a release and record the result in QA_REPORT.md.
#
# Each Blender is passed as "version=path". Separate entries with a semicolon
# so the command works through powershell.exe -File. Local paths stay in the
# shell:
#
#   powershell -File tests/run_matrix.ps1 -Tier smoke `
#     -Blender '4.2.23=C:\Blender\4.2\blender.exe;5.3.0=C:\Blender\5.3\blender.exe'
#
# -Parallel starts one child matrix per version. GUI windows overlap, so treat
# the first parallel run as an experiment and keep the content check enabled.
# -IncludeArtifact runs test_artifact.py without --factory-startup against the
# current profile; set BLENDER_USER_* to an isolated profile first. It cannot
# run in parallel because all versions would share that profile.

$ErrorActionPreference = 'Stop'

$runner = Join-Path $PSScriptRoot 'run_blender.ps1'
$guiDir = Join-Path $PSScriptRoot 'gui'

function New-Case {
    param(
        [string]$Script,
        [string]$Label = $Script,
        [hashtable]$Env = @{},
        [switch]$UserConfig
    )
    [pscustomobject]@{
        Script = $Script
        Label = $Label
        Env = $Env
        UserConfig = [bool]$UserConfig
    }
}

$smokeNames = @(
    'test_export.py',
    'test_trees.py',
    'test_texture.py',
    'test_selected.py',
    'test_repeat.py',
    'test_estimate.py',
    'test_group.py',
    'test_ui_options.py'
)

$fullNames = @(
    'test_export.py',
    'test_legacy.py',
    'test_selected.py',
    'test_selected_comp.py',
    'test_trees.py',
    'test_texture.py',
    'test_repeat.py',
    'test_cancel.py',
    'test_fail.py',
    'test_large.py',
    'test_maxmp.py',
    'test_density.py',
    'test_scaling.py',
    'test_extreme.py',
    'test_multiarea.py',
    'test_multiwindow.py',
    'test_1000.py',
    'test_limits.py',
    'test_readonly.py',
    'test_diskfull.py',
    'test_arealost.py',
    'test_estimate.py',
    'test_estimate_selected.py',
    'test_group.py',
    'test_ui_options.py',
    'test_boost.py',
    'test_naming.py',
    'test_clipboard.py',
    'test_path.py'
)

$cases = @()
$names = if ($Tier -eq 'smoke') { $smokeNames } else { $fullNames }
foreach ($name in $names) {
    $cases += New-Case -Script $name
}
if ($Tier -eq 'full') {
    $cases += New-Case -Script 'test_1000.py' -Label 'test_1000.py @120' -Env @{ NODEATLAS_TEST_DPI = '120' }
    $cases += New-Case -Script 'test_group.py' -Label 'test_group.py @max' -Env @{ NODEATLAS_TEST_MAXIMIZE = '1' }
}
if ($IncludeArtifact) {
    $cases += New-Case -Script 'test_artifact.py' -Label 'test_artifact.py (installed)' -UserConfig
}

$versions = @()
$entries = @()
foreach ($item in $Blender) {
    $entries += ($item -split ';')
}
foreach ($entry in $entries) {
    $entry = $entry.Trim()
    if (-not $entry) { continue }
    $separator = $entry.IndexOf('=')
    if ($separator -lt 1) {
        throw "Pass each Blender as version=path, got: $entry"
    }
    $name = $entry.Substring(0, $separator).Trim()
    $exe = $entry.Substring($separator + 1).Trim().Trim('"')
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "Blender not found: $exe"
    }
    $versions += [pscustomobject]@{ Version = $name; Exe = (Resolve-Path -LiteralPath $exe).Path }
}

# Fail before a 29-case run when a portable build has lost its Python stdlib.
# Blender can exit 0 in that state, so the per-test verdict check alone would
# only report the noise after every case.
foreach ($version in $versions) {
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $probe = & $version.Exe --background --factory-startup `
            --python-expr "import sys; print('PY_OK', sys.version.split()[0])" 2>&1 | Out-String
        $probeCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousPreference
    }
    if ($probeCode -ne 0 -or $probe -notmatch 'PY_OK') {
        $tail = ($probe -split "`r?`n" | Select-Object -Last 8) -join "`n"
        throw "Blender $($version.Version) cannot start Python: $($version.Exe)`n$tail"
    }
}

function Invoke-Case {
    param($Version, $Exe, $Case, [int]$TimeoutSec)

    $arguments = @(
        '-NoProfile',
        '-File', $runner,
        '-Blender', $Exe,
        '-Script', (Join-Path $guiDir $Case.Script),
        '-TimeoutSec', $TimeoutSec
    )
    if ($Case.UserConfig) { $arguments += '-UserConfig' }

    $saved = @{}
    foreach ($key in $Case.Env.Keys) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $Case.Env[$key], 'Process')
    }

    $watch = [Diagnostics.Stopwatch]::StartNew()
    try {
        $output = & powershell @arguments 2>&1 | Out-String
        $exitCode = $LASTEXITCODE
    } finally {
        $watch.Stop()
        foreach ($key in $saved.Keys) {
            [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process')
        }
    }

    $seconds = [Math]::Round($watch.Elapsed.TotalSeconds, 1)
    $ok = ($exitCode -eq 0) -and ($output -match 'DONE \(0\)')
    [pscustomobject]@{
        Version = $Version
        Test = $Case.Label
        Ok = $ok
        Exit = $exitCode
        Seconds = $seconds
        Output = $output
    }
}

function Write-CaseResult {
    param($Result)
    $mark = if ($Result.Ok) { 'PASS' } else { 'FAIL' }
    Write-Output ("{0} {1}: {2} ({3}s, exit {4})" -f
        $Result.Version, $Result.Test, $mark, $Result.Seconds, $Result.Exit)
    if (-not $Result.Ok) {
        $tail = ($Result.Output -split "`r?`n" |
            Where-Object { $_ -match 'FAIL|CONTENT|TIMEOUT|Traceback|Error' } |
            Select-Object -Last 6) -join "`n"
        if ($tail) { Write-Output $tail }
    }
}

if ($Parallel) {
    if ($IncludeArtifact) {
        throw '-IncludeArtifact needs the current profile, so it cannot run with -Parallel.'
    }
    if ($versions.Count -lt 2) {
        throw '-Parallel needs at least two Blender entries.'
    }

    Write-Output ("Parallel {0} matrix: {1} versions, {2} cases each" -f
        $Tier, $versions.Count, $cases.Count)
    $jobs = foreach ($version in $versions) {
        Start-Job -ArgumentList $PSCommandPath, $Tier, $version.Version, $version.Exe, $TimeoutSec -ScriptBlock {
            param($Script, $Tier, $Name, $Exe, $TimeoutSec)
            $output = & powershell -NoProfile -File $Script -Tier $Tier `
                -Blender "$Name=$Exe" -TimeoutSec $TimeoutSec 2>&1 | Out-String
            [pscustomobject]@{
                Version = $Name
                Exit = $LASTEXITCODE
                Output = $output
            }
        }
    }

    $jobs | Wait-Job | Out-Null
    $results = @()
    foreach ($job in $jobs) {
        $result = Receive-Job -Job $job
        Write-Output $result.Output
        $results += $result
        Remove-Job -Job $job
    }

    $failed = @($results | Where-Object { $_.Exit -ne 0 })
    Write-Output ''
    if ($failed.Count) {
        Write-Output ("Parallel {0} matrix FAILED: {1}/{2} versions" -f
            $Tier, $failed.Count, $results.Count)
        $failed | ForEach-Object { Write-Output ("  {0}: exit {1}" -f $_.Version, $_.Exit) }
        exit 1
    }
    Write-Output ("Parallel {0} matrix PASSED: {1}/{1} versions" -f $Tier, $results.Count)
    exit 0
}

$results = @()
foreach ($version in $versions) {
    foreach ($case in $cases) {
        $result = Invoke-Case -Version $version.Version -Exe $version.Exe `
            -Case $case -TimeoutSec $TimeoutSec
        Write-CaseResult -Result $result
        $results += $result
    }
}

$failed = @($results | Where-Object { -not $_.Ok })
Write-Output ''
Write-Output ("{0} matrix summary: {1}/{2} passed" -f
    $Tier, ($results.Count - $failed.Count), $results.Count)
$results |
    Group-Object Version |
    ForEach-Object {
        $bad = @($_.Group | Where-Object { -not $_.Ok }).Count
        Write-Output ("  {0}: {1}/{2} passed" -f $_.Name, ($_.Count - $bad), $_.Count)
    }
if ($failed.Count) {
    Write-Output 'Failed cases:'
    $failed | ForEach-Object { Write-Output ("  {0} {1} (exit {2})" -f $_.Version, $_.Test, $_.Exit) }
    exit 1
}
exit 0
