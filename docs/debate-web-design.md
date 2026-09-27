# MarketCouncil 토론 웹 화면

## 목적

저장된 투자 토론에서 의제, 경쟁 가설, 라운드별 변화, 인용 원문을 빠르게
탐색한다. 기존 Streamlit 뷰어와 JSON을 사용하며 분석 API를 추가 호출하지 않는다.

## 레퍼런스

조사일: 2026-09-27. 아래 서비스의 정보 구조를 참고한 자체 화면이며 복제본이 아니다.

| 레퍼런스 | 참고 요소 | 적용 |
| --- | --- | --- |
| [Kialo](https://www.kialo-edu.com/advantages) | 주장별 찬성·반대 비교 | 의제별 Bull/Bear 카드 |
| [Kialo minimap](https://support.kialo-edu.com/en/hc/discussion-minimap/) | 전체 논증 중 현재 위치 표시 | 왼쪽 의제 선택 및 최종 상태 |
| [Loomio discussions](https://www.loomio.com/docs/en/user_manual/discussions) | 주요 사건을 탐색하는 토론 타임라인 | 라운드 선택, 변화·인정·새 근거·남은 질문 |
| [Loomio proposals](https://www.loomio.com/docs/en/user_manual/polls/proposals) | 토론과 결과의 기록 연결 | 최종 합의점·미해결 쟁점·추가 근거 |
| [Argdown](https://argdown.org/) | 주장과 지지·반박 관계 지도 | 향후 근거 지도 참고. 이번에는 관계 그래프를 추가하지 않음 |
| [Polis](https://pol-is.github.io/polis-documentation/visualization/HowToRead.html) | 의견 집단과 합의 시각화 | 여러 참여자의 실제 응답이 생길 때 검토 |

## 화면 구성

1. 상단: 기업, 분석 생성 시각, 가격 기준일, 의제·라운드·인용·미해결 쟁점 수.
2. 토론 탐색(기본): 왼쪽 의제 / 중앙 검증 질문·라운드·Bull/Bear / 오른쪽 인용 근거.
3. 라운드 선택: 해당 라운드의 주장, 변화 요약, Moderator 평가와 당시 상태.
4. 근거 버튼: 해당 원문 선택, 인용 필터 초기화. 의제·라운드 변경 시 근거 범위도 갱신.
5. 시장 국면: 기존 가격 차트와 기간별 근거 조회 유지.
6. 최종 정리: 요약, 양측 합의, 미해결 쟁점, 추가 확인 자료, 종료 사유.
7. 사이드바: 저장된 분석 세션 선택. 화면 하단: JSON·Markdown 다운로드.

읽을 분량을 줄이기 위해 반론 상세, 라운드 변화, 긴 인용 문단은 접어 둔다.
색과 Bull/Bear 명칭을 함께 사용한다. 좁은 화면에서는 Streamlit의 기본 열 배치를 따른다.

## 데이터 표시 원칙

- 기존 `agenda`, `rounds`, `navigation`, `moderator_summary`, 인용 메타데이터를 사용한다.
- 새 분석이나 숫자·확률·승패를 생성하지 않는다.
- `verified`는 원문 인용 연결 상태로 표시한다. 가설이 사실이라는 뜻으로 표현하지 않는다.
- 최종 쟁점 상태와 선택한 라운드 당시 상태를 구분한다.
- 없는 요약·기준일·근거는 `확인 불가`, `추가 데이터 필요`, 기록 없음으로 표시한다.
- 가설 조건·한계는 원문 `qualifier`를 표시하며 별도 조건을 추론하지 않는다.
- 과거 결과는 그대로 표시한다. 출처 분류나 링크 개선을 과거 JSON에 소급 적용하지 않는다.

## 로컬 실행

```powershell
.\view_debate.bat
```

또는 브라우저 자동 실행 없이 서버만 시작한다.

```powershell
.\venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501 --server.headless true
```

접속: http://localhost:8501. 저장 결과가 없으면 실행 안내를 표시한다.
뷰어만 실행할 때 OpenAI·Docker·새 데이터 수집은 필요하지 않다.
외부 공개 배포와 웹에서 새 분석을 실행하는 기능은 이번 범위에 포함하지 않는다.

## 검증

Streamlit AppTest로 의제·라운드·세션 전환, 인용 버튼과 필터의 동기화,
최종 정리, 빈 결과 안내를 확인한다. 기존 뷰어 데이터 및 렌더러 테스트도 실행한다.

2026-09-27 검증 결과:

- `python -m unittest discover -s tests -p test_debate_web.py -v`: 2개 통과.
- 기존 `test_debate_view_data.py`, `test_debate_transcript_renderer.py`의 테스트 함수
  5개를 직접 실행하여 통과. 환경에 pytest가 없어 의존성을 추가하지 않았다.
- 최신 저장 결과의 기본 토론 화면: AppTest 예외 없음.
- 로컬 서버 `/_stcore/health`: `ok`.
- 브라우저 자동화 연결이 없어 실제 화면 캡처 및 모바일 시각 검증은 미실시.
