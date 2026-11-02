"use client";
// 일기 한 편 보기(일기장 → 한 편 · 우주 → 정리한 결과). 문구 원본 docs/content/C-02. 순서와 이유는 아래 ResultCard 주석.
// 위기 글도 같은 카드다(시험 단계, 2026-10-08 동규): 따로 뜨는 화면 · 단체 안내 없이, 한마디 아래 안부 한 줄만.
import Link from "next/link";
import { useEffect, useState } from "react";
import { answerPersonQuestion, exportDiary, sendFeedback, why, type EntryResult, type Feedback, type Universe } from "@/lib/api";
import { useKindName } from "@/lib/use";
import { DayFix } from "./EntryTools";
import { useKeeperName } from "./Keeper";
import { localToday } from "./EntryTools";
// 관측 보고서(WS15): '더 보기' 안에 관측 상태 · 한계 · 이 기록 JSON 내려받기.
import UniverseGrew, { universeOnce } from "./UniverseGrew";
import { Markdown } from "./WriteParts";

const CONFLICT = new Set(["긴장", "어긋남", "목표 충돌"]);
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

const FROM: Record<string, string> = { 대화: "별지기와 나눈 대화로 쓴 일기", 사진: "사진에서 읽은 일기", "지난 글 묶음": "가져온 일기", 텍스트: "직접 쓴 일기" };
// 관계 → 처음 보는 사람도 읽히는 한 문장(온톨로지 관계 여섯). d = 지난 일기 날('10월 1일'), 없으면 '지난'
const LINKED: Record<string, (d: string) => string> = {
  이어짐: (d) => `${d} 일기와 이어지는 생각이에요`, 바뀜: (d) => `${d} 일기 때와 생각이 바뀌었어요`, 해소: (d) => `${d} 일기의 고민이 오늘 풀렸어요`,
  긴장: (d) => `${d} 일기의 생각과 서로 당기고 있어요`, 어긋남: (d) => `${d} 일기에서 한 말과 오늘이 어긋나요`, "목표 충돌": (d) => `${d} 일기의 목표와 부딪혀요`,
};
const linked = (type: string, at?: string) => (LINKED[type] ?? ((d: string) => `${d} 일기와 ${type}`))(at ? shortDay(at) : "지난");
const SHOW = 3;   // 확인해 주세요: 처음엔 셋만(나머지는 '더 확인하기')
const longDay = new Intl.DateTimeFormat("ko-KR", { year: "numeric", month: "long", day: "numeric", weekday: "long" });
const shortDay = (iso: string) => `${+iso.slice(5, 7)}월 ${+iso.slice(8, 10)}일`;
const dayText = (d: string) => longDay.format(new Date(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)));

