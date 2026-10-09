$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
& .\venv\Scripts\python.exe -m PyInstaller --noconfirm --onefile --windowed --name MarketCouncil --paths . --add-data 'infra/searxng;infra/searxng' --collect-all chromadb --hidden-import chromadb_rust_bindings --collect-data sentence_transformers --collect-data transformers --collect-data playwright --collect-data crawl4ai --collect-data litellm --copy-metadata chromadb --copy-metadata torch --copy-metadata transformers --recursive-copy-metadata langgraph --exclude-module streamlit --exclude-module pytest desktop/main.py
if ($LASTEXITCODE -ne 0) { throw 'Desktop build failed' }
