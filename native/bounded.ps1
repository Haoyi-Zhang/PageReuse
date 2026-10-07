param(
    [ValidateSet('Compile','Conformance','Measure')][string]$Mode = 'Conformance',
    [string]$OutDir = '',
    [string]$WorkRoot = '',
    [string]$Zig = '',
    [string]$ConformanceDir = '',
    [string]$SlotId = '',
    [int]$WallSeconds = 120,
    [int]$MemoryMiB = 1024
)
$ErrorActionPreference='Stop'
if ($WallSeconds -lt 1 -or $WallSeconds -gt 240 -or $MemoryMiB -lt 128 -or $MemoryMiB -gt 2048) { throw 'Invalid process limit' }
if ($Mode -eq 'Measure' -and [string]::IsNullOrWhiteSpace($SlotId)) { throw 'No coordinator slot: measurement is disabled' }
$artifact=Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($WorkRoot)) { $WorkRoot=Join-Path $artifact 'results/native-reproduction' }
$work=[IO.Path]::GetFullPath($WorkRoot)
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir=Join-Path $work $Mode.ToLowerInvariant() }
$resolved=[IO.Path]::GetFullPath($OutDir)
if (-not $resolved.StartsWith($work.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Output scope' }
New-Item -ItemType Directory -Path $work -Force | Out-Null
$tag=[IO.Path]::GetFileName($resolved.TrimEnd('\','/'))
$stdout=Join-Path $work ("$Mode.$tag.stdout.log")
$stderr=Join-Path $work ("$Mode.$tag.stderr.log")
$arguments=@('-NoLogo','-NoProfile','-File',('"'+(Join-Path $PSScriptRoot 'run.ps1')+'"'),'-Mode',$Mode,'-OutDir',('"'+$resolved+'"'),'-WorkRoot',('"'+$work+'"'))
if (-not [string]::IsNullOrWhiteSpace($Zig)) { $arguments+=@('-Zig',('"'+[IO.Path]::GetFullPath($Zig)+'"')) }
if (-not [string]::IsNullOrWhiteSpace($ConformanceDir)) { $arguments+=@('-ConformanceDir',('"'+[IO.Path]::GetFullPath($ConformanceDir)+'"')) }
if ($Mode -eq 'Measure') { $arguments+=@('-SlotId',('"'+$SlotId.Replace('"','')+'"')) }
$p=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    # One fixed logical CPU for comparable paired execution. No other chat is inspected.
    $p.ProcessorAffinity=[IntPtr]1
    $deadline=[DateTime]::UtcNow.AddSeconds($WallSeconds)
    while (-not $p.WaitForExit(250)) {
        $p.Refresh()
        if ($p.WorkingSet64 -gt [long]$MemoryMiB*1024*1024 -or [DateTime]::UtcNow -gt $deadline) {
            $p.Kill($true);throw 'Bounded process exceeded memory or wall limit; partial evidence retained'
        }
    }
    Get-Content -LiteralPath $stdout
    if ($p.ExitCode -ne 0) { Get-Content -LiteralPath $stderr;throw "Worker failed: $($p.ExitCode)" }
} finally { $p.Dispose() }
