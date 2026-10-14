param([Parameter(Mandatory=$true)][string]$Library,
      [Parameter(Mandatory=$true)][string]$BuildEnvironment,
      [Parameter(Mandatory=$true)][string]$WorkRoot,
      [Parameter(Mandatory=$true)][string]$OutDir,
      [int]$WallSeconds=120,[int]$MemoryMiB=1024,[switch]$Worker)
# Functional only. Bounded worker; no measurement or warmup branch.
$ErrorActionPreference='Stop'
$artifact=[IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$work=[IO.Path]::GetFullPath($WorkRoot)
$out=[IO.Path]::GetFullPath($OutDir)
foreach($p in @($work,[IO.Path]::GetFullPath($Library),[IO.Path]::GetFullPath($BuildEnvironment))){
    if($p.Equals($artifact,[StringComparison]::OrdinalIgnoreCase) -or $p.StartsWith($artifact+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Runtime files must remain private'}
}
if($WallSeconds -lt 1 -or $WallSeconds -gt 240 -or $MemoryMiB -lt 128 -or $MemoryMiB -gt 2048){throw 'Invalid worker limits'}
if(-not $Worker){
    if(Test-Path -LiteralPath $out){throw 'Use a new output directory'}
    if((Test-Path -LiteralPath $work) -and (Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Use an empty work root'}
    New-Item -ItemType Directory -Path $work,$out -Force | Out-Null
    $args=@('-NoLogo','-NoProfile','-File',('"'+$PSCommandPath+'"'),'-Worker',
        '-Library',('"'+[IO.Path]::GetFullPath($Library)+'"'),'-BuildEnvironment',('"'+[IO.Path]::GetFullPath($BuildEnvironment)+'"'),
        '-WorkRoot',('"'+$work+'"'),'-OutDir',('"'+$out+'"'),'-WallSeconds',$WallSeconds,'-MemoryMiB',$MemoryMiB)
    $p=Start-Process -FilePath (Join-Path $PSHOME 'pwsh.exe') -ArgumentList $args -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $work 'worker.stdout.log') -RedirectStandardError (Join-Path $work 'worker.stderr.log')
    try{
        $p.ProcessorAffinity=[IntPtr]1;$deadline=[DateTime]::UtcNow.AddSeconds($WallSeconds)
        while(-not $p.WaitForExit(250)){
            $p.Refresh()
            if($p.WorkingSet64 -gt [long]$MemoryMiB*1024*1024 -or [DateTime]::UtcNow -gt $deadline){$p.Kill($true);throw 'Functional worker exceeded limit; partial records preserved'}
        }
        Get-Content -LiteralPath (Join-Path $work 'worker.stdout.log')
        if($p.ExitCode -ne 0){Get-Content -LiteralPath (Join-Path $work 'worker.stderr.log');throw "Worker failed: $($p.ExitCode)"}
    }finally{$p.Dispose()}
    return
}
$env:TEMP=Join-Path $work 'tmp';$env:TMP=$env:TEMP
New-Item -ItemType Directory -Path $env:TEMP -Force | Out-Null
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]1
function Hash([string]$p){(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash}
$build=Get-Content -LiteralPath $BuildEnvironment -Raw | ConvertFrom-Json -AsHashtable
if($build.mode -ne 'Compile' -or $build.source_sha256['allocator.cpp'] -ne (Hash (Join-Path $PSScriptRoot 'allocator.cpp')) -or $build.library_sha256 -ne (Hash $Library)){throw 'Allocator source/binary compilation binding'}
$names=@('native/allocator.cpp','native/NativeBridge.cs','native/NativePolicies.cs','native/NativePolicyTests.cs','native/NativeWorkflow.cs','native/workflow.ps1','src/checker.py','src/producer.py')
$hashes=@{};foreach($n in $names){$hashes[$n]=Hash (Join-Path $artifact $n)}
$assembly=Join-Path $work 'workflow_bridge.dll'
Add-Type -Path @((Join-Path $PSScriptRoot 'NativeBridge.cs'),(Join-Path $PSScriptRoot 'NativePolicies.cs'),(Join-Path $PSScriptRoot 'NativePolicyTests.cs'),(Join-Path $PSScriptRoot 'NativeWorkflow.cs')) -OutputAssembly $assembly -CompilerOptions '/optimize+'
Add-Type -Path $assembly
[P054Native.Bridge]::LoadNative([IO.Path]::GetFullPath($Library))
[P054Native.Bridge]::ExactDocumentWorkflow($artifact,$out)
foreach($n in $names){if((Hash (Join-Path $artifact $n)) -ne $hashes[$n]){throw 'Source changed during execution'}}
$records=@{};foreach($n in @('inputs.jsonl','executions.jsonl','summary.json')){$records[$n]=Hash (Join-Path $out $n)}
$environment=[ordered]@{protocol='exact-document-functional';performance_measurements_started=$false;
    source_sha256=$hashes;record_sha256=$records;library_sha256=(Hash $Library);managed_assembly_sha256=(Hash $assembly);
    input_sha256=(Hash (Join-Path $artifact 'inputs/traces.jsonl'));build_environment_sha256=(Hash $BuildEnvironment);
    os=[Runtime.InteropServices.RuntimeInformation]::OSDescription;architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
    cpu=(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    powershell=$PSVersionTable.PSVersion.ToString();dotnet=[Environment]::Version.ToString();affinity=1;
    wall_limit_seconds=$WallSeconds;working_set_threshold_mib=$MemoryMiB;monitor='250 ms polling; threshold, not OS-enforced memory quota';
    compiler=$build.compiler;compiler_flags=$build.compiler_flags;managed_compiler_flags='/optimize+';
    native_policy_tests_compiled_not_invoked_sha256=(Hash (Join-Path $PSScriptRoot 'NativePolicyTests.cs'))}
[IO.File]::WriteAllText((Join-Path $out 'environment.json'),($environment|ConvertTo-Json -Depth 8),[Text.UTF8Encoding]::new($false))
Write-Output 'Whole exact-document native functional workflow completed; no performance measurements.'
