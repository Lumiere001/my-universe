# Studio 설정 2판 — 1판 대비 비교 (WS2)

```
RECORD_CONFIG_ID=2 · OBSERVE_CONFIG_ID=2(새 백엔드 env 이름은 V8_RECORD_CONFIG_ID · V8_OBSERVE_CONFIG_ID)
```

**상태 (2026-10-08 밤):** 두 에이전트 모두 Studio에 2판을 가져와 config #2로 확정했고, 하늘 29편 전체를 2판으로 돌려 아래 표를 채웠다(`runs/studio_v2_result.json`, 걸린 시간 1574.8초). 1판 "1"은 Streamlit 데모가 계속 쓴다(`.env`의 `RECORD_CONFIG_ID=1`은 그대로).

## 만든 것

| 파일 | 내용 |
| --- | --- |
| `tools/studio_make_configs.py` | v8.json → `agent_configs/Record Agent v2.json` · `Observe Agent v2.json`. 1판 파일(Studio 가 내보낸 `studio.workflow-config-draft`, schemaVersion 3)을 틀로 갈래 · 칸만 바꾼다. 1판 설정 번호(configId · configVer)는 지워서 #1 을 덮어쓰지 않게 했다 |
| `app/service/studio_format.py` | 순수 함수 `record_html` · `parse_record` · `observe_html` · `parse_observe` (WS5 LangGraph 도구가 그대로 씀) |
| `tools/studio_run_v2.py` | `v1`(1판 결과를 잼, 읽기만) · `dry`(입력 HTML 만) · `run`(유료, 원장 기록) |
| `tests/test_studio_format.py` | 설정 파일 = 생성기 결과, 칸 · 목록 · 뜻풀이 · 금지 규칙, 입출력 성공 · 금지 사례 |

## 1판 → 2판에서 바뀐 점

**기록 Agent**
- 글 정보 7칸 → 3칸(요약 · 말 거는 대상 · 사건). 계기 · 다루는 기간 · 참고한 것 · 등장 관계 삭제(쓰는 곳 없음).
- 생각 표 7칸 → 8칸: `people`(사람) 추가. 이름 · 호칭을 그대로 쓰고 쉼표로 나눈다. 실제 서비스에서는 가명(사람1 …)이 들어온다.
- 종류 6 → 9(소망 · 자기평가(부정) · 자기평가(긍정) · 기타 추가, 반성 → 자기평가(부정)). 정의와 함께 **경계 문장**까지 넣었다. 감사는 `감정(감사)`로 쓰게 했다.
- 확신: `질문` → `판단 보류`, 강조어('정말 · 진짜 · 확실히')로 단정을 매기지 않는다는 규칙.
- 가치: 이름 10개 → **Schwartz 뜻풀이 10개**, 드러나지 않으면 비움.
- 목록 밖 값: 뜻이 하나면 바로잡고 애매하면 `기타(원래 말)`로 쓰게 했다. `parse_record`가 `기타` + `<칸>_original`로 나눈다(뜻 바로잡기는 WS3 rules 몫).
- 주제 2판: 삶의 영역 수준 → **해 이름보다 한 단계 구체적**, 해 이름 9개를 금지 목록으로 넣음, 한 번의 행동 금지, 입력의 "참고: 기존 작은 별" 목록에 맞는 이름이 있으면 그대로 재사용.

**관측 Agent**
- 관계 6개를 v8 정의 + 규칙(판단형 = 같은 주제 안에서만, 영향형 = 근거가 있으면 영역을 넘음)으로 설명.
- **거짓 별자리 줄이기:** "두 생각이 같은 대상(같은 일 · 같은 사람 · 같은 결정)을 직접 말할 때만 관계". `same_target`(함께 말하는 대상) 칸을 새로 두고 "못 쓰면 관계를 만들지 않는다"고 했다. 코드가 빈 `same_target`을 거를 수 있다.
- `evidence` 칸: 원문 인용 그대로. 영역을 넘는 두 생각이면 v8 `cross_domain` 조건(같은 글: 이어 쓴 흐름 + 인용 / 다른 날: 원문 설명 + 점선)을 따른다.
- 같은 쌍 하나 · 우선순위 · 감정끼리 바뀜 · 해소 금지.
- **되고 싶은 모습에 닿은 순간** `reached` 표(thought_id · quote · note): 원문 근거로만, 멀어진 순간은 찾지 않고 거리 · 점수는 쓰지 않는다. 입력 HTML 에 "되고 싶은 모습" 절을 더했다.
- 입력 줄에 주제와 함께 **해(영역)** 를 넣어, 영역을 넘는지 Agent 가 알 수 있게 했다.

