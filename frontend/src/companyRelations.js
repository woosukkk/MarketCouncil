// Dated editorial summaries of first-party announcements; no live supply estimates.
export const relationsAsOf='2026-11-05';
export const relationNodes=[
 {id:'AAPL',name:'Apple',x:13,y:22},
 {id:'005930.KS',name:'삼성전자',en:'Samsung Electronics',x:50,y:22},
 {id:'MSFT',name:'Microsoft',x:87,y:22},
 {id:'035420.KS',name:'NAVER',x:50,y:50},
 {id:'000660.KS',name:'SK하이닉스',en:'SK hynix',x:13,y:78},
 {id:'NVDA',name:'NVIDIA',x:50,y:78,reference:true},
 {id:'005380.KS',name:'현대자동차',en:'Hyundai Motor',x:87,y:78},
];
const supplierSource='https://www.supplychainreports.apple/Apple-Supplier-List';
const appleManufacturing='https://www.apple.com/newsroom/2025/08/apple-increases-us-commitment-to-600-billion-usd-announces-ambitious-program/';
export const companyRelations=[
 {id:'apple-samsung',from:'005930.KS',to:'AAPL',type:'development',period:'2025-08-06',
  evidence:[
   {url:appleManufacturing,source:'Apple Newsroom',locator:'2025-08-06 · U.S. silicon supply chain',excerpt:'working with Samsung at its fab in Austin, Texas',
    data:['텍사스 오스틴 팹 · 칩 제조 기술 협력 발표','Austin, Texas fab · chipmaking collaboration announced'],limit:['삼성과의 계약 금액, 양산 실적, 공급량은 공개하지 않았습니다.','Samsung-specific contract value, production results and volumes were not disclosed.']},
   {url:supplierSource+'#page=19',source:'Apple Supplier List',locator:'FY2023 · PDF p.19',excerpt:'Samsung Electronics Company Limited',
    data:['FY2023 공급업체 명단에 삼성전자 등재','Samsung Electronics listed as an FY2023 supplier'],limit:['오스틴 협력과 별개인 과거 공급망 기록입니다.','A historical supplier record, separate from the Austin announcement.']},
  ],
  fact:['Apple은 삼성과 텍사스 오스틴 공장에서 새 칩 제조 기술을 도입하기 위해 협력한다고 발표했습니다.','Apple announced work with Samsung at its Austin, Texas fab to introduce a chipmaking technology.'],
  upside:['기술이 양산으로 이어지고 실제 발주가 확인되면 삼성의 파운드리 매출에 기여할 수 있습니다.','A ramp to mass production and confirmed orders could support Samsung’s foundry revenue.'],
  downside:['인증·수율 문제로 양산이 지연되면 출하와 매출 기여도 늦어질 수 있습니다.','Qualification or yield issues could delay shipments and revenue contribution.'],
  needed:['양산 시작, 칩 종류, 수율, 확정 발주량과 계약 규모','Production start, chip type, yields, confirmed orders and contract value']},
 {id:'apple-hynix',from:'000660.KS',to:'AAPL',type:'supplier',period:'FY2023',historical:true,
  evidence:[
   {url:supplierSource+'#page=20',source:'Apple Supplier List',locator:'FY2023 · PDF p.20',excerpt:'SK hynix Incorporated',
    data:['중국 충칭·장쑤, 한국 충북·경기 소재 사업장이 명단에 기재','Listed sites in Chongqing, Jiangsu, Chungcheongbuk-do and Gyeonggi-do'],limit:['FY2023 등재 사실만 확인됩니다. 현재 공급 여부, 부품 종류, 공급량과 고객별 매출은 확인되지 않습니다.','The list confirms FY2023 inclusion. Current sourcing, components, volumes and customer revenue are unconfirmed.']},
  ],
  fact:['Apple의 FY2023 공급업체 목록에 SK하이닉스가 포함돼 있습니다.','Apple lists SK hynix among its FY2023 suppliers.'],
  upside:['기기당 메모리 용량과 발주가 함께 증가하면 수요 확대 경로가 될 수 있습니다.','Higher memory content and orders could create a demand channel.'],
  downside:['메모리 가격 하락이나 공급처 다변화가 수요 증가 효과를 상쇄할 수 있습니다.','Lower memory prices or supplier diversification could offset demand gains.'],
  needed:['최신 공급 관계, 제품별 메모리 채택, 가격과 고객 집중도','Current supplier relationship, memory adoption, pricing and customer concentration']},
 {id:'samsung-microsoft',from:'005930.KS',to:'MSFT',type:'integration',period:'2025-08-28',
  evidence:[
   {url:'https://news.samsung.com/global/samsung-brings-microsoft-copilot-2025-tvs-and-monitors-unlocking-smarter-on-screen-experiences',source:'Samsung Global Newsroom',locator:'2025-08-28 · footnote 1',excerpt:'M7, M8 and M9 Smart Monitors',
    data:['Copilot 적용 범위에 2025년형 M7·M8·M9 스마트 모니터 포함','2025 M7, M8 and M9 Smart Monitors included in Copilot availability'],limit:['모델·지역별 차이가 있으며 이용자 수나 계약 매출은 발표에 없습니다.','Availability varies by model and market. Usage and contract revenue are undisclosed.']},
  ],
  fact:['삼성전자는 일부 2025년형 TV·모니터에 Microsoft Copilot 통합을 발표했습니다.','Samsung announced Microsoft Copilot integration for selected 2025 TVs and monitors.'],
  upside:['실제 이용과 제품 차별화가 늘면 기기·AI 서비스 생태계에 도움이 될 수 있습니다.','Adoption and differentiation could support the device and AI service ecosystem.'],
  downside:['이용률 저조나 지역·모델별 제약으로 상업적 효과가 제한될 수 있습니다.','Low usage or regional and model restrictions could limit commercial impact.'],
  needed:['대상 모델·지역, 활성 이용자, 계약 조건과 수익 기여','Eligible models and regions, active users, commercial terms and revenue contribution']},
 {id:'samsung-naver',from:'005930.KS',to:'035420.KS',type:'development',period:'2022-12-06',historical:true,
  evidence:[
   {url:'https://www.navercorp.com/en/media/pressReleasesDetail?seq=30987',source:'NAVER Corp.',locator:'2022-12-06 · development scope',excerpt:'semiconductor solutions for hyperscale AI',
    data:['삼성의 메모리·반도체 역량과 NAVER의 AI 소프트웨어를 결합하는 개발 계획','Development plan combining Samsung memory and semiconductor capabilities with NAVER AI software'],limit:['2022년 협력 발표입니다. 공동 제품의 양산·성능과 매출 실현은 별도 확인이 필요합니다.','A 2022 announcement. Joint product deployment, performance and revenue require separate confirmation.']},
  ],
  fact:['삼성전자와 NAVER는 초대규모 AI용 반도체 솔루션 개발 협력을 발표했습니다.','Samsung Electronics and NAVER announced collaboration on semiconductor solutions for hyperscale AI.'],
  upside:['실증 성과가 상용화되면 AI 처리 효율과 인프라 비용 개선의 경로가 될 수 있습니다.','Commercialized results could improve AI processing efficiency and infrastructure costs.'],
  downside:['개발 지연이나 상용화 실패 시 기대한 효율 개선이 실현되지 않을 수 있습니다.','Development delays or failure to commercialize could prevent efficiency gains.'],
  needed:['최근 개발 단계, 상용 적용, 독립적인 성능·전력 측정','Recent development status, commercial deployment and independent performance/power measurements']},
 {id:'hynix-nvidia',from:'000660.KS',to:'NVDA',type:'development',period:'2026-06-08',
  evidence:[
   {url:'https://nvidianews.nvidia.com/news/sk-hynix-ai-factory',source:'NVIDIA Newsroom',locator:'2026-06-07 · News Summary',excerpt:'codeveloping memory for NVIDIA Vera Rubin AI supercomputers',
    data:['Vera Rubin·Vera CPU·RTX Spark·Jetson Thor용 메모리 공동 개발 계획','Memory development planned for Vera Rubin, Vera CPUs, RTX Spark and Jetson Thor'],limit:['다년 기술 협력 발표이며 제품별 확정 물량, 판매 단가, 매출 기여는 공개되지 않았습니다.','The multiyear announcement leaves product-level volumes, prices and revenue undisclosed.']},
  ],
  fact:['SK하이닉스와 NVIDIA는 차세대 메모리 공동 개발·공급을 위한 다년 기술 협력을 발표했습니다.','SK hynix and NVIDIA announced a multiyear technology partnership for next-generation memory development and supply.'],
  upside:['AI 인프라 투자가 실제 메모리 수요와 출하로 이어지면 성장 경로가 될 수 있습니다.','AI infrastructure investment could support growth if it converts to memory demand and shipments.'],
  downside:['투자 지연, 수율 문제나 고객 집중은 출하와 수익성의 위험 요인입니다.','Investment delays, yield issues and customer concentration are risks to shipments and margins.'],
  needed:['확정 출하, 수율, 계약 조건, 설비 투자와 고객 집중도','Confirmed shipments, yields, contract terms, capital spending and customer concentration']},
 {id:'hyundai-nvidia',from:'005380.KS',to:'NVDA',type:'development',period:'2026-03-16',
  evidence:[
   {url:'https://nvidianews.nvidia.com/news/hyundai-motor-kia-autonomous-driving',source:'NVIDIA Newsroom',locator:'2026-03-16 · News Summary / planned deployment',excerpt:'level 2+ deployment across select vehicles',
    data:['일부 차량 L2+ 적용 계획 및 Motional의 L4 로보택시 협력 모색','Plans for L2+ in select vehicles and exploration of L4 robotaxi work through Motional'],limit:['현대차·기아 협력 발표입니다. 현대차 단독 투자액, 전 차종 적용, 양산 완료는 확인되지 않습니다.','This is a Hyundai Motor and Kia announcement. Hyundai-only investment, fleet-wide adoption and production completion are unconfirmed.']},
  ],
  fact:['NVIDIA는 현대자동차·기아와 차세대 자율주행 기술 협력 확대를 발표했습니다. 그룹 전체 계획이 개별 회사의 실적을 뜻하지는 않습니다.','NVIDIA announced expanded autonomous-driving collaboration with Hyundai Motor and Kia. Group plans do not establish company-level earnings.'],
  upside:['양산 적용과 사용 확대가 확인되면 소프트웨어·차량 경쟁력에 도움이 될 수 있습니다.','Verified production deployment and adoption could support software and vehicle competitiveness.'],
  downside:['개발비, 안전·규제 승인과 상용화 일정은 실현 가능성에 영향을 줍니다.','Development cost, safety and regulatory approvals, and deployment schedules affect feasibility.'],
  needed:['현대자동차에 귀속되는 투자·계약, 대상 차종, 승인과 양산 일정','Hyundai-specific investment and contracts, eligible models, approvals and production timeline']},
];
export function relationsFor(ticker){return companyRelations.filter(row=>!ticker||row.from===ticker||row.to===ticker);}
