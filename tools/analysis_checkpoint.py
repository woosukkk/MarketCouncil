"""Local-only completed stages; never persist credentials or publish checkpoints."""
import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Callable

class AnalysisCheckpoint:
    def __init__(self, path: Path, scope: str) -> None:
        self.path=path;self.scope=scope;self.steps={}
        if path.exists():
            record=json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(record,dict) or record.get("version")!=1 or record.get("scope")!=scope or not isinstance(record.get("steps"),dict):raise ValueError("Checkpoint scope or format does not match")
            self.steps=record["steps"]

    def call(self, name: str, callback: Callable, *args: Any, **kwargs: Any) -> Any:
        fingerprint=hashlib.sha256(json.dumps([args,kwargs],sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()
        cached=self.steps.get(name)
        if cached and cached.get("input_hash")==fingerprint:return copy.deepcopy(cached["value"])
        value=callback(*args,**kwargs)
        encoded=json.dumps({"version":1,"scope":self.scope,"steps":{**self.steps,name:{"input_hash":fingerprint,"value":value}}},ensure_ascii=False,allow_nan=False)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temporary=self.path.with_suffix(".tmp");temporary.write_text(encoded,encoding="utf-8");temporary.replace(self.path)
        self.steps[name]={"input_hash":fingerprint,"value":copy.deepcopy(value)}
        return value

    def bind(self, callback: Callable, name: str, rounds: bool = False) -> Callable:
        def wrapped(*args: Any, **kwargs: Any) -> Any:
            key=name+("-"+str(args[0].get("current_round",1)) if rounds else "")
            return self.call(key,callback,*args,**kwargs)
        return wrapped
