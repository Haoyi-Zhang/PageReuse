param([Parameter(Mandatory=$true)][string]$Library,
      [Parameter(Mandatory=$true)][string]$Output)
$ErrorActionPreference='Stop'
if(Test-Path -LiteralPath $Output){throw 'Use a new comparison output directory'}
[Diagnostics.Process]::GetCurrentProcess().ProcessorAffinity=[IntPtr]1
Add-Type -Path (Join-Path $PSScriptRoot 'NativeBridge.cs') -CompilerOptions '/optimize+'
[P054Native.Bridge]::LoadNative([IO.Path]::GetFullPath($Library))
[P054Native.Bridge]::ComparePlanners((Split-Path -Parent $PSScriptRoot),[IO.Path]::GetFullPath($Output))
$environment=[ordered]@{os=[Runtime.InteropServices.RuntimeInformation]::OSDescription;
    architecture=[Runtime.InteropServices.RuntimeInformation]::ProcessArchitecture.ToString();
    dotnet=[Environment]::Version.ToString(); powershell=$PSVersionTable.PSVersion.ToString();
    cpu=(Get-CimInstance Win32_Processor|Select-Object Name,NumberOfCores,NumberOfLogicalProcessors);
    affinity_mask=1; timer='Stopwatch'; compiler_flags='C++17 -O2'; pairs=9;
    workload='unchanged 14-case native panel'; comparison='fresh/direct-union/incremental'}
[IO.File]::WriteAllText((Join-Path $Output 'environment.json'),($environment|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
Write-Output 'Exact planner agreement and matched native comparison completed.'
