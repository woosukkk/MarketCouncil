param([string]$PythonRuntime, [string]$SourceCommit)
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot
if (!$PythonRuntime) { $PythonRuntime = Join-Path $projectRoot 'venv\Scripts\python.exe' }
if (!$SourceCommit) { $SourceCommit = git rev-parse HEAD }
if ($SourceCommit -notmatch '^[a-f0-9]{40}$') { throw 'A verified source commit is required' }
$version = & $PythonRuntime -c 'from desktop.preferences import VERSION; print(VERSION)'
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Desktop version is invalid' }
$metadata = @{version=$version;source_commit=$SourceCommit} | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText((Join-Path $projectRoot 'release-build.json'), $metadata, [System.Text.UTF8Encoding]::new($false))
# Collection and exclusion rules live in scripts/desktop.spec.
& $PythonRuntime -m PyInstaller --noconfirm (Join-Path $PSScriptRoot 'desktop.spec')
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }

# Distribute the complete folder, not the small launcher alone.
Compress-Archive -Path dist/MarketCouncil -DestinationPath dist/MarketCouncil-Windows.zip -Force
$hash = (Get-FileHash -LiteralPath dist/MarketCouncil-Windows.zip -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText((Join-Path $projectRoot 'dist/SHA256.txt'), ($hash + '  MarketCouncil-Windows.zip' + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
