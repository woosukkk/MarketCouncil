param([string]$PythonRuntime, [string]$SourceCommit)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (!$PythonRuntime) { $PythonRuntime = Join-Path $PSScriptRoot 'venv\Scripts\python.exe' }
if (!$SourceCommit) { $SourceCommit = git rev-parse HEAD }
if ($SourceCommit -notmatch '^[a-f0-9]{40}$') { throw 'A verified source commit is required' }
$version = & $PythonRuntime -c 'from desktop.preferences import VERSION; print(VERSION)'
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+$') { throw 'Desktop version is invalid' }
$metadata = @{version=$version;source_commit=$SourceCommit} | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'release-build.json'), $metadata, [System.Text.UTF8Encoding]::new($false))
& $PythonRuntime -m PyInstaller --noconfirm --onedir --windowed --name MarketCouncil --paths . --add-data 'infra/searxng;infra/searxng' --add-data 'tools/install_daily_official.ps1;tools' --add-data 'release-build.json;.' --add-data 'benchmarks/openai-pricing-2026-10-27.json;benchmarks' --collect-all chromadb --hidden-import chromadb_rust_bindings --collect-data sentence_transformers --collect-data transformers --collect-data playwright --collect-data crawl4ai --collect-data litellm --copy-metadata chromadb --copy-metadata torch --copy-metadata transformers --recursive-copy-metadata langgraph --exclude-module streamlit --exclude-module pytest desktop/main.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }

# Distribute the complete folder, not the small launcher alone.
Compress-Archive -Path dist/MarketCouncil -DestinationPath dist/MarketCouncil-Windows.zip -Force
$hash = (Get-FileHash -LiteralPath dist/MarketCouncil-Windows.zip -Algorithm SHA256).Hash.ToLowerInvariant()
[System.IO.File]::WriteAllText((Join-Path $PSScriptRoot 'dist/SHA256.txt'), ($hash + '  MarketCouncil-Windows.zip' + [Environment]::NewLine), [System.Text.UTF8Encoding]::new($false))
