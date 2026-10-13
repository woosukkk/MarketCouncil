param([switch]$Setup)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $repoRoot 'venv\Scripts\python.exe'
$runArguments = '-m desktop.daily_official'
if ($Setup) { $runArguments += ' --setup' }
$process = Start-Process -FilePath $runtime -ArgumentList $runArguments -WorkingDirectory $repoRoot -WindowStyle Hidden -Wait -PassThru
exit $process.ExitCode
