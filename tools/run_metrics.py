"""Local measurements only; no prompts, credentials or remote upload."""
import json
import os
import platform
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Any


def measure_analysis(company: str, run: Callable[[], Any], folder: Path) -> Any:
    started=time.perf_counter();cpu=time.process_time()
    report={"schema_version":1,"kind":"monitoring","id":str(uuid.uuid4()),"recorded_at":datetime.now(timezone.utc).isoformat(),"label":company,"version":"source","scope":"analysis","status":"success","metrics":{},"environment":{"os":platform.system(),"python":platform.python_version(),"cpu_count":os.cpu_count()}}
    try:
        return run()
    except Exception:
        report["status"]="failed"
        raise
    finally:
        report["metrics"]={"duration_ms":(time.perf_counter()-started)*1000,"cpu_ms":(time.process_time()-cpu)*1000}
        try:
            folder.mkdir(parents=True,exist_ok=True)
            path=folder/(report["id"]+".json")
            path.write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding="utf-8")
            print("성능 기록: "+str(path))
        except OSError:
            print("성능 기록 저장 실패 · 분석 결과는 유지됩니다.")
