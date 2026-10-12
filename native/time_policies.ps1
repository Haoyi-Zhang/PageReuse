param(
    [ValidateSet('Prepare','Measure')][string]$Mode='Prepare',
    [Parameter(Mandatory=$true)][string]$Library,
    [Parameter(Mandatory=$true)][string]$BuildEnvironment,
    [Parameter(Mandatory=$true)][string]$WorkRoot,
    [Parameter(Mandatory=$true)][string]$OutDir,
    [string]$SlotId='',
    [int]$WallSeconds=120,
    [int]$MemoryMiB=1024,
    [switch]$Worker
)
# Prepare has no performance-counter reads, warmups or native execution.
# Measure requires a human-assigned exclusive slot; it is forbidden on CI.
$ErrorActionPreference='Stop'
if ($Mode -eq 'Measure' -and $SlotId -notmatch '^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$') { throw 'Explicit parent-assigned reserved SlotId required; no timers started' }
if ($Mode -eq 'Measure' -and ($env:CI -eq 'true' -or $env:GITHUB_ACTIONS -eq 'true')) { throw 'Five-policy timing is forbidden on shared CI' }
if ($WallSeconds -lt 1 -or $WallSeconds -gt 120 -or $MemoryMiB -lt 128 -or $MemoryMiB -gt 1024) { throw 'Worker cap is at most 120 seconds and 1024 MiB' }
$artifact=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$prefix=$artifact.TrimEnd('\','/')+[IO.Path]::DirectorySeparatorChar
$results=[IO.Path]::GetFullPath((Join-Path $artifact 'results/native-policy-comparison'))
$out=[IO.Path]::GetFullPath($OutDir)
if (-not $out.StartsWith($results+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)) { throw 'Use an explicit new child directory of results/native-policy-comparison; functional records are protected' }
$work=[IO.Path]::GetFullPath($WorkRoot)
$library=[IO.Path]::GetFullPath($Library)
$buildPath=[IO.Path]::GetFullPath($BuildEnvironment)
foreach($path in @($work,$library,$buildPath)) {
    if($path.Equals($artifact,[StringComparison]::OrdinalIgnoreCase) -or $path.StartsWith($prefix,[StringComparison]::OrdinalIgnoreCase)){throw 'All binaries/builds/caches/logs must stay outside the artifact-root repository'}
}
if(Test-Path -LiteralPath $out){throw 'Timing output already exists; preserve every prior attempt'}
if(-not $Worker) {
    if($Mode -eq 'Prepare' -and (Test-Path -LiteralPath $work) -and (Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Prepare needs an empty private work root'}
    if($Mode -eq 'Measure' -and -not (Test-Path -LiteralPath (Join-Path $work 'prepared.json'))){throw 'Run Prepare before the exclusive slot; Measure never compiles'}
    New-Item -ItemType Directory -Path $work -Force | Out-Null
    $stdout=Join-Path $work ($Mode.ToLowerInvariant()+'.stdout.log')
    $stderr=Join-Path $work ($Mode.ToLowerInvariant()+'.stderr.log')
    if((Test-Path -LiteralPath $stdout) -or (Test-Path -LiteralPath $stderr)){throw 'Preserve previous worker logs; use a new private work root'}
    $arguments=@('-NoLogo','-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Worker','-Mode',$Mode,
        '-Library',('"'+$library+'"'),'-BuildEnvironment',('"'+$buildPath+'"'),'-WorkRoot',('"'+$work+'"'),'-OutDir',('"'+$out+'"'),
        '-WallSeconds',$WallSeconds,'-MemoryMiB',$MemoryMiB)
    if($Mode -eq 'Measure'){$arguments+=@('-SlotId',$SlotId)}
    $p=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
    try {
        $p.ProcessorAffinity=[IntPtr]1;$deadline=[DateTime]::UtcNow.AddSeconds($WallSeconds)
        while(-not $p.WaitForExit(250)) {
            $p.Refresh()
            if($p.WorkingSet64 -gt [long]$MemoryMiB*1024*1024 -or [DateTime]::UtcNow -gt $deadline){$p.Kill($true);throw 'Bounded worker exceeded cap; partial records/logs preserved'}
        }
        Get-Content -LiteralPath $stdout
        if($p.ExitCode -ne 0){Get-Content -LiteralPath $stderr;throw "Worker failed: $($p.ExitCode)"}
    } finally {if(-not $p.HasExited){$p.Kill($true)};$p.Dispose()}
    return
}
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]1
function Hash([string]$path){(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash}
function SaveJson([string]$path,$value){[IO.File]::WriteAllText($path,($value|ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))}
function DecodedIdentity([string]$path) {
    $file=[IO.File]::OpenRead($path)
    $stream=if($path.EndsWith('.gz')){[IO.Compression.GZipStream]::new($file,[IO.Compression.CompressionMode]::Decompress)}else{$file}
    $sha=[Security.Cryptography.SHA256]::Create();$buffer=[byte[]]::new(65536);[long]$total=0
    try {
        while(($n=$stream.Read($buffer,0,$buffer.Length)) -gt 0){$total+=$n;if($total -gt 256MB){throw 'Actual decompressed input exceeds 256 MiB'};[void]$sha.TransformBlock($buffer,0,$n,$buffer,0)}
        [void]$sha.TransformFinalBlock([byte[]]::new(0),0,0)
        return [ordered]@{bytes=$total;sha256=[Convert]::ToHexString($sha.Hash)}
    } finally {$sha.Dispose();$stream.Dispose();$file.Dispose()}
}
$functional=$results
$functionalEnvironmentPath=Join-Path $functional 'environment.json'
$functionalSummaryPath=Join-Path $functional 'independent-summary.json'
$functionalEnvironment=Get-Content -LiteralPath $functionalEnvironmentPath -Raw|ConvertFrom-Json -AsHashtable
$functionalSummary=Get-Content -LiteralPath $functionalSummaryPath -Raw|ConvertFrom-Json -AsHashtable
if($functionalSummary.status -ne 'SOURCE_SEPARATED_FUNCTIONAL_PASSED' -or $functionalSummary.retained_policy_records -ne 1000 -or $functionalSummary.native_policy_records -ne 35 -or
    $functionalSummary.environment_sha256 -ne (Hash $functionalEnvironmentPath)){throw 'Current source-separated functional gate missing'}
$coreSources=@('native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs','native/policies.ps1','native/check_policies.py','src/producer.py','src/checker.py','tools/generate.py')
if($functionalEnvironment.source_sha256.Count -ne $coreSources.Count){throw 'Functional source manifest coverage changed'}
$sources=$coreSources+@('native/NativePolicyTiming.cs','native/time_policies.ps1')
$sourceHashes=[ordered]@{}
foreach($name in $sources){$sourceHashes[$name]=Hash (Join-Path $artifact $name)}
foreach($name in $coreSources){if($functionalEnvironment.source_sha256[$name] -ne $sourceHashes[$name]){throw "Functional source changed: $name"}}
foreach($entry in $functionalEnvironment.record_sha256.GetEnumerator()){if((Hash (Join-Path $functional $entry.Key)) -ne $entry.Value){throw "Functional record changed: $($entry.Key)"}}
foreach($entry in $functionalEnvironment.record_decoded.GetEnumerator()) {
    $identity=DecodedIdentity (Join-Path $functional $entry.Key)
    if($identity.bytes -ne $entry.Value.bytes -or $identity.sha256 -ne $entry.Value.sha256){throw 'Functional decompressed identity changed'}
}
$inputHashes=[ordered]@{'inputs/traces.jsonl'=(Hash (Join-Path $artifact 'inputs/traces.jsonl'));'results/campaign/certificates.jsonl'=(Hash (Join-Path $artifact 'results/campaign/certificates.jsonl'))}
if($inputHashes['inputs/traces.jsonl'] -ne $functionalEnvironment.input_sha256 -or $inputHashes['results/campaign/certificates.jsonl'] -ne $functionalEnvironment.saved_certificate_sha256){throw 'Functional input binding changed'}
$build=Get-Content -LiteralPath $buildPath -Raw|ConvertFrom-Json -AsHashtable
$libraryHash=Hash $library
if($build.mode -ne 'Compile' -or $build.source_sha256['allocator.cpp'] -ne $sourceHashes['native/allocator.cpp'] -or $build.library_sha256 -ne $libraryHash -or $functionalEnvironment.library_sha256 -ne $libraryHash){throw 'Actual current allocator source/binary/compile binding mismatch'}
$assembly=Join-Path $work 'policy_timing.dll'
$preparedPath=Join-Path $work 'prepared.json'
$inputs=Join-Path $work 'inputs'
$env:TEMP=Join-Path $work 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force|Out-Null
if($Mode -eq 'Prepare') {
    Add-Type -Path @((Join-Path $PSScriptRoot 'NativeBridge.cs'),(Join-Path $PSScriptRoot 'NativePolicies.cs'),(Join-Path $PSScriptRoot 'NativePolicyTests.cs'),(Join-Path $PSScriptRoot 'NativePolicyTiming.cs')) -CompilerOptions '/optimize+' -OutputAssembly $assembly
    Add-Type -Path $assembly
    New-Item -ItemType Directory -Path $inputs|Out-Null
    [P054Native.Bridge]::PreparePolicyTimingInputs($artifact,$functional,$inputs)
    $prepared=[ordered]@{status='PREPARED_NOT_MEASURED';source_sha256=$sourceHashes;input_sha256=$inputHashes;
        functional_environment_sha256=(Hash $functionalEnvironmentPath);functional_summary_sha256=(Hash $functionalSummaryPath);
        library_sha256=$libraryHash;build_environment_sha256=(Hash $buildPath);managed_assembly_sha256=(Hash $assembly);
        prepared_input_sha256=@{'panel.jsonl.gz'=(Hash (Join-Path $inputs 'panel.jsonl.gz'));'functional-values.jsonl.gz'=(Hash (Join-Path $inputs 'functional-values.jsonl.gz'))};
        protocol=([P054Native.Bridge]::PolicyTimingProtocol());performance_measurements_started=$false;native_executions=0}
    SaveJson $preparedPath $prepared
    Write-Output 'Prepared and compiled privately. No native executions, warmups, timers or public timing records.'
    return
}
# All compilation took place in Prepare, before the slot. Revalidate its bindings.
$prepared=Get-Content -LiteralPath $preparedPath -Raw|ConvertFrom-Json -AsHashtable
foreach($name in $sources){if($prepared.source_sha256[$name] -ne $sourceHashes[$name]){throw 'Prepared source changed; reprepare privately before timing'}}
foreach($name in $inputHashes.Keys){if($prepared.input_sha256[$name] -ne $inputHashes[$name]){throw 'Prepared input changed'}}
if($prepared.functional_environment_sha256 -ne (Hash $functionalEnvironmentPath) -or $prepared.functional_summary_sha256 -ne (Hash $functionalSummaryPath) -or
    $prepared.library_sha256 -ne $libraryHash -or $prepared.build_environment_sha256 -ne (Hash $buildPath) -or $prepared.managed_assembly_sha256 -ne (Hash $assembly)){throw 'Prepared functional/binary/build binding changed'}
foreach($name in $prepared.prepared_input_sha256.Keys){if($prepared.prepared_input_sha256[$name] -ne (Hash (Join-Path $inputs $name))){throw 'Prepared panel/value input changed'}}
Add-Type -Path $assembly
[P054Native.Bridge]::ValidatePolicyTimingProtocol()
[P054Native.Bridge]::LoadNative($library)
New-Item -ItemType Directory -Path $out|Out-Null
$sourceCopy=Join-Path $out 'measured-source'
foreach($name in $sources){$dest=Join-Path $sourceCopy $name;New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force|Out-Null;Copy-Item -LiteralPath (Join-Path $artifact $name) -Destination $dest}
$inputCopy=Join-Path $out 'measured-input'
New-Item -ItemType Directory -Path $inputCopy|Out-Null
Copy-Item -LiteralPath (Join-Path $inputs 'panel.jsonl.gz'),(Join-Path $inputs 'functional-values.jsonl.gz') -Destination $inputCopy
Copy-Item -LiteralPath $buildPath -Destination (Join-Path $inputCopy 'native-build-environment.json')
$copyManifest=[ordered]@{}
function CopyInput([string]$from,[string]$relative) {
    $dest=Join-Path $inputCopy $relative
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force|Out-Null
    if($from.EndsWith('.jsonl') -and (Get-Item -LiteralPath $from).Length -gt 150KB) {
        $dest+='.gz';$input=[IO.File]::OpenRead($from);$output=[IO.File]::Open($dest,[IO.FileMode]::CreateNew)
        $gzip=[IO.Compression.GZipStream]::new($output,[IO.Compression.CompressionLevel]::Optimal)
        try{$input.CopyTo($gzip)}finally{$input.Dispose();$gzip.Dispose();$output.Dispose()}
    } else {Copy-Item -LiteralPath $from -Destination $dest}
    $key=[IO.Path]::GetRelativePath($inputCopy,$dest).Replace('\','/')
    $copyManifest[$key]=[ordered]@{sha256=(Hash $dest);decoded=(DecodedIdentity $dest)}
    if($copyManifest[$key].decoded.sha256 -ne (DecodedIdentity $from).sha256){throw 'Input copy/compression was not lossless'}
}
foreach($name in $inputHashes.Keys){CopyInput (Join-Path $artifact $name) $name}
foreach($name in @('environment.json','independent-summary.json')+$functionalEnvironment.record_sha256.Keys){CopyInput (Join-Path $functional $name) ('functional/'+$name)}
foreach($name in @('panel.jsonl.gz','functional-values.jsonl.gz','native-build-environment.json')){$copyManifest[$name]=[ordered]@{sha256=(Hash (Join-Path $inputCopy $name));decoded=(DecodedIdentity (Join-Path $inputCopy $name))}}
SaveJson (Join-Path $out 'source-manifest.json') ([ordered]@{snapshot='measured-source';source_sha256=$sourceHashes;managed_compiler_flags='/optimize+';managed_assembly_sha256=(Hash $assembly);native_library_sha256=$libraryHash})
SaveJson (Join-Path $out 'input-manifest.json') ([ordered]@{snapshot='measured-input';files=$copyManifest;original_input_sha256=$inputHashes;functional_environment_sha256=(Hash $functionalEnvironmentPath);functional_summary_sha256=(Hash $functionalSummaryPath)})
$environment=[ordered]@{mode='Measure';protocol='current-five-policy-timing';slot_id=$SlotId;performance_measurements_started=$false;
    os=[Runtime.InteropServices.RuntimeInformation]::OSDescription;architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
    cpu=@(Get-CimInstance Win32_Processor|Select-Object Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors);
    powershell=$PSVersionTable.PSVersion.ToString();dotnet=[Environment]::Version.ToString();python_used=$false;python_version=$null;
    native_compiler=$build.compiler;native_compiler_flags=$build.compiler_flags;native_compiler_metadata_origin='copied verified native-build-environment.json; binds allocator and DLL, not the new managed assembly';
    managed_compiler_flags='/optimize+';library_sha256=$libraryHash;managed_assembly_sha256=(Hash $assembly);build_environment_sha256=(Hash $buildPath);
    affinity=[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity.ToInt64();cpu_threads=1;
    clock=[ordered]@{name='System.Diagnostics.Stopwatch';frequency=[Diagnostics.Stopwatch]::Frequency;is_high_resolution=[Diagnostics.Stopwatch]::IsHighResolution;zero_ticks_retained=$true};
    runtime=[ordered]@{server_gc=[Runtime.GCSettings]::IsServerGC;gc_latency_mode=[Runtime.GCSettings]::LatencyMode.ToString();forced_gc=$false};
    protocol_details=([P054Native.Bridge]::PolicyTimingProtocol());wall_limit_seconds=$WallSeconds;memory_limit_mib=$MemoryMiB;
    runtime_files_distributed=$false;source_manifest_sha256=(Hash (Join-Path $out 'source-manifest.json'));input_manifest_sha256=(Hash (Join-Path $out 'input-manifest.json'))}
if($environment.affinity -ne 1){throw 'Actual affinity is not the declared one logical CPU'}
SaveJson (Join-Path $out 'environment.json') $environment
$markStarted=[Action]{ $environment.performance_measurements_started=$true;SaveJson (Join-Path $out 'environment.json') $environment }
[P054Native.Bridge]::MeasurePolicyTiming($inputCopy,$out,$SlotId,$markStarted)
foreach($name in $sources){if((Hash (Join-Path $artifact $name)) -ne $sourceHashes[$name] -or (Hash (Join-Path $sourceCopy $name)) -ne $sourceHashes[$name]){throw 'Source changed during timing'}}
foreach($name in $inputHashes.Keys){if((Hash (Join-Path $artifact $name)) -ne $inputHashes[$name]){throw 'Input changed during timing'}}
foreach($name in $copyManifest.Keys){if((Hash (Join-Path $inputCopy $name)) -ne $copyManifest[$name].sha256){throw 'Copied input changed during timing'}}
if((Hash $library) -ne $libraryHash -or (Hash $assembly) -ne $prepared.managed_assembly_sha256 -or (Hash $functionalEnvironmentPath) -ne $prepared.functional_environment_sha256 -or (Hash $functionalSummaryPath) -ne $prepared.functional_summary_sha256){throw 'Binary/functional binding changed during timing'}
$environment['record_sha256']=@{'samples.jsonl.gz'=(Hash (Join-Path $out 'samples.jsonl.gz'));'timing-summary.json'=(Hash (Join-Path $out 'timing-summary.json'))}
$environment['record_decoded']=@{'samples.jsonl.gz'=(DecodedIdentity (Join-Path $out 'samples.jsonl.gz'))}
SaveJson (Join-Path $out 'environment.json') $environment
Write-Output 'All 3080 clock samples and verified timed executions retained; no filtering or guarantee equivalence claimed.'
