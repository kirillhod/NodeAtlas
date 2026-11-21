param(
    [Parameter(Mandatory = $true)][string[]]$Blender,
    [string]$Since,
    [string[]]$Files = @(),
    [switch]$DryRun,
    [switch]$IncludeArtifact,
    [int]$TimeoutSec = 180
)

# Run only the tests that the current diff can affect.
#
# The mapping lives in tests/affected.psd1: changed test files run themselves,
# changed node_atlas modules expand to feature groups, and a change that reaches
# 20 or more of the GUI tests runs the full tier instead of a near-full subset.
# The unit suite runs on the first Blender entry whenever package code changed.
#
#   powershell -File tests/run_affected.ps1 -Blender '5.3.0=C:\Blender\5.3\blender.exe'
#   powershell -File tests/run_affected.ps1 -Blender '5.3.0=...' -Since v1.5.0
#   powershell -File tests/run_affected.ps1 -Blender '5.3.0=...' -Files node_atlas/bounds.py -DryRun
#
# This is the iteration loop. The five-version full matrix stays the release
# check (AGENTS.md section 7, docs/agent/live-check.md).

$ErrorActionPreference = 'Stop'

$root = Split-Path $PSScriptRoot -Parent
$map = Import-PowerShellDataFile (Join-Path $PSScriptRoot 'affected.psd1')
$allTests = @($map.Groups.Values | ForEach-Object { $_ } | Sort-Object -Unique)

function Get-ChangedPaths {
    param([string]$Repository, [string]$SinceRef)

    if ($SinceRef) {
        $paths = @(& git -C $Repository diff --name-only $SinceRef --)
        if ($LASTEXITCODE -ne 0) { throw "git diff against '$SinceRef' failed" }
    } else {
        $paths = @()
    }

    $status = @(& git -C $Repository status --porcelain)
    if ($LASTEXITCODE -ne 0) { throw 'git status failed; run this inside the NodeAtlas repository' }
    foreach ($line in $status) {
        if ($line.Length -lt 4) { continue }
        $path = $line.Substring(3).Trim()
        if ($path -match ' -> ') { $path = ($path -split ' -> ')[-1] }
        $paths += $path.Trim('"')
    }

    return @($paths | Where-Object { $_ } | Sort-Object -Unique)
}

function ConvertTo-RepositoryPath {
    param([string]$Path, [string]$Repository)

    $normalized = ($Path -replace '\\', '/').Trim()
    if (-not $normalized) { return '' }
    if ([System.IO.Path]::IsPathRooted($normalized)) {
        $prefix = ($Repository -replace '\\', '/').TrimEnd('/') + '/'
        if (-not $normalized.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            return ''
        }
        $normalized = $normalized.Substring($prefix.Length)
    }
    return ($normalized -replace '^\./', '')
}

$fileArgs = @()
foreach ($item in $Files) {
    foreach ($part in ($item -split '[,;]')) {
        $part = $part.Trim()
        if ($part) { $fileArgs += $part }
    }
}

$paths = if ($fileArgs.Count) {
    @($fileArgs | ForEach-Object { ConvertTo-RepositoryPath $_ $root } | Where-Object { $_ })
} else {
    Get-ChangedPaths $root $Since
}
if (-not $paths.Count) {
    Write-Output 'No changed files in the working tree.'
    exit 0
}

$groups = @()
$tests = @()
$unit = $false
foreach ($path in $paths) {
    $p = ($path -replace '\\', '/')
    if ($p -like 'tests/gui/*.py') {
        $leaf = Split-Path $p -Leaf
        if ($leaf -eq 'png_content.py') {
            # Shared pixel checker: every capture test observes it.
            $groups += $map.Groups.Keys
        } else {
            $tests += $leaf
        }
        continue
    }
    if ($p -like 'tests/unit/*') { $unit = $true; continue }
    if ($p -like 'tests/fixtures/*') {
        $groups += $map.Groups.Keys
        $unit = $true
        continue
    }
    if ($map.Modules.ContainsKey($p)) {
        $unit = $true
        $groups += $map.Modules[$p]
        continue
    }
    if ($p -like 'node_atlas/*') {
        # New or renamed module: no rule yet, so be conservative.
        $unit = $true
        $groups += $map.Groups.Keys
        continue
    }
    # Docs, packaging and the test runners are not exercised by a GUI test.
}

$groups = @($groups | Sort-Object -Unique)
foreach ($group in $groups) { $tests += $map.Groups[$group] }
$tests = @($tests | Sort-Object -Unique)

Write-Output ("Changed ({0}): {1}" -f $paths.Count, ($paths -join ', '))
Write-Output ("Groups: {0}" -f $(if ($groups.Count) { $groups -join ', ' } else { 'none' }))
Write-Output ("Unit suite: {0}" -f $(if ($unit) { 'yes' } else { 'no' }))
Write-Output ("GUI tests: {0}/{1}" -f $tests.Count, $allTests.Count)
if ($tests.Count) { Write-Output ("  " + ($tests -join ', ')) }

if ($DryRun) { exit 0 }
if (-not $unit -and -not $tests.Count) {
    Write-Output 'Nothing to run.'
    exit 0
}

$entries = @()
foreach ($item in $Blender) {
    $entries += ($item -split ';')
}
$entries = @($entries | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if (-not $entries.Count) { throw 'Pass at least one Blender as version=path' }

$first = $entries[0]
$separator = $first.IndexOf('=')
if ($separator -lt 1) { throw "Pass each Blender as version=path, got: $first" }
$firstName = $first.Substring(0, $separator).Trim()
$firstExe = $first.Substring($separator + 1).Trim().Trim('"')

if ($unit) {
    Write-Output ''
    Write-Output ("Unit suite on {0}" -f $firstName)
    $unitArgs = @(
        '-NoProfile', '-File', (Join-Path $PSScriptRoot 'run_blender.ps1'),
        '-Blender', $firstExe,
        '-Script', (Join-Path $PSScriptRoot 'unit/test_core.py'),
        '-Background', '-TimeoutSec', $TimeoutSec
    )
    & powershell @unitArgs
    if ($LASTEXITCODE -ne 0) { exit 1 }
}

if (-not $tests.Count) { exit 0 }

$runFull = $tests.Count -ge 20
if ($runFull) {
    Write-Output ''
    Write-Output ("The change reaches {0} of {1} GUI tests; running the full tier instead." -f
        $tests.Count, $allTests.Count)
}

$matrixArgs = @(
    '-NoProfile', '-File', (Join-Path $PSScriptRoot 'run_matrix.ps1'),
    '-Tier', 'full',
    '-Blender', ($entries -join ';'),
    '-TimeoutSec', $TimeoutSec
)
if (-not $runFull) { $matrixArgs += @('-Only', ($tests -join ',')) }
if ($IncludeArtifact) { $matrixArgs += '-IncludeArtifact' }

& powershell @matrixArgs
exit $LASTEXITCODE
