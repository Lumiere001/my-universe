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