// 일기 한 편(2026-11-02 동규): ① 내가 쓴 원문(종이 · 손글씨, 대화로 쓴 날은 정리본 → '대화 전체 보기'를 눌러야 대화)
// → ② 별지기의 정리(요약 · 주제 · 한마디 · 찾은 생각 · 지난 기록과 이어진 곳 · 같은 주제) → ③ 확인해 주세요(헷갈린 것만).
// 처음 보는 사람도 읽히게 칸마다 '누가 만든 것인지'를 이름으로 밝히고, 내부 말(말 거는 대상 · 실선/점선)은 쓰지 않는다.
// onChange: 날짜를 고치면 고친 결과로 바꿔 그린다
export default function ResultCard({ r, onChange }: { r: EntryResult; onChange?: (r: EntryResult) => void }) {
  const kindName = useKindName();
  const keeper = useKeeperName();
  const [vows, setVows] = useState<Record<string, string>>({});
  const [answered, setAnswered] = useState<Record<string, string>>({});
  const [askErr, setAskErr] = useState<Record<string, string>>({});
  const [talk, setTalk] = useState<string | null>(null);   // 대화 전체를 펼친 기록 id
  const [all, setAll] = useState<string | null>(null);     // 확인할 것을 다 펼친 기록 id
  const [uni, setUni] = useState<Universe | null>(null);
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
  const openVows = r.thoughts.filter((t) => t.state?.type === "다짐" && t.state.status === "열림");   // 답하면 그 자리에 '고마워요'
  const guesses = r.relations.filter((x) => x.line === "점선" && x.needs_confirm);
  const checks = r.day_check || r.people_questions.length > 0 || openVows.length > 0 || guesses.length > 0;
  const day = r.day ?? r.written_at.slice(0, 10);
  // 확인할 것(사람 이름 → 다짐 → 짐작한 연결 순, 확신 낮은 것부터)
  const asks = [
    ...r.people_questions.map((q) => (
      <div key={q.id} className="rc-ask">
        <p>{q.question}</p>
        {answered[q.id] ? <p className="toast" role="status">“{answered[q.id]}”{ro(answered[q.id])} 기억할게요.</p> : (
          <div className="row" role="group" aria-label={q.name + " 확인"}>
            {q.options.map((o) => <button key={o} className="small" onClick={() => answer(q.id, o)}>{o}</button>)}
            {askErr[q.id] && <span className="err" role="alert">{askErr[q.id]}</span>}
          </div>
        )}
      </div>
    )),
    ...openVows.map((t) => (
      <div key={t.id} className="rc-ask">
        <p>이 다짐은 어떻게 됐어요? <span className="quote-inline">“{unquote(t.quote)}”</span></p>
        <FeedbackButtons label="다짐 상태" target="vow" targetId={t.id} values={["지켰어요", "그만둘래요"]}
          onDone={(v) => setVows({ ...vows, [t.id]: v === "지켰어요" ? "지켜짐" : "그만둠" })} />
      </div>
    )),
    ...guesses.map((rel) => {
      const p = past(rel.from);
      return (
        <div key={rel.id} className="rc-ask">
          <p>{linked(rel.type, p?.written_at)}. 맞나요?</p>
          {p && <Quote pre="그때 " text={rel.quote ?? p.text} />}
          <FeedbackButtons label="이 연결이 맞나요" target="relation" targetId={rel.id} values={["맞아요", "아니에요"]} />
        </div>
      );
    }),
  ];

  return (
    <div className="rc" data-testid="result">

      {/* ① 원문 */}
      <section aria-label="원문" className="stack">
        <article className="paper read">
          <p className="read-meta" data-testid="entry-day">{dayText(day)}{r.weather ? ` · ${r.weather}` : ""}</p>
          <h1>{r.title || "제목 없는 일기"}</h1>   {/* 종이 위 제목이 이 화면의 제목 */}
          {r.text !== undefined && <div className="read-text"><Markdown text={r.text} /></div>}
        </article>
        <div className="rc-src">
          <span className="sub">{FROM[r.source ?? "텍스트"] ?? r.source}</span>
          {r.source === "대화" && !!r.talk?.length && (
            <button type="button" className="small" aria-expanded={talk === r.id} onClick={() => setTalk(talk === r.id ? null : r.id)}>
              {talk === r.id ? "대화 접기" : "대화 전체 보기"}</button>
          )}
        </div>
        {talk === r.id && r.talk && (
          <section className="rc-talk" aria-label="그날 대화">
            {r.talk.map((t, i) => t.role === "user"
              ? <div key={i} className="bubble me"><p style={{ margin: 0, ...PRE }}>{t.text}</p></div>
              : <div key={i} className="voice"><span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
                  <div className="bubble"><p style={{ margin: 0, ...PRE }}>{t.text}</p></div></div>)}
          </section>
        )}
      </section>

      {/* ② 별지기의 정리 */}
      {(r.info || m?.text || r.thoughts.length > 0) && (
        <section className="rc-sec" aria-labelledby={`ai-${r.id}`}>
          <h2 id={`ai-${r.id}`}>{keeper}의 정리</h2>
          <p className="sub rc-who">이 일기를 읽고 {keeper}가 정리한 것이에요.</p>
          {r.info && <p className="rc-sum" style={PRE}>{r.info.summary}</p>}
          {sun && star && <p className="sub rc-topic">주제 · {sun.name} › {star.name}</p>}
          <UniverseGrew r={r} />
          {r.reached.map((x) => (
            <p key={x.aspiration_id + x.quote} className="rc-call g">되고 싶은 모습에 닿은 순간 · “{unquote(x.quote)}”<span className="sub"> {x.message}</span></p>
          ))}
          {m?.text && <KeeperWord text={m.text} checkIn={m.check_in} who={keeper} tone={m.tone} />}

          {r.thoughts.length > 0 && (
            <details className="rc-more">
              <summary>찾은 생각 {r.thoughts.length}개</summary>
              <ul aria-label="생각 목록">
                {r.thoughts.map((t) => (
                  <li key={t.id}>
                    <span className="badge v">{kindName(t.kind)}{t.kind === "기타" && t.other ? `: ${t.other}` : ""}</span> {t.text}
                    {t.self_change && <span className="sub"> · 스스로 쓴 변화: {t.self_change}</span>}
                    {t.state?.type === "다짐" && <span className="sub"> · 다짐 {VOW[vows[t.id] ?? t.state.status] ?? t.state.status}</span>}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {r.relations.length > 0 && (
            <details className="rc-more">
              <summary>지난 일기와 이어진 곳 {r.relations.length}곳</summary>
              <div aria-label="이어진 지난 생각">
                {r.relations.map((rel) => {
                  const p = past(rel.from), t = thought(rel.to), c = CONFLICT.has(rel.type);
                  return (
                    <article key={rel.id} className="rc-item">
                      <p className="rc-link">
                        <b className={c ? "o" : ""}>{linked(rel.type, p?.written_at)}</b>
                        {rel.line === "점선" && <span className="sub"> · {keeper}의 짐작</span>}
                      </p>
                      {p && <Quote pre="그때 " text={rel.quote ?? p.text} c={c} />}
                      {t && <Quote pre="오늘 " text={t.quote} c={c} />}
                      <p className="sub" style={{ margin: 0 }}>{rel.explanation}</p>
                      {p && p.entry_id !== r.id && <Link className="sub" href={`/history?id=${encodeURIComponent(p.entry_id)}`}>그날 일기 열기</Link>}
                    </article>
                  );
                })}
              </div>
            </details>
          )}
          {same.length > 0 && (
            <details className="rc-more">
              <summary>같은 주제의 다른 일기 {same.length}편</summary>
              <ul className="rc-list" aria-label="같은 주제의 다른 기록">
                {same.map((p) => (
                  <li key={p.id}><Link href={`/history?id=${encodeURIComponent(p.id)}`}>{p.title || "제목 없는 일기"}</Link> <span className="sub">{shortDay(p.written_at)}</span></li>
                ))}
              </ul>
            </details>
          )}
        </section>
      )}

      {/* ③ 확인해 주세요 */}
      {checks && (
        <section className="rc-sec" aria-labelledby={`chk-${r.id}`}>
          <h2 id={`chk-${r.id}`}>확인해 주세요</h2>
          <p className="sub rc-who">{keeper}가 헷갈린 곳이에요. 알려 주면 다음부터 맞춰요.</p>
          {r.day_check && <DayFix r={r} onFixed={onChange} />}
          {asks.slice(0, all === r.id ? asks.length : SHOW)}
          {asks.length > SHOW && all !== r.id && (
            <button type="button" className="small link" onClick={() => setAll(r.id)}>남은 확인 {asks.length - SHOW}개 더 보기</button>
          )}
        </section>
      )}

      <details className="rc-more rc-extra">
        <summary>더 보기</summary>
        {r.observation && (
          <section className="stack" aria-label="관측 보고서" data-testid="observation">
            <p style={{ margin: 0 }}>이 글을 읽은 방식 <span className="badge v">{r.observation.state}</span></p>
            {r.observation.limits.length > 0 && (
              <ul className="sub" style={{ margin: 0, paddingLeft: 18 }}>
                {r.observation.limits.map((x) => <li key={x}>{x}</li>)}
              </ul>
            )}
            <DownloadJson id={r.id} label="이 일기 내려받기" />
          </section>
        )}
        <OneLine target="entry" targetId={r.id} />
      </details>
    </div>
  );
}

// 별지기 한마디: 세 줄까지 보이고 누르면 다(긴 한마디가 화면을 먼저 차지하지 않게)
function KeeperWord({ text, checkIn, who, tone }: { text: string; checkIn: string | null; who: string; tone: string }) {
  const [open, setOpen] = useState(false);
  return (
    <section className="voice rc-word" aria-label="별지기 한마디" data-tone={tone}>
      <span className="who" aria-hidden>{who.slice(0, 1)}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <button type="button" className="bubble" aria-expanded={open} onClick={() => setOpen(!open)}>
          <span className="sr">{who} 한마디: </span><span className="clamp3" style={PRE}>{text}</span></button>
        {checkIn && <p className="sub" data-testid="check-in" style={{ margin: "6px 0 0", ...PRE }}>{checkIn}</p>}
      </div>
    </section>
  );
}
