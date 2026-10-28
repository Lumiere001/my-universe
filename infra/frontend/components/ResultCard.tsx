"use client";
// 결과 카드(노트 한 장처럼, docs/DESIGN.md · 문구 docs/content/C-02). 한 화면에 가깝게(2026-10-28 동규):
// 별지기 한마디(+ 안부 한 줄 · 버튼 한 줄) → 글 정보(제목 · 날 · 마음 날씨 · 해 › 작은 별 · 요약) → 있을 때만 작은 알림(닿은 순간 · 넓어진 우주 · 사람 질문 · 다음 질문)
// → 나눠 보기: 생각 · 이어진 생각 · 같은 주제(같은 작은 별의 다른 기록) · 더 보기(관측 보고서 · 내려받기 · 불편한 점 한 줄) 중 하나만.
// 숨긴 칸도 그려 두어(hidden) 누른 버튼 · 적던 글이 칸을 옮겨도 남는다.
// 위기 글도 같은 카드다(시험 단계, 2026-10-08 동규): 따로 뜨는 화면 · 단체 안내 없이, 한마디 아래 안부 한 줄만.
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { answerPersonQuestion, exportDiary, sendFeedback, why, type EntryResult, type Feedback, type Universe } from "@/lib/api";
import { useKindName } from "@/lib/use";
import { DayFix, WeatherSkip } from "./EntryTools";
import { useKeeperName } from "./Keeper";
import { localToday } from "./EntryTools";
// 관측 보고서(WS15): '더 보기' 안에 관측 상태 · 한계 · 이 기록 JSON 내려받기.
import UniverseGrew, { universeOnce } from "./UniverseGrew";

const CONFLICT = new Set(["긴장", "어긋남", "목표 충돌"]);
const day = (iso: string) => iso.slice(0, 10);
const PRE = { whiteSpace: "pre-line" } as const;   // 요약 · 한마디의 줄바꿈을 그대로
// 다짐 상태: 서버 값 → 보이는 말(docs/content/C-02)
const VOW: Record<string, string> = { 열림: "진행 중", 지켜짐: "지켰어요", 그만둠: "그만뒀어요" };
// 받침 있으면 '으로'(ㄹ 받침은 '로'): “같은 사람”으로 · “나”로
const ro = (w: string) => { const c = (w.charCodeAt(w.length - 1) - 0xac00) % 28; return c > 0 && c !== 8 ? "으로" : "로"; };
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

// 보이는 글자가 하나라도 있나(서버 routes.py _visible 과 같은 규칙). 폭 없는 글자 · 한글 채움 문자 · 받아쓰기 자리표만이면 빈 글
const visible = (s: string) => /[^\s\p{Cc}\p{Cf}\u115f\u1160\u3164\uffa0\u2800\ufffc]/u.test(s);

export function OneLine({ target, targetId }: { target: Feedback["target"]; targetId?: string | null }) {
  const [text, setText] = useState("");
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!visible(text)) return setErr("불편한 점을 한 줄 적어 주세요.");
    setErr("");
    try { await sendFeedback({ target, target_id: targetId ?? null, value: "불편한 점 한 줄", text: text.trim().slice(0, 200) }); setDone(true); }
    catch { setErr("보내지 못했어요. 다시 보내 주세요."); }
  };
  if (done) return <p className="toast" role="status">불편한 점을 받았어요. 고칠 곳을 찾아볼게요.</p>;
  return (
    <form onSubmit={submit} className="row" aria-label="불편한 점 한 줄">
      <div style={{ flex: "1 1 220px" }}>
        <label htmlFor={"one-" + targetId}>불편한 점 한 줄</label>
        <input id={"one-" + targetId} maxLength={200} value={text} onChange={(e) => setText(e.target.value)} placeholder="예: 생각을 잘못 나눴어요" />
      </div>
      <button type="submit" className="small" style={{ alignSelf: "flex-end" }}>보내기</button>
      {err && <span className="err" role="alert">{err}</span>}
    </form>
  );
}

