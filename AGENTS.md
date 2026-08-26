# Project Instructions

## Project Goal

Build the investment analysis system in this order:

1. Single LLM-based analysis
2. Financial data integration
3. RAG
4. Tools
5. Agent workflows
6. LangGraph
7. Multi-agent architecture

Do not introduce later-stage technologies before they are needed.

## Investment Analysis Principles

* Treat every prompt as an operational specification, not a simple question.
* Define the role, objective, supplied inputs, decision criteria, analysis order,
  output format, and prohibited behavior explicitly.
* Do not ask an agent to jump directly to a conclusion or recommendation.
* Separate verified facts, market expectations, and analyst hypotheses.
* Use this default analysis order when the available inputs support it:
  market environment, industry, company performance, valuation, growth drivers,
  counter-evidence, risks, and hypothesis validation.
* Do not invent a missing section. Mark unavailable evidence as
  `확인 불가` or `추가 데이터 필요`.
* Express conclusions conditionally. State what strengthens, weakens, or
  invalidates each hypothesis.
* Prefer tracking changes and validating previous judgments over pretending to
  predict the future precisely.
* Keep data collection, evidence classification, directional analysis,
  portfolio-risk analysis, and final judgment as separate responsibilities.
* Expand the system incrementally: basic agent, data input, result storage,
  comparison with prior analysis, self-review, and then automation.

## Standard Analysis Output

Unless a strict JSON schema or a specialized collector format applies, use this
section order:

1. 핵심 결론
2. 확인된 사실
3. 시장 기대
4. 투자 가설
5. 긍정 근거
6. 반대 근거
7. 위험 요인
8. 추가 확인 데이터
9. 가설 강화 조건
10. 가설 약화·폐기 조건
11. 최종 판단

Collection agents must return evidence only and must not make an investment
recommendation. Analysis agents must cite the supplied evidence and distinguish
fact from interpretation. Final-judgment agents must compare competing
hypotheses and report confidence and evidence limitations.

## File Rules

* Keep prompt definitions in dedicated prompt files.
* Do not place prompt definitions directly inside agent logic files.

## Coding Rules

* Use Python type hints for new functions.
* Add appropriate error handling for external API calls.
* Make the smallest necessary change.
* Avoid unnecessary refactoring or dependency additions.
* Do not modify any code without explicit user approval.

## Git Rules

* Write commit messages in English only.
* After completing and verifying a meaningful unit of work, create a local commit automatically.
* Do not ask for separate user approval before creating that local commit.
* Commit only changes made for the current approved task and leave unrelated user changes untouched.
* Do not push, create branches, or open pull requests unless explicitly requested.

### PR Convention

* Title format: `[PR type] 주요 기능`
* Body must include:
  * 추가하거나 수정한 기능명
  * 관련 이슈가 존재하면 해당 이슈
  * 어느 코드를 어떤 방식으로 수정했는지
  * 실행 결과
* PR types:
  * `[기능 추가]`: 신규 기능 추가
  * `[버그 수정]`: 버그 수정
  * `[배포 수정]`: 배포 관련 수정

### Issue Convention

* Title format: `[Issue type] 주요 내용`
* Body must include:
  * 이슈 관련 내용
  * 발생하는 문제에 대한 상세 설명
  * 이슈와 관련된 코드 부분
* Issue types:
  * `[기능추가요청]`: 신규 기능 추가 요청
  * `[버그]`: 기존 브랜치 버그 제보

### Branch Convention

* `main`: 최종 발표 및 배포용
* `develop`: 통합 개발용
* `feature/*`: 기능 개발용
* `hotfix/*`: 발표 직전 긴급 수정용

### Commit Convention

* Format: `type: subject`
* Add one space after the colon.
* Write the subject in English.
* Commit types:
  * `feat`: 새로운 기능 추가
  * `fix`: 버그 수정
  * `docs`: 문서 수정
  * `style`: 코드 포매팅 및 코드 스타일 변경
  * `design`: 사용자 UI 변경
  * `test`: 테스트 코드
  * `refactor`: 리팩토링
  * `chore`: 자잘한 수정
  * `rename`: 파일 또는 폴더명 수정
  * `remove`: 파일 삭제만 수행

## Token and Context Usage

* Read only files relevant to the current task.
* Start with targeted searches instead of scanning the entire repository.
* Do not repeatedly read files whose contents are already known.
* Do not inspect `.env`, `venv/`, `__pycache__/`, `results/`, cache directories, generated files, model files, datasets, or binary files unless required.
* Do not repeat large code blocks when a diff or partial snippet is sufficient.
* Keep explanations concise and focused on the issue, proposed changes, affected files, and test results.
* Reuse existing project conventions and known context instead of rediscovering them.

## Required Working Process

### Before Editing

1. Inspect only the files relevant to the request.
2. Explain the current problem or code behavior.
3. Describe the proposed changes and why they are needed.
4. List the files that would be modified.
5. Ask for explicit user approval.
6. Do not edit files, run formatting tools, install dependencies, or execute commands that modify the project before approval.

### After Approval

* Apply only the approved changes.
* Do not make additional unapproved changes.
* If another change becomes necessary, stop and ask for approval again.
* Run relevant tests after editing when possible.

### After Editing

* Summarize the modified files and key changes.
* Report the tests or commands executed and their results.
* Mention remaining issues, assumptions, or unverified behavior.
* Suggest an appropriate English commit message.
* Immediately provide a brief, easy-to-scan summary of what was changed.
* List the modified files and the key change made in each file.

## Approval Rule

A request to analyze, review, explain, debug, or identify a problem is not permission to modify code.

Only modify code after the user clearly approves the proposed changes with a response such as:

* “수정해”
* “진행해”
* “적용해”
* “승인”
* “고쳐줘”

When approval is unclear, explain the proposed changes and wait without modifying any files.
