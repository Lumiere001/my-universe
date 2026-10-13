// 가짜 데이터 모드(NEXT_PUBLIC_MOCK=1)의 운영 화면 숫자(WS22). 지어낸 숫자와 가상 인물의 가명 피드백뿐이다.
import type { OpsDigest, OpsFeedback, OpsSummary } from "./api";

const nd = (pairs: number, returned: number) => ({ pairs, returned, ratio: pairs ? Math.round((returned / pairs) * 1000) / 1000 : null });

export const summary: OpsSummary = {
  generated_at: "2026-10-20T09:00:00+09:00",
  users: { total: 6, active_7d: 4, operator_read: 3 },
  cost: { total_usd: 4.8312, month_usd: 1.2044, budget_usd: 50, used_ratio: 0.097, warn: false, over: false,
    by_step: { record_agent: 2.95, observe: 1.42, voice: 0.31, safety: 0.11, ops_summarize: 0.0412 } },
  runs: {
    count: 412,
    by_step: [
      { step: "safety", count: 59, avg_ms: 1840, fails: 0, est_usd: 0.11 },
      { step: "record_agent", count: 59, avg_ms: 38200, fails: 1, est_usd: 2.95 },
      { step: "observe", count: 58, avg_ms: 27400, fails: 2, est_usd: 1.42 },
      { step: "voice", count: 56, avg_ms: 4100, fails: 0, est_usd: 0.31 },
      { step: "save", count: 56, avg_ms: 210, fails: 0, est_usd: 0 },
    ],
    per_entry: { entries: 59, avg_s: 74.2, avg_usd: 0.0812 },
    recent: [
      { at: "2026-10-20T08:41:12+09:00", step: "save", ms: 190, calls: 0, est_usd: 0, code: null, config: "2/2", entry_id: "e_3f2a91c0d4b1" },
      { at: "2026-10-20T08:41:08+09:00", step: "voice", ms: 3920, calls: 1, est_usd: 0.0051, code: null, config: "2/2", entry_id: "e_3f2a91c0d4b1" },
      { at: "2026-10-20T08:40:41+09:00", step: "observe", ms: 26810, calls: 1, est_usd: 0.025, code: null, config: "2/2", entry_id: "e_3f2a91c0d4b1" },
      { at: "2026-10-19T23:02:55+09:00", step: "observe", ms: 180000, calls: 2, est_usd: 0.05, code: "studio_timeout", config: "2/2", entry_id: "e_9b01aa7c22e0" },
    ],
  },
  gates: { real_name_leak: 0, voice_runs: 56, voice_regenerated: 7, voice_regenerated_ratio: 0.125 },
  failures: { entries: 2, by_code: { studio_timeout: 1, llm_failed: 1 },
    run_errors: [{ step: "observe", code: "studio_timeout", count: 2 }, { step: "record_agent", code: "llm_failed", count: 1 }],
    recent: [{ entry_id: "e_9b01aa7c22e0", step: "past", code: "studio_timeout", at: "2026-10-19T23:02:55+09:00" }] },
  eval: [{ file: "2026-10-08-all.json", gate_ok: true, regressions: 0, passed: 130, total: 132, est_usd: 0 }],
  satisfaction: { yes: 18, no: 5, yes_ratio: 0.783,
    reactions: { "맞아요": 18, "아니에요": 5, "좋아요": 21, "별로": 4, "불편한 점 한 줄": 3, "지켰어요": 6, "그만둘래요": 1 },
    by_config: { "2/2": { "맞아요": 18, "아니에요": 5, "좋아요": 21, "별로": 4 } }, next_day: nd(31, 17) },
  direction: { multi_sun: { window_days: 14, users: 4, avg_suns: 2.25, share_2plus: 0.75, avg_suns_all: 3.5 }, closer_feeling: null },
  talk: { conversations: 12, avg_turns: 6.4, finished: 9, dropped: 2, drop_at: { "2": 1, "5": 1 },
    stop_after_suggestion: 0.08, stop_without_suggestion: 0.02, confirms: 9, edited_ratio: 0.14, confirms_with_edit: 0.44 },
  voice: { messages: 56, suggested_ratio: 0.41, repeat_ratio: 0.054, dislike_ratio: 0.071,
    next_day_with_suggestion: nd(14, 8), next_day_without_suggestion: nd(17, 9) },
  other_values: { thoughts: 231, kind: 4, certainty: 1, value: 2 },
  feedback_text: { consented: 3, not_consented: 1 },
};

export const feedback: OpsFeedback = {
  days: 30, wrong: false, users: 2,
  items: [
    { user: "사용자 1", at: "2026-10-19T22:14:03+09:00", target: "relation", value: "아니에요", text: null,
      target_text: "[바뀜] 혼자 다 해내야 책임감 있는 거다 → 같이 하는 게 더 낫다", config: "2/2" },
    { user: "사용자 1", at: "2026-10-19T22:15:40+09:00", target: "message", value: "불편한 점 한 줄",
      text: "다음 걸음을 너무 자주 권해서 숙제 같았어요", target_text: "오늘도 할 일을 정리했네요. 내일은 10분만 먼저 시작해 볼까요?", config: "2/2" },
    { user: "사용자 2", at: "2026-10-18T23:40:11+09:00", target: "message", value: "별로", text: null,
      target_text: "도윤 선배와 나눈 이야기가 힘이 됐겠어요.", config: "2/2" },
  ],
  other_candidates: [{ field: "kind", original: "회상", count: 3 }, { field: "addressee", original: "미래의 나", count: 1 }],
  not_consented: { "불편한 점 한 줄": 1, "별로": 2 },
};

export const digest: OpsDigest = {
  days: 30, users: 2, est_usd: 0.0012,
  lines: feedback.items.map((x) => `[${x.target} · ${x.value}] 대상: ${x.target_text ?? "-"} / 남긴 말: ${x.text ?? "-"}`),
  groups: [
    { reason: "설교 같음", items: [2], count: 1, fix_where: "말 걸기 규칙", suggestion: "제안은 질문형 한 번으로 줄이고, 연달아 권하지 않기" },
    { reason: "틀린 연결", items: [1], count: 1, fix_where: "관측 Agent", suggestion: "같은 주제 안에서만 '바뀜'을 잡는지 경계 설명 보강" },
  ],
};
