"use client";
// (마) 되고 싶은 모습: 허락을 구한 뒤 대화하듯 4단계(요즘의 나 → 되고 싶은 나 → 걸리는 것 → 그때 해 볼 것). 이력 보존.
// 한 화면에 맞추기(2026-10-28): 북극성 카드는 짧게, 닿은 순간 · 예전 모습은 안에서 스크롤, 묻기는 한 번에 한 단계만.
import { useState } from "react";
import { useKeeperName } from "@/components/Keeper";
import { unquote } from "@/components/ResultCard";
import { declineAspiration, getAspiration, saveAspiration, why, type Aspiration } from "@/lib/api";
import { useLoad, useOntology } from "@/lib/use";

const KEYS = ["now", "want", "obstacle", "if_then"] as const;

function AspirationCard({ a, title }: { a: Aspiration; title: string }) {
  return (
    <section className="card asp-card" aria-label={title}>
      <h2>{title}</h2>
      <p className="quote" style={{ borderColor: "var(--gold)" }}>“{a.said}”</p>
      <div className="row" style={{ marginBottom: 6 }}>{a.values.map((v) => <span key={v} className="badge g">{v}</span>)}</div>
      <dl className="asp-facts">
        <dt>걸림돌</dt><dd>{a.obstacle}</dd>
        <dt>그때 해 볼 것</dt><dd>{a.if_then}</dd>
        <dt>말한 날</dt><dd>{a.said_at.slice(0, 10)}</dd>
      </dl>
      {a.reached.length > 0 && (
        <div className="asp-reached">
          <b>닿은 순간</b>
          <ul>{a.reached.map((r) => <li key={r.entry_id + r.quote} className="quote" style={{ borderColor: "var(--gold)" }}>{r.at.slice(0, 10)} · “{unquote(r.quote)}”</li>)}</ul>
        </div>
      )}
    </section>
  );
}

