$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$taskUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$runner = Join-Path $repoRoot 'venv\Scripts\pythonw.exe'
if (!(Test-Path -LiteralPath $runner)) { throw 'Project Python runtime is missing' }
$launcher = Join-Path $repoRoot 'tools\run_daily_official.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "' + $launcher + '"') -WorkingDirectory $repoRoot
$login = New-ScheduledTaskTrigger -AtLogOn -User $taskUser
$login.Delay = 'PT2M'
$daily = New-ScheduledTaskTrigger -Daily -At '09:00'
$principal = New-ScheduledTaskPrincipal -UserId $taskUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 4) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName 'MarketCouncil Daily Samsung Official' -Action $action -Trigger @($login,$daily) -Principal $principal -Settings $settings -Description 'Samsung analysis and official publication once per KST date; encrypted user credentials.' -Force | Out-Null
