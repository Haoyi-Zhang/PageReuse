param(
    [ValidateSet('Compile','Conformance','Measure')][string]$Mode = 'Conformance',
    [string]$OutDir = '',
    [string]$WorkRoot = '',
    [string]$Zig = '',
    [string]$ConformanceDir = '',
    [string]$SlotId = ''
)
$ErrorActionPreference = 'Stop'
$artifact = Split-Path -Parent $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($WorkRoot)) { $WorkRoot = Join-Path $artifact 'results/native-reproduction' }
$work = [IO.Path]::GetFullPath($WorkRoot)
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir = Join-Path $work $Mode.ToLowerInvariant() }
$out = [IO.Path]::GetFullPath($OutDir)
$allowed = $work.TrimEnd('\','/') + [IO.Path]::DirectorySeparatorChar
if (-not $out.StartsWith($allowed,[StringComparison]::OrdinalIgnoreCase)) { throw 'Output must remain inside the selected work root' }
if ($Mode -eq 'Measure' -and [string]::IsNullOrWhiteSpace($SlotId)) { throw 'Coordinator reserved-slot identifier is required; no measurements started' }
if (Test-Path -LiteralPath $out) { if ((Get-ChildItem -LiteralPath $out -Force).Count -ne 0) { throw 'Use a new empty output directory' } }
New-Item -ItemType Directory -Path $out -Force | Out-Null
$build = Join-Path $work 'build'
New-Item -ItemType Directory -Path $build -Force | Out-Null
$env:TEMP = Join-Path $build 'tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
if ([string]::IsNullOrWhiteSpace($Zig)) {
    $command=Get-Command zig -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw 'Specify -Zig or put the existing Zig compiler on PATH; no installation is performed' }
    $Zig=$command.Source
}
$zig = [IO.Path]::GetFullPath($Zig)
if (-not (Test-Path -LiteralPath $zig -PathType Leaf)) { throw 'Compiler does not exist' }
$library = Join-Path $build 'p054_allocator.dll'
$sources = @('allocator.cpp','NativeBridge.cs','run.ps1','bounded.ps1','check_native.py','summarize_native.py','protocol.json')
$hashes = @{}
foreach ($f in $sources) { $hashes[$f] = (Get-FileHash -LiteralPath (Join-Path $PSScriptRoot $f) -Algorithm SHA256).Hash }
if ($Mode -eq 'Compile') {
    $env:ZIG_LOCAL_CACHE_DIR = Join-Path $build 'local-cache'
    $env:ZIG_GLOBAL_CACHE_DIR = Join-Path $build 'global-cache'
    & $zig c++ -std=c++17 -O2 -Wall -Wextra -Werror -target x86_64-windows-gnu -shared (Join-Path $PSScriptRoot 'allocator.cpp') -o $library
    if ($LASTEXITCODE -ne 0) { throw "Native compiler failed: $LASTEXITCODE" }
    [IO.File]::WriteAllText((Join-Path $build 'compiled-source.json'),($hashes | ConvertTo-Json),[Text.UTF8Encoding]::new($false))
} else {
    if (-not (Test-Path -LiteralPath $library)) { throw 'Run bounded Compile first' }
    $compiled = Get-Content -LiteralPath (Join-Path $build 'compiled-source.json') -Raw | ConvertFrom-Json -AsHashtable
    if ($compiled['allocator.cpp'] -ne $hashes['allocator.cpp']) { throw 'Native source changed since compilation' }
}
# Add-Type uses already installed Roslyn; it installs nothing. All native loads are in the DLL.
Add-Type -Path (Join-Path $PSScriptRoot 'NativeBridge.cs') -CompilerOptions '/optimize+'
[P054Native.Bridge]::LoadNative($library)
$environment = [ordered]@{
    mode=$Mode; slot_id=$SlotId; os=[Runtime.InteropServices.RuntimeInformation]::OSDescription;
    architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
    dotnet=[Environment]::Version.ToString(); powershell=$PSVersionTable.PSVersion.ToString();
    compiler=(& $zig version | Out-String).Trim(); compiler_path=$zig;
    compiler_flags='c++ -std=c++17 -O2 -Wall -Wextra -Werror -target x86_64-windows-gnu -shared';
    processor=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    affinity=[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity.ToInt64();
    source_sha256=$hashes; library_sha256=(Get-FileHash -LiteralPath $library -Algorithm SHA256).Hash;
    original_input_sha256=(Get-FileHash -LiteralPath (Join-Path $artifact 'inputs/traces.jsonl')).Hash;
    original_certificate_sha256=(Get-FileHash -LiteralPath (Join-Path $artifact 'results/campaign/certificates.jsonl')).Hash;
    cpu_threads=1; performance_measurements_started=($Mode -eq 'Measure')
}
[IO.File]::WriteAllText((Join-Path $out 'environment.json'),($environment | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
if ($Mode -eq 'Conformance') { [P054Native.Bridge]::Conformance($artifact,$out) }
if ($Mode -eq 'Measure') {
    if ([string]::IsNullOrWhiteSpace($ConformanceDir)) { $ConformanceDir = Join-Path $work 'conformance' }
    $ready = Join-Path $ConformanceDir 'environment.json'
    $verified = Get-Content -LiteralPath $ready -Raw | ConvertFrom-Json -AsHashtable
    foreach ($f in $sources) { if ($verified.source_sha256[$f] -ne $hashes[$f]) { throw "Conformance must be rerun after changing $f" } }
    if ($verified.library_sha256 -ne $environment.library_sha256) { throw 'Binary differs from conformance binary' }
    $checks=Get-Content -LiteralPath (Join-Path $ConformanceDir 'independent-summary.json') -Raw | ConvertFrom-Json
    if ($checks.status -ne 'INDEPENDENT_CHECKS_PASSED') { throw 'Independent correctness gate missing' }
    [P054Native.Bridge]::Measure($artifact,$out)
}
Write-Output "$Mode completed. Performance measurements started: $($Mode -eq 'Measure')"
