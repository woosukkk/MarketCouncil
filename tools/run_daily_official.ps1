param([switch]$Setup)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$runtime = Join-Path $repoRoot 'venv\Scripts\pythonw.exe'
$runArguments = '-m desktop.daily_official'
if ($Setup) { $runArguments += ' --setup' }
$process = Start-Process -FilePath $runtime -ArgumentList $runArguments -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru
$null = $process.Handle
$process.WaitForExit()
exit $process.ExitCode
