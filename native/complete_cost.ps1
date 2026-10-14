param([Parameter(Mandatory=$true)][string]$Authority,
      [Parameter(Mandatory=$true)][string]$Inputs,
      [Parameter(Mandatory=$true)][string]$Library,
      [Parameter(Mandatory=$true)][string]$BuildEnvironment,
      [Parameter(Mandatory=$true)][string]$WorkRoot,
      [Parameter(Mandatory=$true)][string]$OutDir,
      [int]$WallSeconds=180,[int]$MemoryMiB=1024,[switch]$Worker)
# This distinct protocol accepts explicit renewed measurement authority, not an
# invented historical reserved SlotId. Existing reserved-slot scripts unchanged.
$ErrorActionPreference='Stop'
$artifact=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$work=[IO.Path]::GetFullPath($WorkRoot);$out=[IO.Path]::GetFullPath($OutDir)
function Hash([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash}
function Save([string]$p,$o){[IO.File]::WriteAllText($p,($o|ConvertTo-Json -Depth 20),[Text.UTF8Encoding]::new($false))}
if($env:CI -or $env:GITHUB_ACTIONS){throw 'No automatic CI timing'}
$a=Get-Content -LiteralPath $Authority -Raw|ConvertFrom-Json -AsHashtable
if($a.project_id -ne 'P054' -or $a.complete_cost_measurement_authorized -cne $true -or $a.authority_kind -ne 'explicit-user-resume' -or [string]::IsNullOrWhiteSpace($a.request)){throw 'Explicit scoped user measurement authority required'}
foreach($p in @($work,$out,[IO.Path]::GetFullPath($Library),[IO.Path]::GetFullPath($BuildEnvironment),[IO.Path]::GetFullPath($Inputs))){
    if($p.Equals($artifact,[StringComparison]::OrdinalIgnoreCase) -or $p.StartsWith($artifact+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Runtime/input/measurement files must remain private'}
}
if($WallSeconds -lt 1 -or $WallSeconds -gt 240 -or $MemoryMiB -lt 128 -or $MemoryMiB -gt 2048){throw 'Invalid limits'}
$build=Get-Content -LiteralPath $BuildEnvironment -Raw|ConvertFrom-Json -AsHashtable
if($build.source_sha256['allocator.cpp'] -ne (Hash (Join-Path $PSScriptRoot 'allocator.cpp')) -or $build.library_sha256 -ne (Hash $Library)){throw 'Native source/build binding'}
$names=@('native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs','native/NativePolicyTiming.cs','native/NativeCompleteCost.cs','native/complete_cost.ps1','src/checker.py','src/producer.py','native/check_complete_cost.py','native/evidence.py')
if(-not $Worker){
    if((Test-Path -LiteralPath $work) -or (Test-Path -LiteralPath $out)){throw 'Fresh private directories required'}
    New-Item -ItemType Directory -Path $work,$out|Out-Null
    $env:TEMP=Join-Path $work 'tmp';$env:TMP=$env:TEMP;New-Item -ItemType Directory -Path $env:TEMP|Out-Null
    $self=[Diagnostics.Process]::GetCurrentProcess();$self.Refresh();$cpu=$self.TotalProcessorTime.Ticks;$wall=[Diagnostics.Stopwatch]::StartNew()
    Add-Type -Path @((Join-Path $PSScriptRoot 'NativeBridge.cs'),(Join-Path $PSScriptRoot 'NativePolicies.cs'),(Join-Path $PSScriptRoot 'NativePolicyTests.cs'),(Join-Path $PSScriptRoot 'NativePolicyTiming.cs'),(Join-Path $PSScriptRoot 'NativeCompleteCost.cs')) -OutputAssembly (Join-Path $work 'cost_bridge.dll') -CompilerOptions '/optimize+'
    $wall.Stop();$self.Refresh();Save (Join-Path $out 'managed-build.json') @{wall_seconds=$wall.Elapsed.TotalSeconds;process_cpu_seconds=($self.TotalProcessorTime.Ticks-$cpu)/1e7;scope='Add-Type compilation in already-running parent process; not PowerShell startup';flags='/optimize+'}
    $args=@('-NoLogo','-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Worker','-Authority',('"'+[IO.Path]::GetFullPath($Authority)+'"'),'-Inputs',('"'+[IO.Path]::GetFullPath($Inputs)+'"'),'-Library',('"'+[IO.Path]::GetFullPath($Library)+'"'),'-BuildEnvironment',('"'+[IO.Path]::GetFullPath($BuildEnvironment)+'"'),'-WorkRoot',('"'+$work+'"'),'-OutDir',('"'+$out+'"'),'-WallSeconds',$WallSeconds,'-MemoryMiB',$MemoryMiB)
    $launch=[Diagnostics.Stopwatch]::GetTimestamp()
    $p=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $work 'worker.stdout.log') -RedirectStandardError (Join-Path $work 'worker.stderr.log')
    try{
        $p.ProcessorAffinity=[IntPtr]1;$deadline=[DateTime]::UtcNow.AddSeconds($WallSeconds)
        while(-not $p.WaitForExit(200)){$p.Refresh();if($p.WorkingSet64 -gt [long]$MemoryMiB*1024*1024 -or [DateTime]::UtcNow -gt $deadline){$p.Kill($true);throw 'Bound exceeded; partial records preserved'}}
        $p.Refresh();$end=[Diagnostics.Stopwatch]::GetTimestamp()
        Save (Join-Path $out 'worker-process.json') @{launch_timestamp=$launch;exit_observed_timestamp=$end;frequency=[Diagnostics.Stopwatch]::Frequency;launch_to_exit_observed_seconds=($end-$launch)/[double][Diagnostics.Stopwatch]::Frequency;process_cpu_seconds=$p.TotalProcessorTime.TotalSeconds;exit_code=$p.ExitCode;scope='whole worker incl startup/load/preflight/warmup/measured calls/validation/compression; not a per-call cost; exit observed after bounded polling'}
        Get-Content -LiteralPath (Join-Path $work 'worker.stdout.log')
        if($p.ExitCode -ne 0){Get-Content -LiteralPath (Join-Path $work 'worker.stderr.log');throw "Worker failed: $($p.ExitCode)"}
    }finally{$p.Dispose()}
    return
}
$env:TEMP=Join-Path $work 'tmp';$env:TMP=$env:TEMP
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]1
$source=@{};foreach($n in $names){$source[$n]=Hash (Join-Path $artifact $n)}
$inputManifest=Get-Content -LiteralPath (Join-Path $Inputs 'manifest.json') -Raw|ConvertFrom-Json -AsHashtable
if($inputManifest.files.Count -ne 207 -or $inputManifest.frozen_inputs_sha256 -ne (Hash (Join-Path $artifact 'results/exact-document-workflow/inputs.jsonl.gz')) -or $inputManifest.index_sha256 -ne (Hash (Join-Path $Inputs 'index.jsonl'))){throw 'Frozen input binding'}
foreach($n in $inputManifest.files.Keys){if((Hash (Join-Path $Inputs $n)) -ne $inputManifest.files[$n]){throw 'Prepared serialized input changed'}}
$assembly=Join-Path $work 'cost_bridge.dll';Add-Type -Path $assembly
[P054Native.Bridge]::LoadNative([IO.Path]::GetFullPath($Library))
$ready=[Diagnostics.Stopwatch]::GetTimestamp()
Save (Join-Path $out 'ready.json') @{timestamp=$ready;frequency=[Diagnostics.Stopwatch]::Frequency;process_cpu_seconds=[Diagnostics.Process]::GetCurrentProcess().TotalProcessorTime.TotalSeconds;scope='worker entry, authority/source/input checks, assembly/native load; before consumer tests/warmups/calls'}
$protocol=[P054Native.Bridge]::CompleteCostProtocol();Save (Join-Path $out 'protocol.json') $protocol
$envRecord=[ordered]@{project_id='P054';protocol='same-contract-complete-cost';run_id=$a.run_id;authority_kind=$a.authority_kind;authority_file_sha256=(Hash $Authority);historical_reserved_slot_claimed=$false;
    source_sha256=$source;input_manifest=$inputManifest;input_manifest_sha256=(Hash (Join-Path $Inputs 'manifest.json'));native_library_sha256=(Hash $Library);build_environment_sha256=(Hash $BuildEnvironment);managed_assembly_sha256=(Hash $assembly);
    os=[Runtime.InteropServices.RuntimeInformation]::OSDescription;architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();cpu=(Get-CimInstance Win32_Processor|Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    powershell=$PSVersionTable.PSVersion.ToString();dotnet=[Environment]::Version.ToString();affinity=[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity.ToInt64();wall_limit_seconds=$WallSeconds;working_set_threshold_mib=$MemoryMiB;monitor='200ms polling, threshold not OS quota; RSS not measured as an outcome';
    native_compiler=$build.compiler;native_compiler_flags=$build.compiler_flags;managed_compiler_flags='/optimize+';zero_ticks_retained=$true;forced_gc=$false;all_samples_retained=$true;physical_disk_bytes=$null;network_bytes=$null;peak_rss=$null;gpu=$null}
if($envRecord.affinity -ne 1){throw 'Affinity changed'}
Save (Join-Path $out 'environment.json') $envRecord
[P054Native.Bridge]::MeasureCompleteCost([IO.Path]::GetFullPath($Inputs),$out)
foreach($n in $names){if((Hash (Join-Path $artifact $n)) -ne $source[$n]){throw 'Measured source changed'}}
foreach($n in $inputManifest.files.Keys){if((Hash (Join-Path $Inputs $n)) -ne $inputManifest.files[$n]){throw 'Measured input changed'}}
if((Hash $Library) -ne $envRecord.native_library_sha256 -or (Hash $assembly) -ne $envRecord.managed_assembly_sha256){throw 'Binary changed'}
$envRecord['record_sha256']=@{};foreach($n in @('samples.jsonl.gz','completion.json','protocol.json','ready.json')){$envRecord.record_sha256[$n]=Hash (Join-Path $out $n)}
Save (Join-Path $out 'environment.json') $envRecord
Write-Output 'All 6624 measured calls and 828 warmup native calls completed; four ordinary-consumer controls rejected; no trimming.'
