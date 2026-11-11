# -*- mode: python ; coding: utf-8 -*-
# Windows desktop package (onedir, windowed). Run through scripts/build_desktop.ps1 from the project root.
import os
from PyInstaller.utils.hooks import collect_all, collect_data_files, copy_metadata

ROOT = os.path.dirname(SPECPATH)


def under(*parts: str) -> str:
    return os.sep + os.path.join(*parts) + os.sep


datas = [
    (os.path.join(ROOT, 'infra', 'searxng'), 'infra/searxng'),
    (os.path.join(ROOT, 'tools', 'install_daily_official.ps1'), 'tools'),
    (os.path.join(ROOT, 'release-build.json'), '.'),
    (os.path.join(ROOT, 'benchmarks', 'openai-pricing-2026-10-27.json'), 'benchmarks'),
]
for package in ('sentence_transformers', 'transformers', 'playwright', 'crawl4ai', 'litellm'):
    datas += collect_data_files(package)
# The litellm proxy admin UI is never served by the desktop app.
datas = [entry for entry in datas if under('litellm', 'proxy', '_experimental') not in entry[0]]
datas += copy_metadata('chromadb')
datas += copy_metadata('torch')
datas += copy_metadata('transformers')
datas += copy_metadata('langgraph', recursive=True)

chroma_datas, binaries, chroma_imports = collect_all('chromadb')
# chromadb's own tests pull in test-only dependencies.
datas += [entry for entry in chroma_datas if under('chromadb', 'test') not in entry[0]]
hiddenimports = ['chromadb_rust_bindings'] + [name for name in chroma_imports if not name.startswith('chromadb.test')]

a = Analysis(
    [os.path.join(ROOT, 'desktop', 'main.py')],
    pathex=[ROOT],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    # kubernetes: only chromadb's distributed mode. pyarrow: optional pandas backend the app does not use.
    excludes=['streamlit', 'pytest', 'chromadb.test', 'kubernetes', 'pyarrow'],
    noarchive=False,
)


def unused_at_runtime(entry: tuple) -> bool:
    name = entry[0].lower()
    # torch import libraries are link-time only; the patchright driver is used only by crawl4ai's undetected mode.
    return (name.startswith('torch' + os.sep) and name.endswith('.lib')) or name.startswith(os.path.join('patchright', 'driver') + os.sep)


a.datas = [entry for entry in a.datas if not unused_at_runtime(entry)]
a.binaries = [entry for entry in a.binaries if not unused_at_runtime(entry)]

pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='MarketCouncil', console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, upx=False, name='MarketCouncil')