export default function AspirationPage() {
  const [data, err, reload] = useLoad(getAspiration, "되고 싶은 모습을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const onto = useOntology();
  const keeper = useKeeperName();
  const [fail, setFail] = useState("");
  const [mode, setMode] = useState<"view" | "ask" | "form" | "done" | "declined">("view");
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [values, setValues] = useState<string[]>([]);
  const [declined, setDeclined] = useState("");
  const steps = onto?.aspiration.ask_steps ?? [];

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data || !onto) return <main><p className="sub">되고 싶은 모습을 불러오는 중…</p></main>;
  const showAsk = mode === "ask" || (mode === "view" && !data.current && data.ask.should_ask);

  const next = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setAns({ ...ans, [KEYS[step]]: draft.trim() }); setDraft("");
    setStep(step + 1);
  };
  const save = async () => {
    setFail("");
    try { await saveAspiration({ now: ans.now, want: ans.want, obstacle: ans.obstacle, if_then: ans.if_then, values }); }
    catch (e) { return setFail(why(e, "북극성으로 띄우지 못했어요. 적은 답은 그대로 있으니 잠시 뒤 다시 눌러 주세요.")); }
    setMode("done"); reload();
  };
  const decline = async (m: "skip" | "stop") => {
    setFail("");
    try { await declineAspiration(m); }
    catch (e) { return setFail(why(e, "고른 것을 저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.")); }
    setDeclined(m === "skip" ? "알겠어요. 지금은 묻지 않을게요. 나중에 계기가 생기면 다시 여쭤볼게요." : "더 묻지 않을게요. 언제든 여기서 다시 적을 수 있어요.");
    setMode("declined");
  };
  const who = <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>;
  const s = steps[step];

  return (
    <main>
      <h1>되고 싶은 모습</h1>
      <p className="sub">내가 말한 되고 싶은 모습이 우주의 북극성이 돼요. 거리나 점수로 재지 않고, 글에서 그 모습에 닿은 순간만 짚어 드려요.</p>

      {mode === "declined" && <p className="toast" role="status">{declined}</p>}

      {showAsk && (
        <section className="card stack" aria-label="되고 싶은 모습 묻기">
          <div className="voice">{who}
            <div><div className="sub">{keeper}</div>
              <div className="bubble">며칠 동안 써 온 글을 보니, 되고 싶은 모습을 한번 같이 적어 보면 좋겠어요. 네 가지만 천천히 물어봐도 될까요?</div></div></div>
          <div className="row">
            <button className="primary" onClick={() => { setMode("form"); setStep(0); }}>좋아요</button>
            <button onClick={() => decline("skip")}>이번엔 넘어가기</button>
            <button onClick={() => decline("stop")}>그만 묻기</button>
          </div>
          {fail && <p className="err" role="alert" style={{ margin: 0 }}>{fail}</p>}
        </section>
      )}

      {mode === "form" && (
        <section className="card stack" aria-label="되고 싶은 모습 대화">
          <ol className="asp-dots" aria-hidden>{steps.map((x, i) => <li key={x.name} data-on={i <= step ? "" : undefined} />)}<li data-on={step >= 4 ? "" : undefined} /></ol>
          {step < 4 ? (<>
            <div className="voice">{who}
              <div><div className="sub">{step + 1} / 4 · {s?.name}</div><div className="bubble">{s?.question}</div></div></div>
            <form onSubmit={next} className="stack" aria-label={s?.name}>
              <label htmlFor="asp" className="sr">{s?.question}</label>
              <input id="asp" value={draft} maxLength={300} onChange={(e) => setDraft(e.target.value)} autoFocus
                placeholder={step === 3 ? "예: 피곤하면 오 분만 하고 자겠다" : "편하게 적어 주세요"} />
              {!draft.trim() && <p className="sub" style={{ margin: 0 }}>답을 적으면 다음 질문으로 넘어가요.</p>}
              <div className="row">
                <button type="submit" className="primary" disabled={!draft.trim()}>다음</button>
                <button type="button" onClick={() => decline("skip")}>이번엔 넘어가기</button>
                <button type="button" onClick={() => decline("stop")}>그만 묻기</button>
              </div>
            </form>
          </>) : (
            <div className="stack">
              <div className="bubble me">{ans.want}</div>
              <fieldset>
                <legend>이 모습이 기대는 가치를 골라 주세요(여럿 골라도, 하나도 안 골라도 돼요)</legend>
                <div className="row">
                  {onto.values.map((v) => (
                    <button key={v.name} type="button" className="small" title={v.definition} aria-pressed={values.includes(v.name)}
                      onClick={() => setValues(values.includes(v.name) ? values.filter((x) => x !== v.name) : [...values, v.name])}>{v.name}</button>
                  ))}
                </div>
              </fieldset>
              <button className="primary" onClick={save}>북극성으로 띄우기</button>
            </div>
          )}
          {fail && <p className="err" role="alert" style={{ margin: 0 }}>{fail}</p>}
        </section>
      )}

      {mode === "done" && <p className="toast" role="status">북극성으로 띄웠어요. 예전 모습은 &apos;예전 모습 보기&apos;에 남겨 둘게요.</p>}

      {data.current && mode !== "form" && <AspirationCard a={data.current} title="지금의 북극성" />}
      {mode !== "form" && !showAsk && (
        <div className="row">
          <button onClick={() => { setMode("form"); setStep(0); setAns({}); setValues([]); }}>{data.current ? "새로 적기" : "되고 싶은 모습 적어 보기"}</button>
          {data.history.length > 0 && (
            <details className="asp-history">
              <summary className="btn">예전 모습 보기 ({data.history.length})</summary>
              <ul>
                {data.history.map((a) => (
                  <li key={a.id}>
                    <span className="meta">{a.said_at.slice(0, 10)}</span> “{a.said}”
                    {a.values.map((v) => <span key={v} className="badge g">{v}</span>)}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </main>
  );
}
