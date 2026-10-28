"""Bounded structured-output retries and metadata-only local diagnostics."""
import json
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from tools.run_metrics import create_response

class ResponseIncomplete(ValueError):
    def __init__(self, response: Any) -> None:
        self.response_status = getattr(response, "status", "unknown")
        self.incomplete_reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
        super().__init__("Structured response did not complete")

def ensure_complete(response: Any) -> None:
    if getattr(response, "status", "completed") != "completed":
        raise ResponseIncomplete(response)

def record_response(name: str, limit: int, response: Any = None, error: Exception | None = None) -> None:
    folder = os.getenv("RESULTS_RESPONSE_METRICS_DIR")
    if not folder: return
    usage = getattr(response, "usage", None)
    record = {"recorded_at":datetime.now(timezone.utc).isoformat(),"run_id":os.getenv("RESULTS_RUN_ID"),"source_version":os.getenv("RESULTS_SOURCE_VERSION"),"phase": name, "limit": limit, "status": getattr(response, "status", "error"), "reason": getattr(getattr(response, "incomplete_details", None), "reason", None), "input_tokens": getattr(usage, "input_tokens", None), "output_tokens": getattr(usage, "output_tokens", None), "reasoning_tokens": getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", None)}
    if error is not None:
        record.update(error_type=type(error).__name__, http_status=getattr(error, "status_code", None))
        if getattr(error,"code",None) in {"insufficient_quota","credit_balance_exhausted","rate_limit_exceeded","invalid_api_key","context_length_exceeded"}:record["api_code"]=error.code
    try:
        target=Path(folder);target.mkdir(parents=True,exist_ok=True)
        (target/(str(uuid.uuid4())+".json")).write_text(json.dumps(record),encoding="utf-8")
    except OSError: pass

def structured_response(client: Any, instructions: str, input_text: str, name: str, schema: dict, max_output_tokens: int = 4000) -> dict:
    if hasattr(client, "with_options"): client=client.with_options(max_retries=0,timeout=180)
    limit=min(max(max_output_tokens,4000),8000)
    for attempt in range(3):
        response=None
        try:
            response=create_response(client,name,model=__import__("config").MODEL_NAME,instructions=instructions,text={"format":{"type":"json_schema","name":name,"strict":True,"schema":schema}},input=input_text,reasoning={"effort":"minimal"},max_output_tokens=limit)
        except Exception as error:
            record_response(name,limit,error=error)
            status=getattr(error,"status_code",None);code=getattr(error,"code",None)
            transient=type(error).__name__ in {"APIConnectionError","APITimeoutError"} or (isinstance(status,int) and status>=500) or (status==429 and code not in {"insufficient_quota","credit_balance_exhausted"})
            if not transient or attempt==2: raise
            time.sleep(2**attempt);continue
        record_response(name,limit,response)
        try:
            ensure_complete(response)
            result=json.loads(response.output_text)
            if not isinstance(result,dict):raise ValueError("Structured response must be an object")
            return result
        except ResponseIncomplete as error:
            if error.incomplete_reason!="max_output_tokens" or limit>=8000 or attempt==2: raise
            limit=8000
        except (json.JSONDecodeError,ValueError):
            if attempt==2:raise
    raise RuntimeError("Structured response attempts exhausted")