// JSON 내려받기(WS15): id 가 있으면 그 기록, 없으면 전체. 받은 JSON 을 파일로 저장한다(다른 사람 이름은 그대로).
export function DownloadJson({ id, label }: { id?: string; label: string }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const url = URL.createObjectURL(new Blob([JSON.stringify(await exportDiary(id), null, 2)], { type: "application/json" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `my-universe-${id ?? "all"}-${localToday()}.json`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (x) { setErr(why(x, "내려받지 못했어요. 잠시 뒤 다시 해 주세요.")); } finally { setBusy(false); }
  };
  return (
    <div className="row">
      <button type="button" className="small" disabled={busy} onClick={go}>{busy ? "파일을 만드는 중…" : label}</button>
      {err && <span className="err" role="alert">{err}</span>}
    </div>
  );
}

// 긴 원문 인용은 두 줄까지만 보이고 누르면 펼친다(짧으면 그냥 인용)
function Quote({ text, pre = "", c = false, gold = false }: { text: string; pre?: string; c?: boolean; gold?: boolean }) {
  const [open, setOpen] = useState(false);
  const cls = "quote" + (c ? " o" : "") + (gold ? " g" : "");
  const body = `${pre}“${unquote(text)}”`;
  if (body.length <= 60) return <p className={cls}>{body}</p>;
  return <button type="button" className={cls + " clamp"} aria-expanded={open} onClick={() => setOpen(!open)}>{body}</button>;
}

type Tab = "thoughts" | "links" | "same" | "more";

// onChange: 날짜를 고치면 고친 결과로 바꿔 그린다
export default function ResultCard({ r, onChange }: { r: EntryResult; onChange?: (r: EntryResult) => void }) {
  const kindName = useKindName();
  const keeper = useKeeperName();
  const [vows, setVows] = useState<Record<string, string>>({});
  const [answered, setAnswered] = useState<Record<string, string>>({});
  const [askErr, setAskErr] = useState<Record<string, string>>({});
  const [sel, setSel] = useState<[string, Tab] | null>(null);   // 고른 칸(다른 기록을 열면 처음 칸으로)
  const [uni, setUni] = useState<Universe | null>(null);
  const uid = useId();
  useEffect(() => { universeOnce().then(setUni, () => setUni(null)); }, [r.id]);

  const thought = (id: string) => r.thoughts.find((t) => t.id === id);
  const past = (id: string) => r.past.find((p) => p.thought_id === id);
  const m = r.message;
  const answer = async (id: string, o: string) => {
    setAskErr({ ...askErr, [id]: "" });
    try { await answerPersonQuestion(id, o); setAnswered({ ...answered, [id]: o }); }
    catch (e) { setAskErr({ ...askErr, [id]: why(e, "답을 보내지 못했어요. 다시 눌러 주세요.") }); }
  };
  // 이 기록이 도는 해 › 작은 별, 같은 작은 별의 다른 기록(최근 것부터). 우주를 읽은 뒤에만
  const me = uni?.planets.find((p) => p.id === r.id);
  const star = me && uni!.stars.find((s) => s.id === me.star_id);
  const sun = me && uni!.suns.find((s) => s.id === me.sun_id);
  const same = me ? uni!.planets.filter((p) => p.star_id === me.star_id && p.id !== r.id).sort((a, b) => b.written_at.localeCompare(a.written_at)) : [];

  const tabs = ([
    ["thoughts", `생각 ${r.thoughts.length}`, r.thoughts.length > 0],
    ["links", `이어진 생각 ${r.relations.length}`, r.relations.length > 0],
    ["same", `같은 주제 ${same.length}`, same.length > 0],
    ["more", "더 보기", true],
  ] as const).filter((x) => x[2]);
  const on = tabs.find((x) => sel?.[0] === r.id && x[0] === sel[1])?.[0] ?? tabs[0][0];
  const pane = (t: Tab) => ({ id: uid + t, hidden: on !== t });

  return (
    <div className="note rc" data-testid="result">
      <h1 className="sr">정리한 결과</h1>
      <p className="sr">이 글에서 찾은 생각과, 그 생각이 이어진 지난 기록을 원문 그대로 보여 드려요.</p>
      {m && m.text && (
        <section className="rc-voice" aria-label="별지기 한마디">
          <div className="voice">
            <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="sub">{keeper} · {m.tone}{m.mode === "comfort" ? " · 오늘은 위로만" : ""}</div>
              <div className="bubble"><p style={{ margin: 0, ...PRE }}>{m.text}</p></div>
              {m.check_in && <p className="sub" data-testid="check-in" style={{ margin: "6px 0 0", ...PRE }}>{m.check_in}</p>}
              <div className="row rc-fb">
                <FeedbackButtons label="한마디 피드백" target="message" targetId={r.id} values={["좋아요", "별로", "오늘은 위로만"]} />
                <FeedbackButtons label="말의 세기" target="message" targetId={r.id} values={["오늘은 살살"]} />
              </div>
            </div>
          </div>
        </section>
      )}

      {r.info && (
        <section className="rc-head" aria-label="글 정보">
          <h2>{r.title || "오늘의 글"}</h2>
          <p className="sub rc-props" data-testid="entry-day">
            {r.day ?? day(r.written_at)}{r.weather ? ` · 마음 날씨 ${r.weather}` : ""}{sun && star ? ` · ${sun.name} › ${star.name}` : ""} · 말 거는 대상: {r.info.addressee}
          </p>
          {r.day_check && <DayFix r={r} onFixed={onChange} />}
          <p style={{ margin: 0, ...PRE }}>{r.info.summary}</p>
          {r.info.events.length > 0 && <p className="sub" style={{ margin: "4px 0 0" }}>있었던 일: {r.info.events.join(" · ")}</p>}
        </section>
      )}

      {r.reached.map((x) => (
        <section key={x.aspiration_id + x.quote} className="rc-call g" aria-label="되고 싶은 모습에 닿은 순간">
          <p style={{ margin: 0 }}><span className="badge g">북극성에 닿은 순간</span> “{unquote(x.quote)}”</p>
          <p className="sub" style={{ margin: "2px 0 0" }}>{x.message}</p>
        </section>
      ))}

      <UniverseGrew r={r} />

      {r.people_questions.map((q) => (
        <section key={q.id} className="rc-call row" aria-label="사람 질문">
          <p style={{ margin: 0 }}>{q.question}</p>
          {answered[q.id] ? <p className="toast" role="status" style={{ margin: 0 }}>“{answered[q.id]}”{ro(answered[q.id])} 기억할게요.</p> : (
            <div className="row" role="group" aria-label={q.name + " 확인"} style={{ gap: 4 }}>
              {q.options.map((o) => (
                <button key={o} className="small" onClick={() => answer(q.id, o)}>{o}</button>
              ))}
              {askErr[q.id] && <span className="err" role="alert">{askErr[q.id]}</span>}
            </div>
          )}
        </section>
      ))}

      {r.next_question && r.next_question.kind !== "none" && (
        <section className="rc-call" aria-label="다음 질문">
          <div className="voice">
            <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <p style={{ margin: 0, ...PRE }}>{r.next_question.text}</p>
              {r.next_question.kind === "aspiration" && <p style={{ margin: "6px 0 0" }}><Link href="/aspiration">되고 싶은 모습 적어 보기</Link></p>}
              {r.next_question.kind === "weather" && <p className="sub" style={{ margin: "6px 0 0" }}>다음 글을 쓸 때 마음 날씨를 골라 주세요. 고르지 않아도 괜찮아요.</p>}
              {r.next_question.kind === "weather" && <WeatherSkip />}
            </div>
          </div>
        </section>
      )}

      <div className="seg rc-tabs" role="group" aria-label="나눠 보기">
        {tabs.map(([k, name]) => (
          <button key={k} type="button" className="small" aria-pressed={on === k} aria-controls={uid + k} onClick={() => setSel([r.id, k])}>{name}</button>
        ))}
      </div>

      {r.thoughts.length > 0 && (
        <section className="rc-pane" aria-label="생각 목록" {...pane("thoughts")}>
          {r.thoughts.map((t) => (
            <article key={t.id} className="rc-item">
              <p style={{ margin: 0 }}>
                <span className="badge v">{kindName(t.kind)}{t.kind === "기타" && t.other ? `: ${t.other}` : ""}</span>
                {t.grateful && <> <span className="badge g">감사</span></>} {t.text}
                {[t.certainty, t.value && `가치 · ${t.value}`, t.topic].filter(Boolean).map((x) => <span key={x} className="badge rc-meta">{x}</span>)}
              </p>
              <Quote text={t.quote} />
              {t.self_change && <p className="sub" style={{ margin: 0 }}>스스로 쓴 변화: {t.self_change}</p>}
              {t.state?.type === "다짐" && (
                <div className="row" style={{ marginTop: 4 }}>
                  <span className="sub">금빛 고리 · 다짐 {VOW[vows[t.id] ?? t.state.status] ?? t.state.status}{t.state.mistake ? " · 지키지 못한 날이 있었어요" : ""}</span>
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
        <section className="rc-pane links" aria-label="이어진 지난 생각" {...pane("links")}>
          {r.relations.map((rel) => {
            const p = past(rel.from), t = thought(rel.to), c = CONFLICT.has(rel.type);
            return (
              <article key={rel.id} className="rc-item">
                <div className="row" style={{ gap: 6 }}>
                  <span className={"badge " + (c ? "o" : "v")}>{rel.type}</span>
                  <span className="badge">{rel.line === "실선" ? "실선 · 글에 직접 씀" : "점선 · AI 추정"}</span>
                  {rel.cross_domain && <span className="badge">다른 영역</span>}
                  {p && p.entry_id !== r.id && <Link className="sub" href={`/history?id=${encodeURIComponent(p.entry_id)}`}>그때 글 열기</Link>}
                </div>
                {p && <Quote pre={`그때 ${day(p.written_at)}: `} text={rel.quote ?? p.text} c={c} />}
                {t && <Quote pre="지금: " text={t.quote} c={c} />}
                <p className="sub" style={{ margin: 0 }}>{rel.explanation}</p>
                {rel.line === "점선" && rel.needs_confirm && (
                  <FeedbackButtons label="이 연결이 맞나요" target="relation" targetId={rel.id} values={["맞아요", "아니에요"]} />
                )}
              </article>
            );
          })}
        </section>
      )}

      {same.length > 0 && (
        <section className="rc-pane" aria-label="같은 주제의 다른 기록" {...pane("same")}>
          <p style={{ margin: 0 }}><b>‘{star?.name}’의 다른 기록 {same.length}편</b></p>
          <p className="sub" style={{ margin: "2px 0 8px" }}>같은 작은 별(주제)에 모인 기록이에요. AI가 이어 준 연결은 아니에요.</p>
          <ul className="rc-list">
            {same.map((p) => (
              <li key={p.id}><Link href={`/history?id=${encodeURIComponent(p.id)}`}>{p.title || "제목 없는 글"}</Link> <span className="sub">{day(p.written_at)}</span></li>
            ))}
          </ul>
        </section>
      )}

      <div className="rc-pane" {...pane("more")}>
        {r.observation && (
          <section className="stack" aria-label="관측 보고서" data-testid="observation">
            <h2>관측 보고서</h2>
            <p className="sub" style={{ margin: 0 }}>이 글을 어떻게 읽었는지와, 그렇게 읽은 데서 알아 둘 점이에요.</p>
            <p style={{ margin: 0 }}>이 글의 흐름 <span className="badge v">{r.observation.state}</span></p>
            {r.observation.limits.length > 0 && (
              <div>
                <span className="sub">알아 둘 점</span>
                <ul className="sub" style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                  {r.observation.limits.map((x) => <li key={x}>{x}</li>)}
                </ul>
              </div>
            )}
            <DownloadJson id={r.id} label="이 기록 파일로 내려받기(JSON)" />
          </section>
        )}
        <section aria-label="불편한 점" style={{ marginTop: 16 }}>
          <OneLine target="entry" targetId={r.id} />
        </section>
      </div>
    </div>
  );
}
