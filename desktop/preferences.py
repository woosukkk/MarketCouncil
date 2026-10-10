"""Remember non-secret input only; credentials never enter this file."""
import json
from pathlib import Path
from urllib.request import Request, urlopen

VERSION = "0.4.0"
RELEASES = "https://api.github.com/repos/woosukkk/MarketCouncil/releases?per_page=30"


def load_preferences(path: Path) -> dict[str, str]:
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        return {key:value for key,value in data.items() if key in {"company","search"} and isinstance(value,str) and len(value)<=500}
    except (OSError,ValueError,AttributeError):
        return {}


def save_preferences(path: Path, company: str, search: str) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"company":company[:120],"search":search[:500]},ensure_ascii=False),encoding="utf-8")
    temporary.replace(path)


def newer_release(releases: list[dict]) -> dict | None:
    current=tuple(map(int,VERSION.split(".")))
    candidates=[]
    for release in releases:
        tag=release.get("tag_name","")
        if release.get("draft") or not tag.startswith("desktop-v"):continue
        try:version=tuple(map(int,tag.removeprefix("desktop-v").split(".")))
        except ValueError:continue
        if len(version)==3 and version>current:candidates.append((version,release))
    return max(candidates,key=lambda item:item[0])[1] if candidates else None


def check_update() -> dict | None:
    req=Request(RELEASES,headers={"User-Agent":"MarketCouncil-desktop"})
    with urlopen(req,timeout=5) as response:
        return newer_release(json.load(response))
