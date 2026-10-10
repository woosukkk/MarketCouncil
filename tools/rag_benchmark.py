"""Evaluate fixed local gold cases. This command never calls an LLM."""
import argparse
import hashlib
import json
import math
import statistics
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def validate_dataset(data: dict) -> None:
    if not isinstance(data,dict) or not data.get("name") or not isinstance(data.get("cases"),list) or not data["cases"]:
        raise ValueError("평가 데이터셋 이름과 정답 근거를 지정한 cases가 필요합니다.")
    ids=set()
    for case in data["cases"]:
        if not isinstance(case,dict) or not all(isinstance(case.get(k),str) and case[k].strip() for k in ("id","query","company","as_of_date")):
            raise ValueError("각 사례에 id/query/company/as_of_date가 필요합니다.")
        if case["id"] in ids:raise ValueError("사례 ID는 중복될 수 없습니다.")
        ids.add(case["id"])
        datetime.strptime(case["as_of_date"],"%Y-%m-%d")
        expected=case.get("expected",[])
        if not isinstance(expected,list) or not expected or any(not isinstance(x,dict) or not isinstance(x.get("source"),str) or not x["source"] for x in expected):
            raise ValueError("expected에 실제 정답 source와 선택적 chunk_id를 지정하세요.")
        keys=[(x["source"],str(x.get("chunk_id","*"))) for x in expected]
        if len(set(keys))!=len(keys):raise ValueError("정답 근거가 중복됩니다.")


def score(case: dict, retrieved: list[dict]) -> dict:
    expected=case["expected"]
    matches=lambda gold,row:row.get("source")==gold["source"] and ("chunk_id" not in gold or str(row.get("chunk_id"))==str(gold["chunk_id"]))
    hits=[any(matches(gold,row) for row in retrieved) for gold in expected]
    relevant=[any(matches(gold,row) for gold in expected) for row in retrieved]
    cutoff=datetime.fromisoformat(case["as_of_date"]+"T23:59:59").timestamp()
    metadata=[row.get("metadata") or {} for row in retrieved]
    return {"recall":sum(hits)/len(hits),"precision":sum(relevant)/len(retrieved) if retrieved else 0,"mrr":next((1/(i+1) for i,v in enumerate(relevant) if v),0),"hit":int(any(hits)),"mixed_company":sum(bool(x.get("company")) and x["company"]!=case["company"] for x in metadata),"unknown_company":sum(not x.get("company") for x in metadata),"future_sources":sum(float(x.get("published_timestamp",0) or 0)>cutoff for x in metadata),"retrieved_count":len(retrieved)}


def evaluate(data: dict, search: Callable, top_k: int, repeats: int) -> dict:
    validate_dataset(data)
    if not 1<=top_k<=50 or not 1<=repeats<=10:raise ValueError("top_k는 1~50, 반복은 1~10입니다.")
    rows=[]
    for case in data["cases"]:
        for repeat in range(repeats):
            start=time.perf_counter()
            retrieved=search(query=case["query"],top_k=top_k,company_name=case["company"],as_of_date=case["as_of_date"])
            rows.append({"case_id":case["id"],"repeat":repeat+1,"duration_ms":(time.perf_counter()-start)*1000,**score(case,retrieved)})
    durations=sorted(x["duration_ms"] for x in rows)
    means={key:statistics.mean(x[key] for x in rows) for key in ("recall","precision","mrr","hit")}
    return {"schema_version":1,"kind":"rag","id":str(uuid.uuid4()),"recorded_at":datetime.now(timezone.utc).isoformat(),"label":data["name"],"version":data.get("version","unversioned"),"scope":"retrieval","status":"success","dataset_hash":hashlib.sha256(json.dumps(data,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),"settings":{"top_k":top_k,"repeats":repeats,"case_count":len(data["cases"]),"timing":"model warm-up excluded; search calls only"},"metrics":{**means,"median_ms":statistics.median(durations),"p95_ms":durations[math.ceil(len(durations)*.95)-1],"mixed_company":sum(x["mixed_company"] for x in rows),"unknown_company":sum(x["unknown_company"] for x in rows),"future_sources":sum(x["future_sources"] for x in rows)},"cases":rows}


def main() -> None:
    parser=argparse.ArgumentParser(description="정답 근거가 지정된 로컬 RAG 벤치마크")
    parser.add_argument("dataset",type=Path);parser.add_argument("--top-k",type=int,default=5);parser.add_argument("--repeats",type=int,default=3);parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args();data=json.loads(args.dataset.read_text(encoding="utf-8"));validate_dataset(data)
    from rag.retriever import ReportRetriever, MODEL_NAME
    retriever=ReportRetriever()
    if not retriever.collection.count():raise ValueError("RAG 문서 저장소가 비어 있습니다. 실제 자료를 준비하세요.")
    if not 1<=args.top_k<=50 or not 1<=args.repeats<=10:raise ValueError("평가 설정 범위를 확인하세요.")
    case=data["cases"][0]
    retriever.search(query=case["query"],top_k=args.top_k,company_name=case["company"],as_of_date=case["as_of_date"])
    snapshot_before=retriever.collection.get(include=["documents","metadatas"])
    report=evaluate(data,retriever.search,args.top_k,args.repeats)
    report["settings"]["model"]=MODEL_NAME
    report["settings"]["corpus_count"]=retriever.collection.count()
    snapshot=retriever.collection.get(include=["documents","metadatas"])
    if snapshot!=snapshot_before:raise ValueError("평가 중 문서 저장소가 변경됐습니다. 고정 저장소로 다시 평가하세요.")
    corpus=sorted(zip(snapshot["ids"],snapshot["documents"],snapshot["metadatas"]),key=lambda x:x[0])
    report["settings"]["corpus_hash"]=hashlib.sha256(json.dumps(corpus,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(report,ensure_ascii=False,allow_nan=False),encoding="utf-8")
    print("평가 기록 저장: "+str(args.output))

if __name__=="__main__":main()
