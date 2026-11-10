# 평가셋 v1 만들기

관련: [ROADMAP P2](ROADMAP.md), [공통 평가 기준](standard-evaluation.md), 이슈 #24.

## 목적

"근거 기반 토론이 단일 답변보다 낫다"는 주장을 실제 점수로 확인한다. 평가 도구(`tools/rag_benchmark.py`, `tools/quality_benchmark.py`, `tools/external_evaluation.py`)는 이미 있지만 **사람이 정답을 정한 데이터셋이 없어 실측 점수가 없다.** v1은 그 첫 데이터셋이다.

## 범위 (v1)

- 기업: 삼성전자. 현재 로컬 색인 문서 48건이 모두 삼성전자다. 다른 기업은 문서를 색인한 뒤 v2에서 추가한다.
- 문항: 30~50개. 실적 수치, 사업부 동향, 위험 요인, 가이던스, 공시 사건을 고르게 포함한다.
- 기준일: 문항마다 `as_of_date`를 정한다. 기준일 이후 발행 문서는 정답이 될 수 없다.

## 만드는 순서

1. 후보 문서 목록을 뽑는다. 모델·네트워크 호출이 없다.

   ```powershell
   venv\Scripts\python.exe -m tools.rag_dataset_candidates --company 삼성전자 --as-of-date 2026-11-10 --output benchmarks\candidates-samsung.csv
   ```

2. 문서를 읽고 질문을 직접 쓴다. 질문 하나에 답을 담은 문서의 `source`(파일명)를 `expected`에 넣는다. 특정 청크까지 확인했다면 `chunk_id`를 함께 적는다.
3. `benchmarks/rag.dataset.example.json` 형식을 따라 `benchmarks/rag.dataset.v1.json`을 만든다. `dataset_kind`는 `real`, `version`은 `1`로 둔다. 예시 파일은 형식 확인용이며 점수 기록에 쓰지 않는다.
4. 다른 사람이 10~20%를 교차 검토하면 정답 신뢰도가 올라간다. 검토 범위를 `note`에 적는다.
5. 데이터셋을 확정하면 내용을 바꾸지 않는다. 고칠 때는 `version`을 올린다. 보고서의 `dataset_hash`가 버전을 구분한다.

## 측정

```powershell
venv\Scripts\python.exe -m tools.rag_benchmark benchmarks\rag.dataset.v1.json --top-k 5 --repeats 3 --output results\benchmarks\rag-v1-baseline.json
```

- Recall@k, Precision@k, MRR, 지연시간(중앙값·p95), 다른 기업·기준일 이후 자료 혼입 수를 기록한다.
- 결과 JSON은 관리자 화면의 검색 평가 탭으로 가져온다.
- 같은 데이터셋·`top_k`·코퍼스 해시끼리만 비교한다.

## 답변 비교 (v1 다음 단계)

같은 문항으로 단일 LLM, RAG 단일 답변, 토론 결과를 만들고 주장–인용 지지 여부를 사람이 판정한다(`tools/quality_benchmark.py` 검토 큐). 이 단계는 유료 호출이 필요하므로 실행 전 승인을 받는다. Ragas 점수는 [공통 평가 기준](standard-evaluation.md)의 가져오기 절차를 따른다.

## 하지 않는 것

- 모델이 만든 질문·정답을 사람 검수 없이 `real` 데이터셋으로 쓰지 않는다.
- 점수를 전체 서비스 정확도나 환각률로 일반화하지 않는다.
- 원문 본문을 데이터셋이나 보고서에 복사하지 않는다(파일명·청크 번호만 사용).
