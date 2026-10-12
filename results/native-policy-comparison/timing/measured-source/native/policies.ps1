param(
    [Parameter(Mandatory=$true)][string]$Library,
    [Parameter(Mandatory=$true)][string]$BuildEnvironment,
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [string]$OutDir='',
    [int]$WallSeconds=120,
    [int]$MemoryMiB=1024,
    [switch]$Worker
)
# Functional only: deliberately no measurement branch or performance timer.
$ErrorActionPreference='Stop'
$artifact=Split-Path -Parent $PSScriptRoot
$results=[IO.Path]::GetFullPath((Join-Path $artifact 'results/native-policy-comparison'))
if ([string]::IsNullOrWhiteSpace($OutDir)) { $OutDir=$results }
$out=[IO.Path]::GetFullPath($OutDir)
$work=[IO.Path]::GetFullPath($WorkRoot)
$artifactPath=[IO.Path]::GetFullPath($artifact).TrimEnd('\','/')
$artifactPrefix=$artifactPath+[IO.Path]::DirectorySeparatorChar
if (-not $out.Equals($results,[StringComparison]::OrdinalIgnoreCase) -and
    ($out.Equals($artifactPath,[StringComparison]::OrdinalIgnoreCase) -or $out.StartsWith($artifactPrefix,[StringComparison]::OrdinalIgnoreCase))) { throw 'Use the stable public result directory or an explicit private reproduction directory (such as RUNNER_TEMP)' }
foreach ($privatePath in @($work,[IO.Path]::GetFullPath($Library),[IO.Path]::GetFullPath($BuildEnvironment))) {
    if ($privatePath.Equals($artifactPath,[StringComparison]::OrdinalIgnoreCase) -or $privatePath.StartsWith($artifactPrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Build/runtime files must remain outside the artifact-root repository' }
}
if ($WallSeconds -lt 1 -or $WallSeconds -gt 240 -or $MemoryMiB -lt 128 -or $MemoryMiB -gt 2048) { throw 'Invalid worker limits' }
if (-not $Worker) {
    if (Test-Path -LiteralPath $out) { throw 'Use a new output directory; prior runs are preserved' }
    if ((Test-Path -LiteralPath $work) -and (Get-ChildItem -LiteralPath $work -Force).Count -ne 0) { throw 'Use an empty private work root; prior binaries/logs are preserved' }
    New-Item -ItemType Directory -Path $out | Out-Null
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    $args=@('-NoLogo','-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Worker',
        '-Library',('"'+[IO.Path]::GetFullPath($Library)+'"'),'-BuildEnvironment',('"'+[IO.Path]::GetFullPath($BuildEnvironment)+'"'),
        '-WorkRoot',('"'+$work+'"'),'-OutDir',('"'+$out+'"'),'-WallSeconds',$WallSeconds,'-MemoryMiB',$MemoryMiB)
    $p=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $work 'worker.stdout.log') -RedirectStandardError (Join-Path $work 'worker.stderr.log')
    try {
        $p.ProcessorAffinity=[IntPtr]1
        $deadline=[DateTime]::UtcNow.AddSeconds($WallSeconds)
        while (-not $p.WaitForExit(250)) {
            $p.Refresh()
            if ($p.WorkingSet64 -gt [long]$MemoryMiB*1024*1024 -or [DateTime]::UtcNow -gt $deadline) {
                $p.Kill($true);throw 'Functional worker exceeded limit; partial records preserved'
            }
        }
        Get-Content -LiteralPath (Join-Path $work 'worker.stdout.log')
        if ($p.ExitCode -ne 0) { Get-Content -LiteralPath (Join-Path $work 'worker.stderr.log');throw "Functional worker failed: $($p.ExitCode)" }
    } finally { $p.Dispose() }
    return
}
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]1
$library=[IO.Path]::GetFullPath($Library)
$buildPath=[IO.Path]::GetFullPath($BuildEnvironment)
$build=Get-Content -LiteralPath $buildPath -Raw | ConvertFrom-Json -AsHashtable
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
$allocatorHash=Hash (Join-Path $PSScriptRoot 'allocator.cpp')
$libraryHash=Hash $library
if ($build.mode -ne 'Compile' -or $build.source_sha256['allocator.cpp'] -ne $allocatorHash -or $build.library_sha256 -ne $libraryHash) { throw 'Current allocator source/binary do not match the recorded compilation' }
$sources=@('native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs','native/policies.ps1',
    'native/check_policies.py','src/producer.py','src/checker.py','tools/generate.py')
$hashes=@{}
foreach ($name in $sources) { $hashes[$name]=Hash (Join-Path $artifact $name) }
$inputHash=Hash (Join-Path $artifact 'inputs/traces.jsonl')
$certificateHash=Hash (Join-Path $artifact 'results/campaign/certificates.jsonl')
$env:TEMP=Join-Path $work 'tmp'
$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
$assembly=Join-Path $work 'policy_bridge.dll'
Add-Type -Path @((Join-Path $PSScriptRoot 'NativeBridge.cs'),(Join-Path $PSScriptRoot 'NativePolicies.cs'),(Join-Path $PSScriptRoot 'NativePolicyTests.cs')) -CompilerOptions '/optimize+' -OutputAssembly $assembly
Add-Type -Path $assembly
[P054Native.Bridge]::LoadNative($library)
$environment=[ordered]@{
    mode='Functional'; protocol='matched-five-policy-functional-v1'; performance_measurements_started=$false;
    policies=[P054Native.Bridge]::Policies; fixed_visit_price=[P054Native.Bridge]::FixedVisitPrice;
    source_sha256=$hashes; library_sha256=$libraryHash; managed_assembly_sha256=(Hash $assembly);
    runtime_files_distributed=$false; results_directory='results/native-policy-comparison';
    result_location_kind=$(if($out.Equals($results,[StringComparison]::OrdinalIgnoreCase)){'artifact-stable'}else{'private-reproduction'});
    build_environment_sha256=(Hash $buildPath); compiler=$build.compiler; compiler_flags=$build.compiler_flags;
    input_sha256=$inputHash; saved_certificate_sha256=$certificateHash;
    architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
    powershell=$PSVersionTable.PSVersion.ToString(); dotnet=[Environment]::Version.ToString(); affinity=1; cpu_threads=1;
    complete_path='price/plan/check/mask/index/allocate/materialize/execute/project/guards/free; decoding and verification excluded';
    heuristic_checks='safety-only, no optimizer; zero potentials only when serializing for Python safety schema';
    rho0_scope='all 207 inputs explicitly repriced to 0; original prices retained in cases.jsonl.gz';
    rho1_scope='all 207 inputs explicitly repriced to fixed 1; same payloads/lives/requirements/masks';
    wall_limit_seconds=$WallSeconds; memory_limit_mib=$MemoryMiB
}
[IO.File]::WriteAllText((Join-Path $out 'environment.json'),($environment | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
[P054Native.Bridge]::ComparePoliciesFunctional($artifact,$out)
foreach ($name in $sources) { if ((Hash (Join-Path $artifact $name)) -ne $hashes[$name]) { throw "Source changed during run: $name" } }
if ((Hash $library) -ne $libraryHash -or (Hash $assembly) -ne $environment.managed_assembly_sha256 -or
    (Hash (Join-Path $artifact 'inputs/traces.jsonl')) -ne $inputHash -or
    (Hash (Join-Path $artifact 'results/campaign/certificates.jsonl')) -ne $certificateHash) { throw 'Binary/input changed during run' }
$bindings=[ordered]@{}
$decoded=[ordered]@{}
foreach ($name in @('cases.jsonl','planner-agreement.jsonl','policies.jsonl')) {
    $plain=Join-Path $out $name
    $bytes=(Get-Item -LiteralPath $plain).Length
    if ($bytes -le 150KB) { throw 'Frozen large functional-record coverage changed; review the gzip manifest' }
    $identity=[ordered]@{bytes=$bytes;sha256=(Hash $plain)}
    $compressed=$plain+'.gz'
    $input=[IO.File]::OpenRead($plain)
    $output=[IO.File]::Open($compressed,[IO.FileMode]::CreateNew)
    $gzip=[IO.Compression.GZipStream]::new($output,[IO.Compression.CompressionLevel]::Optimal)
    try { $input.CopyTo($gzip) } finally { $input.Dispose();$gzip.Dispose();$output.Dispose() }
    # Lossless identity is independently rechecked with an actual decompressed
    # byte cap by check_policies.py. Only this owned newly generated plain file
    # is removed; historical datasets and inputs are never changed.
    $decoded[$name+'.gz']=$identity
    $bindings[$name+'.gz']=Hash $compressed
    Remove-Item -LiteralPath $plain
}
$bindings['functional-summary.json']=Hash (Join-Path $out 'functional-summary.json')
$environment['record_sha256']=$bindings
$environment['record_decoded']=$decoded
[IO.File]::WriteAllText((Join-Path $out 'environment.json'),($environment | ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Output 'Functional policies passed. No performance measurements started.'
