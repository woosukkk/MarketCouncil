import React from 'react';
export default function GettingStarted({session,onLogin}) {
 return <section className="getting-started"><span className="eyebrow">START YOUR RESEARCH</span><h2>내 분석을 시작하는 순서</h2><div className="start-steps"><article><span>01</span><h3>내 공간 만들기</h3><p>로그인하면 관심기업과 개인 분석을 본인 계정에 보관합니다.</p>{session?<strong>계정 연결 완료</strong>:<button className="primary" onClick={onLogin}>로그인하기</button>}</article><article><span>02</span><h3>PC에서 분석하기</h3><p>프로그램에서 API 키와 기업명을 입력하세요. 로컬 분석은 로그인 없이 가능합니다.</p><a href="/download">설치·사용 안내 →</a></article><article><span>03</span><h3>내 결과 가져오기</h3><p>아래에서 분석 JSON 파일을 업로드하세요. 처음에는 본인만 볼 수 있으며 공유 여부는 직접 선택합니다.</p></article></div></section>;
}
