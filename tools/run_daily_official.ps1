param([switch]$Setup)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $repoRoot 'venv\Scripts\pythonw.exe'
$runArguments = '-m desktop.daily_official --prompt'
if ($Setup) { $runArguments = '-m desktop.daily_official --setup' }
$process = Start-Process -FilePath $runtime -ArgumentList $runArguments -WorkingDirectory $repoRoot -WindowStyle Normal -PassThru
$null = $process.Handle
$process.WaitForExit()
exit $process.ExitCode