## 비교표 (하늘 가상 데이터 29편)

1판 숫자는 `uv run --frozen python tools/studio_run_v2.py v1`(`output/records.json`, `data/ops/eval_virtual.json` 읽기만)로 다시 쟀다. 1판 결과는 다시 돌리지 않았다.

| 측정 | 1판 (config #1) | 2판 (config #2) |
| --- | --- | --- |
| 생각 수 | 61 | 72 |
| 종류 분포 | 다짐 17 · 해석 16 · 감정 9 · 신념·원칙 8 · 질문 6 · 반성 5 | 해석 22 · 다짐 17 · 신념·원칙 8 · 감정 8 · 질문 7 · 자기평가(부정) 5 · 소망 3 · 기타 2 |
| v8 목록 밖 종류 | 5 (`반성` = v7 이름) | 0 |
| 원문 인용 대조 실패(G1) | 0 | 0 |
| 주제 수 | 10 | 13 (+ 빈 주제 1) |
| 해 이름을 쓴 주제 | 3 (건강 · 공동체 · 관계) | 1 (건강). 가치 이름 `배려`를 주제로 쓴 것 1 |
| 관계 수(전체 / 다른 글끼리) | 43 / 38 | 64 / 48 |
| 설계 밖 관계(다른 글끼리) | 30 | 33 |
| 거짓 별자리 비율 | 약 1/3 (설계 밖 31개를 눈으로 봄, MVP 인수인계) | 아직 눈으로 안 봄. `same_target` 빈 관계는 0개(Agent가 늘 채워서 코드 거르기로는 줄지 않음) |
| 정답(expected.json) 짝 / 종류 | 8/8 · 7/8 (긴장 4/5→4/12 놓침) | 8/8 · 7/8 (같은 긴장 4/5→4/12를 바뀜으로 읽음) |
| 금지 관계 위반 | 0 | 0 |
| 시간(평균) | 기록 30.7초 · 관측 31.8초 | 기록 27.9초 · 관측 30.6초 (29편 전체 1574.8초) |
| 비용 | 81회 $4.05 (편당 $0.14) | 54회 $2.70 (편당 약 $0.09) |

주의: 1판은 생각이 주제 낱말 · 영역 유사도로 고른 지난 생각과 비교됐고, 2판 실행기는 "같은 세부 주제 먼저, 그다음 최근 순, 10개까지"로 고른다(`ponytail:` 표시, WS3 고르기가 나오면 바꿈). 관계 수 차이에 이 차이가 섞인다.

## 2판 돌리는 순서 (동규)

1. Studio 에서 두 에이전트에 2판을 가져와 #2 로 확정(아래 "Studio 화면 경로").
2. 원장 합계 확인: `python3 -c "import json;print(sum(json.loads(l)['est_usd'] for l in open('/Users/east_star/Projects/my-universe/runs/cost_ledger.jsonl') if l.strip()))"`
3. worktree 루트에 `.env` 연결(`ln -sf /Users/east_star/Projects/my-universe/.env .env`) 뒤, 형식 확인 2편:
   `RECORD_CONFIG_ID=2 OBSERVE_CONFIG_ID=2 uv run --frozen python tools/studio_run_v2.py run --limit 2`
   (`RECORD_AGENT_ID` · `OBSERVE_AGENT_ID` 는 `.env` 에서 읽는다. 실행기는 `.env` 를 고치지 않는다.)
4. 출력이 괜찮으면 29편 전부: `... run` → `runs/studio_v2_result.json` 의 숫자로 위 표 2판 칸을 채운다.

### Studio 화면 경로

1. https://studio.upstage.ai → 조직 **Default Organization** → 에이전트 목록에서 **나의 우주 기록 Agent**(`agt_gomJkjwWbZ7LkLPh2LSdtC`).
2. 설정(Config) 메뉴 → **Import workflow config** → `agent_configs/Record Agent v2.json` 선택. 새 초안으로 열리는지 확인(설정 #1 은 그대로 두기).
3. 초안 확인: Classify 4갈래, Extract 칸 `summary · addressee · events · thoughts(8칸)`.
4. 샘플 글(`data/smoke-0920.html`, 하늘 9/20)로 **Run** → 초안이 **Config #2** 로 확정. 번호를 적는다.
5. **나의 우주 관측 Agent**(`agt_E8xfPQN6aXtn4F2piJVDes`)도 같은 방법: `agent_configs/Observe Agent v2.json`, 샘플 `data/smoke-observe.html`. Extract 칸 `state · summary · question · relations(9칸) · reached(3칸)`.
6. 확정한 설정을 내보내(export) `agent_configs/` 의 v2 파일과 비교하고, 이 문서 맨 위 config id 를 채운다.

## 남은 문제

- 2판은 관계가 더 많다(다른 글끼리 38 → 48, 설계 밖 30 → 33). `same_target`이 늘 채워져 코드로는 못 거른다. 설계 밖 33개를 눈으로 보고 거짓 별자리 비율을 재야 2판이 거짓 연결을 줄였는지 말할 수 있다. 실서비스에서는 WS3 관계 규칙(판단형은 같은 주제 안에서만, 다른 날은 점선)이 한 번 더 거른다.
- 빈 주제 1개, 가치 이름(`배려`)을 주제로 쓴 것 1개: 설명에 "가치 이름도 주제로 쓰지 않는다"를 더할지 3판 후보.
- 설명이 길다(종류 칸 약 930자, 관계 종류 칸 약 870자). Studio 칸 설명 길이 제한이 있으면 가져오기에서 걸릴 수 있다. 걸리면 경계 문장(`boundary`)을 빼고 다시 만든다.
- 관측 상태 `처음 쓰는 주제` 의 정의가 v8.json 에 없어 1판 설명을 그대로 쓴다.
- PRD §5.4 의 관측 `encouragement`(한마디) 칸은 넣지 않았다. 말 걸기는 WS7(Solar)이 만든다.
- 목록 밖 값 "뜻이 하나면 바로잡기"(예: 확실함 → 단정)는 v8.json 에 바꿈 표가 없어 WS3 rules 가 맡는다. `parse_record` 는 값을 그대로 둔다.

## Studio 에서 내보낸 #2 vs 저장소 v2 (2026-10-14)

동규가 Studio 에서 두 에이전트의 Config #2 를 내보냈다: `agent_configs/Record Agent v2.exported.json`(configId `cfg_WNf2RbyPzFj27XDHh28NXQ`, configVer 2) · `agent_configs/Observe Agent v2.exported.json`(`cfg_MMFH7sjBv2ohtJLS6CgjVE`, configVer 2). 저장소의 생성기 결과(`Record Agent v2.json` · `Observe Agent v2.json`)와 키 하나하나 견줬다.

| 항목 | 저장소 v2(생성기) | 내보낸 #2 |
| --- | --- | --- |
| `kind` | studio.workflow-config-draft | 같음 |
| `schemaVersion` | 3 | **4** |
| `exportedFrom` | workflowId · workflowName | + `configId` · `configVer: 2` |
| `exportedAt` | 2026-10-07 | 2026-10-14 |
| `workflowConfig` 전체 | | **같음** — Parse 설정, Classify 갈래(기록 4 · 관측 6)와 설명, Extract 칸 · 설명 글, 갈래 → Extract 연결, 표 배치까지 한 글자도 다르지 않음 |
| 모델 칸 | Parse `document-parse`, Classify · Extract(공통 칸 + 갈래별 칸) `""` | 같음(Studio 기본 전용 모델, 화면에 고르는 칸 없음) |

- 읽기: Studio 에 올라가 있는 #2 = 저장소 v2 그대로다. 그러니 2판 숫자(WS2 29편 · WS23 흔들림 · 거짓 연결 17/33)는 이 설정의 결과다. `schemaVersion` 4 는 Studio 내보내기 형식 번호가 오른 것뿐이고 키 구조는 같다.
- 3판 파일은 이 내보낸 #2 를 틀로 만든다(아래).

## 품질 3판 설정 (2026-10-14, 동규 '전부 추천대로')

설정 #2 거짓 연결(약함 + 틀림) 17/33 = 0.52, 틀림 10개 중 7개가 4/26 시(창작)에 붙은 관계(`docs/eval-v8.md` '설정 #2 거짓 연결 판정'). 3판 후보 규칙 셋을 Studio 설명과 코드 양쪽에 넣었다.

| 파일 | 내용 |
| --- | --- |
| `agent_configs/Record Agent v3.json` · `Observe Agent v3.json` | **3판 A**: 2판 + 규칙 ①②③, 모델 칸은 2판처럼 비움(Studio 기본) |
| `agent_configs/Record Agent v3b.json` · `Observe Agent v3b.json` | **3판 B**: A 와 같고 Classify · Extract 의 `modelName` 만 `solar-pro4`(Classify 칸, Extract 공통 칸, 갈래별 Extract 칸 모두. Parse 는 `document-parse` 그대로) |

틀 = 내보낸 #2(`kind` · `schemaVersion` 4 · `workflowConfig` 키 구조 그대로, 설정 번호 `configId` · `configVer` 만 지움 → 가져오면 새 초안). `tests/test_studio_format.py` 가 내보낸 #2 와 키 구조가 같은지, 모델 칸, 규칙 글을 확인하고, 파일 = 생성기 결과(`uv run --frozen python tools/studio_make_configs.py`)인지도 본다.

| 규칙 | 어디에 | 더한 것 |
| --- | --- | --- |
| ① 시 · 창작 글에는 관계를 잇지 않기 | 기록 Classify '창작' 갈래 설명 | "줄을 나눈 짧은 시 한 편(계절 · 비 · 꽃 · 풍경을 노래한 시)도 창작이다." |
| | 관측 Extract `relations` 설명 | "'글 유형: 창작'이 붙은 생각(시 · 가사 · 소설)은 어떤 생각과도 잇지 않는다(비유는 글쓴이의 생각이 아니다)." 관측 입력 줄에 `글 유형: 창작` 을 붙인다(`studio_format._line`, 창작일 때만) |
| | **코드(설정과 상관없이)** | `rules.filter_relations`: 글 유형 '창작' 생각에 닿는 관계는 버림("시 · 창작 글에는 관계를 잇지 않음"). 오늘 생각은 기록 Agent Classify 결과, 지난 생각은 `entries.record_type`(`tools.search_past`)에서 받는다. 생각 · 행성은 그대로 남는다 |
| ② 사건 서술은 생각에 넣지 않기 | 기록 Extract `thoughts` 설명 | "있었던 일만 적은 문장(예: '오늘 시험이 끝났다', '저녁에 친구를 만났다')은 생각이 아니라 사건(events)에 넣는다. 그 일에 대한 해석 · 판단 · 다짐 · 감정이 함께 적혀 있을 때만 생각으로 만든다." 예시는 평가 글(하늘)이 아닌 일반 문장 |
| ③ 가치 이름을 주제로 쓰지 않기 | 기록 Extract `topic` 설명 | "가치 이름(쓰지 않는다): 자율 / 도전 / 즐거움 / 성취 / 영향력 / 안정 / 규범 / 전통·신앙 / 배려 / 공익." |
| | 코드 | 이미 있음: `rules.match_topic` 이 '가치 이름' · '빈 주제'를 표시 → `graph.record_clean` 이 '기타 생각' 작은 별로 모음(2026-10-08 결정, `tests/test_graph_flow.py::test_value_or_empty_topic_goes_to_other_star`) |

코드 한 겹 시험: `tests/test_rules_relations.py::test_creative_record_never_links`, `tests/test_graph_flow.py::test_creative_record_gets_no_relations`(가짜 Studio 가 첫 글을 '창작'으로 → 둘째 글에서 그 생각을 지난 생각으로 고르되 관계는 0개, 관측 입력에 '글 유형: 창작'), 골든셋 `rl-14`. 규칙을 끄면 앞의 둘이 실패하고, 지난 생각에 글 유형을 넘기지 않아도 그래프 시험이 실패한다.

### 3판 가져오기 (동규)

위 "Studio 화면 경로"와 같다. 기록 Agent 에 `Record Agent v3.json` → 샘플 Run → 번호 확정, 이어서 `Record Agent v3b.json` → 번호 확정. 관측 Agent 도 `Observe Agent v3.json` · `v3b.json`. 네 번호를 알려 주면 아래 측정을 돈다. v3b 의 `solar-pro4` 는 화면에 고르는 칸이 없어 Studio 가 받아들이는지 모른다 — 확정 뒤 다시 내보내 `modelName` 이 남았는지 확인할 것(지워졌으면 B 는 A 와 같은 설정이다).

### 3판 측정 (유료, 번호를 받은 뒤)

```bash
uv run --frozen python tools/quality_v3.py dry                                                    # 글 수 · 예상 비용만
uv run --frozen python tools/quality_v3.py run --record-config 2 --observe-config 2 --tag v2      # 2판 기준선(같은 서비스 길)
uv run --frozen python tools/quality_v3.py run --record-config <A기록> --observe-config <A관측> --tag v3a
uv run --frozen python tools/quality_v3.py run --record-config <B기록> --observe-config <B관측> --tag v3b
uv run --frozen python tools/stability_v2.py --record-config <A기록>                               # 흔들림(B 도 같은 방법)
uv run --frozen python eval/labels.py links-score eval/results/<날짜>-links-<tag>.csv               # verdict 칸을 채운 뒤
```

- 길: 하늘 29편을 날짜 순으로 `app/agents/graph`(safety → names → 기록 → 지난 생각 → 관측 → 규칙 → 한마디 → 저장) 그대로, 로컬 Supabase · ChromaDB 의 시험 계정 `e2e@my-universe.test`(돌기 전에 비우고 하늘의 사람을 등록). 운영 DB · Chroma Cloud 를 가리키면 멈춘다. 실패한 글은 '이어서 하기' 한 번만 다시.
- 결과: `eval/results/<날짜>-quality-<tag>.json` — ① 관계 날것(관측 Agent 가 낸 그대로) · 화면(서비스 규칙을 지난 것)마다 설계 짝 · 종류, 금지 관계 위반, 설계 밖 수, 버린 이유 ② 생각 수 · 종류 · 글 유형 분포, '기타 생각' 수, 주제 수 ③ 첫 실행 실패 · 이어 하기 뒤 실패 · 오류 코드, 글 한 편 · 기록 · 관측 단계 시간(중앙값 · 90%), 호출 수 · 비용(runs 표). `-links-<tag>.csv` — 거짓 연결 판정 양식(설계 밖 다른 글끼리 날것 관계, `service` 칸 = '남음 → 종류' / '버림: 이유'). `links-score` 가 날것 거짓 연결률(2판 0.52 와 같은 잣대)과 화면에 나가는 것만의 거짓 연결률(`false_rate_shown`)을 함께 낸다.
- 2판 0.52 는 WS2 실행기(지난 생각을 '같은 주제 먼저 + 최근 순'으로 고름) 숫자라 서비스 길과 바로 견줄 수 없다 → 같은 명령으로 `v2` 기준선을 함께 낸다.
- **비용(판당):** Studio 58번(29편 × 기록 · 관측, 생각이 없는 글은 관측 없음) ≈ $2.90 + Solar 위기 · 한마디 · 임베딩 ≈ $0.06 → **약 $3.0**(다시 시도는 번당 $0.05, 판 상한 $4, 원장 누적 $45 넘으면 멈춤). 흔들림은 설정마다 Studio 9번 ≈ $0.45. v2 기준선 · v3a · v3b 세 판 + 흔들림 둘 ≈ $9.9(원장 지금 $6.98). 글마다 원장 `runs/cost_ledger.jsonl` 에 한 줄(갈래 `Q3`, 흔들림은 `Q3-흔들림`).

### 3판 결과 (2026-10-14)

Studio 확정 번호: 기록 #3 = 3판 A, #4 = 3판 B(`solar-pro4`, 견본 9/20 에서 Extract 결과가 모두 비어 재지 않음), 관측 #3 = 3판 A. 서비스 길 측정 결과는 `docs/eval-v8.md` '품질 3판': 3판 A 는 거짓 연결이 2판보다 나빠(날것 0.64 → 0.69, 화면 0.57 → 0.71) **운영 전환하지 않는다**(V8_* = 2 / 2 유지). 주된 원인은 기록 Agent 가 기존 작은 별 이름을 다른 일에 갖다 붙이는 것이고, 4판 후보는 그 주제 규칙이다.

## 품질 4판 설정 (2026-10-14)

3판 측정에서 거짓 연결의 주된 원인이 "기록 Agent 가 기존 작은 별 이름을 다른 일에 붙임"이었다(2판 틀림 20 중 10, 3판 A 19 중 17). 작은 별이 셋뿐일 때(3/14)도 일어나, 넘기는 목록이 길어서가 아니라 "맞는 이름이 있으면 다시 쓴다" 규칙 탓으로 보았다 → 서비스가 넘기는 기존 작은 별 목록(`graph.record_agent`, '기타 생각' 뺀 전부)은 그대로 둔다.

| 파일 | 3판 A 에서 바뀐 것 |
| --- | --- |
| `agent_configs/Record Agent v4.json` | 주제 칸: '맞는 이름이 있으면 다시 쓴다'(두 문장)를 빼고 "기존 작은 별 이름은 이 생각과 같은 일 · 같은 대상을 말할 때만 글자 그대로 다시 쓴다. 비슷한 영역이라는 이유로 다른 일에 붙이지 않는다(예: '아침 운동' 별이 있어도 식단 이야기는 새 이름, '이직 고민' 별이 있어도 시험 공부는 새 이름). 맞는 이름이 없으면 새 이름. 주제는 이름 하나만." 예시는 평가 글(하늘)이 아닌 문장. 나머지(①②③)는 3판 A 그대로 |
| `agent_configs/Observe Agent v4.json` | 관계 칸에 "주제 이름이 같아도 두 생각이 같은 일 · 같은 대상을 말하지 않으면 잇지 않는다(주제 이름은 기록 Agent 가 붙여 틀릴 수 있다)." 기록 Agent 가 또 잘못 붙여도 관측에서 한 번 더 막으려고. 기록만의 효과를 따로 보려면 관측은 #3 으로 |

코드(설정과 상관없이): `rules.one_topic` — 주제 칸에 이름을 쉼표로 여럿 쓴 값(2판 4/5 '독서노트 습관, 진로 선택, 혼자 있는 시간')을 생각 · 인용에 낱말이 가장 많이 나오는 이름 하나로(같으면 앞 이름). 앞 이름만 쓰면 그 사례가 '독서노트 습관'으로 다시 잘못 붙고, 새 작은 별로 두면 이름 셋을 이은 별이 생겨서다. 가운뎃점은 나누지 않는다('영성·신앙' · '학업·동아리'가 이름 하나). 시험 `tests/test_rules_topics.py::test_many_topics_become_one`, 골든셋 `cl-21`.

가져오기 · 측정: 기록 Agent 에 `Record Agent v4.json`(→ 번호 N), 관측 Agent 에 `Observe Agent v4.json`(→ M, 또는 #3) 을 가져와 확정한 뒤
`uv run --frozen python tools/quality_v3.py run --record-config N --observe-config M --tag v4` + `tools/stability_v2.py --record-config N`(약 $2.8 + $0.45). 비교 기준은 같은 날 2판 기준선(`eval/results/2026-10-14-quality-v2.json` · `-links-v2.csv`).

### 4판 결과 (2026-10-14)

Studio 확정: 기록 #5 = `Record Agent v4.json`, 관측 #4 = `Observe Agent v4.json`. 서비스 길 결과는 `docs/eval-v8.md` '품질 4판': 화면 거짓 연결 0.57 → 0.27 로 크게 줄었지만 작은 별이 13 → 25 개로 쪼개져 대표 바뀜(3/14 → 9/20)을 놓치고 맞는 관계도 26 → 23 이라 **지금은 운영 전환하지 않는다**(V8_* = 2 / 2). 다음은 쪼개짐을 막는 4b.

## 품질 4b 설정 (2026-10-14)

4판은 거짓 연결을 크게 줄였지만 작은 별이 13 → 25 개로 쪼개져 대표 바뀜(3/14 → 9/20)을 놓쳤다. 두 겹으로 막는다.

- **코드 `rules.pick_past`:** (운영 4판 합칠 때는 기본 끔 `NEAREST_OTHER_TOPIC = 0`, q5 에서 켜고 잼) 오늘 생각마다 다른 주제에서 가장 가까운 지난 생각 하나는 낙폭 자르기 · 운영 한도와 상관없이 남긴다. 4판 9/20 은 '마음이 무겁다'끼리(7/30, 유사도 0.91) 뒤의 큰 낙폭에서 다른 주제 후보가 모두 잘려, 변화 서술 "예전에는 대기업이 …"에 다른 주제 중 가장 가까운 3/14('안정이 제일')를 놓쳤다. 4판 로컬 벡터로 외부 호출 없이 다시 고르면 설계 관계의 정답 지난 글이 7/8 → 8/8(3/14 → 9/20 포함), 고르는 개수 평균 5.8 → 6.5. 시험 `tests/test_rules_past.py` 2개(규칙을 끄면 실패).
- **`agent_configs/Record Agent v4b.json`:** 4판 주제 칸의 "같은 일 · 같은 대상을 말할 때만 다시 쓴다" 바로 뒤에 "같은 결정 · 같은 고민을 이어 쓰는 생각(예: 몇 달째 이어지는 이직 고민)도 같은 대상이다. 그때는 표현이 조금 달라도 그 기존 별 이름을 다시 쓴다." 를 넣었다. '같은 대상'의 뜻을 넓히는 꼴이라 4판 규칙과 부딪치지 않고, 바로 뒤의 "비슷한 영역이라는 이유로 다른 일에 붙이지 않는다"는 그대로. 관측은 4판(#4) 그대로라 새 파일 없음.
- 측정(번호를 받은 뒤): `tools/quality_v3.py run --record-config <v4b> --observe-config 4 --tag v4b` + `tools/stability_v2.py --record-config <v4b>`, 약 $3.2. 코드 쪽 `pick_past` 변경은 이 측정에 함께 들어간다.

### 4b 결과 · 최종 권고 (2026-10-14)

Studio 확정: 기록 #6 = `Record Agent v4b.json`(관측 #4). 결과는 `docs/eval-v8.md` '품질 4b · 최종 권고': 4b 는 화면 거짓 연결 0.42 · 대표 바뀜 없음이라 **4판(기록 #5 · 관측 #4)으로 운영 전환을 권고**한다. 대표 바뀜은 관측 Agent 가 냈지만 "판단형은 같은 주제 안에서만" 규칙이 버린다(동규 결정 필요).

### q5 결과 (2026-10-14)

운영 4판(#5/#4) + q5 코드(작성자가 쓴 변화면 판단형이 다른 작은 별을 넘음 · 다른 주제 자리)로 다시 잼: 대표 바뀜은 나왔지만 화면 거짓 연결 0.44 라 **끔**(q5 코드는 합치지 않음). 이번 실행에서 q5 코드가 작용한 관계는 사실상 없었고(예외 0 · 자리 1), 4판과의 차이는 같은 설정의 흔들림이다. `docs/eval-v8.md` 'q5' 절.
