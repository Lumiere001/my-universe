"use client";
// 결과 카드: 별지기 한마디 → 닿은 순간 → 글 정보 → 생각 목록 → 이어진 지난 생각 → 사람 질문 → 다음 질문 → 불편한 점 한 줄.
// 위기(crisis)면 평소 결과 대신 돌봄 화면만 보인다.
import Link from "next/link";
import { useState } from "react";
import { answerPersonQuestion, sendFeedback, type EntryResult, type Feedback } from "@/lib/api";
import { useKindName } from "@/lib/use";

const CONFLICT = new Set(["긴장", "어긋남", "목표 충돌"]);
const day = (iso: string) => iso.slice(0, 10);
// 인용에 따옴표가 이미 붙어 오면 떼고 화면에서 한 번만 감싼다(“"…"” 방지)
export const unquote = (s: string) => s.trim().replace(/^["“'‘](.*)["”'’]$/s, "$1");

// 한 묶음의 피드백 버튼. 하나를 누르면 그 묶음은 닫힌다.
export function FeedbackButtons({ label, target, targetId, values, onDone }:
  { label: string; target: Feedback["target"]; targetId?: string | null; values: string[]; onDone?: (v: string) => void }) {
  const [sent, setSent] = useState<string | null>(null);
  const [err, setErr] = useState("");
  const send = async (value: string) => {
    setErr("");
    try { await sendFeedback({ target, target_id: targetId ?? null, value }); setSent(value); onDone?.(value); }
    catch { setErr("보내지 못했어요. 다시 눌러 주세요."); }
  };
  return (
    <div className="row" role="group" aria-label={label}>
      {values.map((v) => (
        <button key={v} className="small" aria-pressed={sent === v} disabled={!!sent} onClick={() => send(v)}>{v}</button>
      ))}
      {sent && <span className="toast" role="status">고마워요, 반영할게요.</span>}
      {err && <span className="err" role="alert">{err}</span>}
    </div>
  );
}

export function OneLine({ target, targetId }: { target: Feedback["target"]; targetId?: string | null }) {
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    await sendFeedback({ target, target_id: targetId ?? null, value: "불편한 점 한 줄", text: text.trim().slice(0, 200) });
    setDone(true);
  };
  if (done) return <p className="toast" role="status">불편한 점을 받았어요. 고칠 곳을 찾아볼게요.</p>;
  return (
    <form onSubmit={submit} className="row" aria-label="불편한 점 한 줄">
      <div style={{ flex: "1 1 220px" }}>
        <label htmlFor={"one-" + targetId}>불편한 점 한 줄</label>
        <input id={"one-" + targetId} maxLength={200} value={text} onChange={(e) => setText(e.target.value)} placeholder="예: 생각을 잘못 나눴어요" />
      </div>
      <button type="submit" className="small" style={{ alignSelf: "flex-end" }}>보내기</button>
    </form>
  );
}

export function CareCard({ r }: { r: EntryResult }) {
  return (
    <section className="care stack" aria-label="돌봄" data-testid="care">
      <div className="voice"><span className="who" aria-hidden>별</span><div className="bubble"><p>{r.care?.message}</p></div></div>
      {r.care?.resources.map((x) => (
        <div key={x.name}>
          {/^\d+$/.test(x.contact)
            ? <a className="call" href={`tel:${x.contact}`}>{x.name} {x.contact}{x.hours ? ` (${x.hours})` : ""}</a>
            : <p><b>{x.name}</b><br />{x.contact}{x.hours ? ` (${x.hours})` : ""}</p>}
        </div>
      ))}
      <p className="sub">지금 위험하다면 112 · 119로도 바로 연락할 수 있어요.</p>
    </section>
  );
}

export default function ResultCard({ r }: { r: EntryResult }) {
  const kindName = useKindName();
  const [vows, setVows] = useState<Record<string, string>>({});
  const [answered, setAnswered] = useState<Record<string, string>>({});
  if (r.crisis) return <CareCard r={r} />;

  const thought = (id: string) => r.thoughts.find((t) => t.id === id);
  const past = (id: string) => r.past.find((p) => p.thought_id === id);
  const m = r.message;

  return (
    <div data-testid="result">
      {m && m.text && (
        <section className="card stack" aria-label="별지기 한마디">
          <div className="voice">
            <span className="who" aria-hidden>별</span>
            <div>
              <div className="sub">별지기 · {m.tone}{m.mode === "comfort" ? " · 오늘은 위로만" : ""}</div>
              <div className="bubble"><p style={{ margin: 0 }}>{m.text}</p></div>
            </div>
          </div>
          <FeedbackButtons label="한마디 피드백" target="message" targetId={r.id} values={["좋아요", "별로", "오늘은 위로만"]} />
          <FeedbackButtons label="말의 세기" target="message" targetId={r.id} values={["오늘은 살살"]} />
        </section>
      )}

      {r.reached.map((x) => (
        <section key={x.aspiration_id + x.quote} className="card" aria-label="되고 싶은 모습에 닿은 순간">
          <span className="badge g">북극성에 닿은 순간</span>
          <p className="quote" style={{ borderColor: "var(--gold)" }}>“{unquote(x.quote)}”</p>
          <p style={{ margin: 0 }}>{x.message}</p>
        </section>
      ))}

      {r.info && (
        <section className="card" aria-label="글 정보">
          <h2>{r.title || "오늘의 글"}</h2>
          <p className="sub">{day(r.written_at)}{r.weather ? ` · 마음 날씨 ${r.weather}` : ""} · 말 거는 대상: {r.info.addressee}</p>
          <p>{r.info.summary}</p>
          {r.info.events.length > 0 && <p className="sub" style={{ margin: 0 }}>있었던 일: {r.info.events.join(" · ")}</p>}
        </section>
      )}

      {r.thoughts.length > 0 && (
        <section className="card stack" aria-label="생각 목록">
          <h2>생각 {r.thoughts.length}개</h2>
          {r.thoughts.map((t) => (
            <article key={t.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
              <div className="row">
                <span className="badge v">{kindName(t.kind)}{t.kind === "기타" && t.other ? `: ${t.other}` : ""}</span>
                {t.grateful && <span className="badge g">감사</span>}
                <span className="badge">{t.certainty}</span>
                {t.value && <span className="badge">가치 · {t.value}</span>}
                <span className="badge">{t.topic}</span>
              </div>
              <p style={{ margin: "6px 0 0" }}>{t.text}</p>
              <p className="quote">“{unquote(t.quote)}”</p>
              {t.self_change && <p className="sub" style={{ margin: 0 }}>스스로 쓴 변화: {t.self_change}</p>}
              {t.state?.type === "다짐" && (
                <div className="stack" style={{ marginTop: 8 }}>
                  <span className="sub">금빛 고리 · 다짐 {vows[t.id] ?? t.state.status}{t.state.mistake ? " · 실수 표시" : ""}</span>
                  {t.state.status === "열림" && !vows[t.id] && (
                    <FeedbackButtons label="다짐 상태" target="vow" targetId={t.id} values={["지켰어요", "그만둘래요"]}
                      onDone={(v) => setVows({ ...vows, [t.id]: v === "지켰어요" ? "지켜짐" : "그만둠" })} />
                  )}
                </div>
              )}
            </article>
          ))}
        </section>
      )}

      {r.relations.length > 0 && (
        <section className="card stack" aria-label="이어진 지난 생각">
          <h2>지난 생각 {r.relations.length}개와 이어졌어요</h2>
          {r.relations.map((rel) => {
            const p = past(rel.from), t = thought(rel.to), c = CONFLICT.has(rel.type);
            return (
              <article key={rel.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
                <div className="row">
                  <span className={"badge " + (c ? "o" : "v")}>{rel.type}</span>
                  <span className="badge">{rel.line === "실선" ? "실선 · 글에 직접 씀" : "점선 · AI 추정"}</span>
                  {rel.cross_domain && <span className="badge">다른 영역</span>}
                </div>
                {p && <p className={"quote" + (c ? " o" : "")}>그때 {day(p.written_at)}: “{unquote(rel.quote ?? p.text)}”</p>}
                {t && <p className={"quote" + (c ? " o" : "")}>지금: “{unquote(t.quote)}”</p>}
                <p className="sub">{rel.explanation}</p>
                {rel.line === "점선" && rel.needs_confirm && (
                  <FeedbackButtons label="이 연결이 맞나요" target="relation" targetId={rel.id} values={["맞아요", "아니에요"]} />
                )}
              </article>
            );
          })}
        </section>
      )}

      {r.people_questions.map((q) => (
        <section key={q.id} className="card stack" aria-label="사람 질문">
          <p style={{ margin: 0 }}>{q.question}</p>
          {answered[q.id] ? <p className="toast" role="status">“{answered[q.id]}”로 기억할게요.</p> : (
            <div className="row" role="group" aria-label={q.name + " 확인"}>
              {q.options.map((o) => (
                <button key={o} className="small" onClick={async () => { await answerPersonQuestion(q.id, o); setAnswered({ ...answered, [q.id]: o }); }}>{o}</button>
              ))}
            </div>
          )}
        </section>
      ))}

      {r.next_question && r.next_question.kind !== "none" && (
        <section className="card" aria-label="다음 질문">
          <div className="voice">
            <span className="who" aria-hidden>별</span>
            <div className="bubble">
              <p style={{ margin: 0 }}>{r.next_question.text}</p>
              {r.next_question.kind === "aspiration" && <p style={{ margin: "8px 0 0" }}><Link href="/aspiration">되고 싶은 모습 적어 보기</Link></p>}
              {r.next_question.kind === "weather" && <p className="sub" style={{ margin: "8px 0 0" }}>다음 글을 쓸 때 마음 날씨를 골라 주세요. 고르지 않아도 괜찮아요.</p>}
            </div>
          </div>
        </section>
      )}

      <section className="card" aria-label="불편한 점">
        <OneLine target="entry" targetId={r.id} />
      </section>
    </div>
  );
}
