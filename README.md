<p align="right"><strong>한국어</strong> | <a href="README.en.md">English</a></p>

<div align="center">

# MarketCouncil

### 같은 근거를 두고, 서로 다른 투자 가설을 비교합니다.

Bull과 Bear가 같은 자료로 토론하고, Moderator가 쟁점과 추가로 확인할 근거를 정리합니다.

[서비스](https://frontend-six-pi-h5i7tztups.vercel.app/) · [리서치 라이브러리](https://frontend-six-pi-h5i7tztups.vercel.app/app) · [Windows 다운로드](https://frontend-six-pi-h5i7tztups.vercel.app/download)

`React` · `Python` · `LangGraph` · `ChromaDB / BGE-M3` · `Supabase` · `Vercel`

</div>

[![MarketCouncil 소개 페이지](docs/images/readme/landing.jpg)](https://frontend-six-pi-h5i7tztups.vercel.app/)

## 무엇을 할 수 있나요?

- 리서치 라이브러리에서 삼성전자, SK하이닉스, 현대자동차, NAVER, Apple, Microsoft의 공개 분석을 찾아 읽습니다.
- 토론의 쟁점과 Bull·Bear 발언을 비교하고, 각 주장에 연결된 인용과 원문을 확인합니다.
- 로그인하면 관심기업과 분석을 저장할 수 있습니다. 개인 토론은 비공개로 보관되며, 선택한 결과만 링크로 공유하거나 커뮤니티에 게시합니다.
- Windows 앱에서 새 분석을 만듭니다. 공개 웹에서는 저장된 결과를 읽고 비교하며, 화면 언어는 한국어와 영어 중 선택할 수 있습니다.

| 리서치 라이브러리 | 토론 상세 |
| --- | --- |
| ![공개 분석 목록](docs/images/readme/library.jpg) | ![쟁점과 라운드가 표시된 토론 상세](docs/images/readme/debate.jpg) |

<details>
<summary>토론에서 인용과 원문을 확인하는 화면</summary>

![출처와 인용이 펼쳐진 실제 화면](docs/images/readme/evidence.jpg)

</details>

## 어떤 원리로 동작하나요?

1. **근거 준비** — 종목과 분석 기준일을 정하고, 공시·실적 자료와 검색된 문서를 공통 근거로 모읍니다. 최소 원문이 부족하면 분석을 보류합니다.
2. **토론** — Bull은 상승 가설을, Bear는 하락 가설을 제시합니다. Moderator는 서로 다른 주장이 어떤 자료와 조건에 기대는지 정리합니다.
3. **근거 추적** — 주장에 출처와 인용을 연결합니다. 인용이 뒷받침하는 범위, 반대 근거, 추가 확인 항목을 결과에 남깁니다.
4. **보관과 열람** — 분석과 원문 보관은 사용자 PC에서 처리합니다. 공유할 결과만 클라우드에 저장하고, 웹에서 공식·공개 토론을 열람합니다.

검색 품질은 정답 근거가 있는 질문으로, 답변의 근거 품질은 인용 대조와 별도 평가로 살펴봅니다. 판단을 재검토할 수 있도록 사실, 가설, 확인할 데이터를 구분합니다. [동작 원리와 설계](docs/how-it-works.md)

서비스 구현은 [`debate_focus` 브랜치](https://github.com/woosukkk/MarketCouncil/tree/debate_focus)에서 관리합니다.
