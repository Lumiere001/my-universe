"use client";
// 저장 뒤 화면(PRD v9 Q16 · Q18): 별지기 한마디(짧게) + 좋아요 · 별로, '⋯' 안에 오늘은 위로만 · 오늘은 살살.
// 확인 카드는 한 번에 하나씩 — 답하면 다음 것이 그 자리에 뜬다. 순서: 사람 이름(가명 처리) → 다짐 → AI 가 추정한 연결.
// '다음에 할게요'로 멈추면 남은 연결 확인은 우주 · 흐름 카드의 점선 옆에 그대로 남는다. 직접 쓴 날의 숨은 이유 한 줄(Q7)도 여기.
import { useEffect, useState } from "react";
import { useKeeperName } from "@/components/Keeper";
import { PushAsk } from "@/components/PushSetting";
import { FeedbackButtons, unquote } from "@/components/ResultCard";
import { answerPersonQuestion, getMe, sendFeedback, why, type EntryResult } from "@/lib/api";

const PRE = { whiteSpace: "pre-line" } as const;
type Check = { id: string; ask: string; quote?: string; options: string[]; send: (v: string) => Promise<unknown> };

export function checksOf(r: EntryResult): Check[] {
  const thought = (id: string) => r.thoughts.find((t) => t.id === id);
  return [
    ...r.people_questions.map((q) => ({ id: q.id, ask: q.question, options: q.options, send: (v: string) => answerPersonQuestion(q.id, v) })),
    ...r.thoughts.filter((t) => t.state?.type === "다짐" && t.state.status === "열림").map((t) => ({
      id: t.id, ask: "이 다짐은 어떻게 됐어요?", quote: t.text, options: ["지켰어요", "그만둘래요"],
      send: (v: string) => sendFeedback({ target: "vow", target_id: t.id, value: v }) })),
    ...r.relations.filter((x) => x.line === "점선" && x.needs_confirm).map((x) => ({
      id: x.id, ask: `이 생각, 지난 생각과 ${x.type} 사이로 이어져 있나요?`, quote: thought(x.to)?.text ?? x.explanation, options: ["맞아요", "아니에요"],
      send: (v: string) => sendFeedback({ target: "relation", target_id: x.id, value: v }) })),
  ];
}

export default function AfterSave({ r, reason, children }: { r: EntryResult; reason?: string; children?: React.ReactNode }) {
  const keeper = useKeeperName();
  const checks = checksOf(r);
  const [i, setI] = useState(0);
  const [stop, setStop] = useState(false);
  const [err, setErr] = useState("");
  const [first, setFirst] = useState(false);   // 첫 일기 → 알림 켜기 안내(PRD v9 Q13)
  useEffect(() => { getMe().then((me) => setFirst(me.onboarding.entries <= 1), () => setFirst(false)); }, [r.id]);
  const m = r.message;
  const c = checks[i];
  const answer = async (v: string) => {
    setErr("");
    try { await c.send(v); setI(i + 1); } catch (e) { setErr(why(e, "보내지 못했어요. 다시 눌러 주세요.")); }
  };

  return (
    <section className="after stack" aria-label="저장했어요" data-testid="after-save">
      {m?.text && (
        <div className="voice" data-testid="saved-message">
          <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
          <div style={{ minWidth: 0, flex: 1 }}>
            <div className="bubble"><p style={{ margin: 0, ...PRE }}>{m.text}</p></div>
            {m.check_in && <p className="sub" style={{ margin: "6px 0 0", ...PRE }}>{m.check_in}</p>}
            <div className="row" style={{ marginTop: 6, flexWrap: "nowrap" }}>
              <FeedbackButtons label="한마디 피드백" target="message" targetId={r.id} values={["좋아요", "별로"]} />
              <details className="pop">
                <summary aria-label="한마디 더 보기">⋯</summary>
                <div className="stack">
                  <FeedbackButtons label="오늘은 위로만" target="message" targetId={r.id} values={["오늘은 위로만"]} />
                  <FeedbackButtons label="말의 세기" target="message" targetId={r.id} values={["오늘은 살살"]} />
                </div>
              </details>
            </div>
          </div>
        </div>
      )}
      {reason && <p className="sub reason" style={{ margin: 0 }} data-testid="reason-line">{reason}</p>}

      {c && !stop && (
        <div className="card stack check-card" aria-label="확인할 것" data-testid="check-card">
          <div className="row" style={{ justifyContent: "space-between" }}>
            <b>{c.ask}</b>
            {checks.length - i > 1 && <span className="sub">남은 확인 {checks.length - i - 1}개</span>}
          </div>
          {c.quote && <p className="quote" style={{ margin: 0 }}>“{unquote(c.quote)}”</p>}
          <div className="row">
            {c.options.map((o) => <button key={o} className="small" onClick={() => answer(o)}>{o}</button>)}
            <button className="small link" onClick={() => setStop(true)}>다음에 할게요</button>
          </div>
          {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
        </div>
      )}
      {(!c || stop) && <PushAsk first={first} />}
      {children}
    </section>
  );
}
