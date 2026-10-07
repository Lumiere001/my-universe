"use client";
// (마) 되고 싶은 모습: 허락을 구한 뒤 대화하듯 4단계(요즘의 나 → 되고 싶은 나 → 걸리는 것 → 그때 해 볼 것). 이력 보존.
import { useState } from "react";
import { unquote } from "@/components/ResultCard";
import { declineAspiration, getAspiration, saveAspiration, type Aspiration } from "@/lib/api";
import { useLoad, useOntology } from "@/lib/use";

const KEYS = ["now", "want", "obstacle", "if_then"] as const;

function AspirationCard({ a, title }: { a: Aspiration; title: string }) {
  return (
    <section className="card" aria-label={title}>
      <h2>{title}</h2>
      <p className="quote" style={{ borderColor: "var(--gold)" }}>“{a.said}”</p>
      <div className="row" style={{ marginBottom: 6 }}>{a.values.map((v) => <span key={v} className="badge g">{v}</span>)}</div>
      <p className="sub" style={{ margin: 0 }}>걸림돌: {a.obstacle}<br />그때 해 볼 것: {a.if_then}<br />말한 날: {a.said_at.slice(0, 10)}</p>
      {a.reached.length > 0 && (
        <div style={{ marginTop: 8 }}>
          <b>닿은 순간</b>
          {a.reached.map((r) => <p key={r.entry_id + r.quote} className="quote" style={{ borderColor: "var(--gold)" }}>{r.at.slice(0, 10)} · “{unquote(r.quote)}”</p>)}
        </div>
      )}
    </section>
  );
}

export default function AspirationPage() {
  const [data, err, reload] = useLoad(getAspiration);
  const onto = useOntology();
  const [mode, setMode] = useState<"view" | "ask" | "form" | "done" | "declined">("view");
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState<Record<string, string>>({});
  const [draft, setDraft] = useState("");
  const [values, setValues] = useState<string[]>([]);
  const [declined, setDeclined] = useState("");
  const steps = onto?.aspiration.ask_steps ?? [];

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data || !onto) return <main><p className="sub">불러오는 중…</p></main>;
  const showAsk = mode === "ask" || (mode === "view" && !data.current && data.ask.should_ask);

  const next = (e: React.FormEvent) => {
    e.preventDefault();
    if (!draft.trim()) return;
    setAns({ ...ans, [KEYS[step]]: draft.trim() }); setDraft("");
    setStep(step + 1);
  };
  const save = async () => {
    await saveAspiration({ now: ans.now, want: ans.want, obstacle: ans.obstacle, if_then: ans.if_then, values });
    setMode("done"); reload();
  };
  const decline = async (m: "skip" | "stop") => {
    await declineAspiration(m);
    setDeclined(m === "skip" ? "알겠어요. 지금은 묻지 않을게요. 나중에 계기가 생기면 다시 여쭤볼게요." : "더 묻지 않을게요. 언제든 여기서 다시 적을 수 있어요.");
    setMode("declined");
  };

  return (
    <main>
      <h1>되고 싶은 모습</h1>
      <p className="sub">우주의 북극성이 돼요. 거리나 점수로 재지 않고, 닿은 순간만 짚어 드려요.</p>

      {mode === "declined" && <p className="toast" role="status">{declined}</p>}

      {showAsk && (
        <section className="card stack" aria-label="되고 싶은 모습 묻기">
          <div className="voice"><span className="who" aria-hidden>별</span>
            <div className="bubble">며칠 동안 써 주신 글을 보니, 되고 싶은 모습을 한번 같이 적어 보면 좋겠어요. 네 가지만 천천히 물어봐도 될까요?</div></div>
          <div className="row">
            <button className="primary" onClick={() => { setMode("form"); setStep(0); }}>좋아요</button>
            <button onClick={() => decline("skip")}>이번엔 넘어가기</button>
            <button onClick={() => decline("stop")}>그만 묻기</button>
          </div>
        </section>
      )}

      {mode === "form" && (
        <section className="card stack" aria-label="되고 싶은 모습 대화">
          {steps.slice(0, step + 1).map((s, i) => (
            <div key={s.name} className="stack">
              <div className="voice"><span className="who" aria-hidden>별</span>
                <div><div className="sub">{i + 1} / 4 · {s.name}</div><div className="bubble">{s.question}</div></div></div>
              {i < step && <div className="bubble me">{ans[KEYS[i]]}</div>}
            </div>
          ))}
          {step < 4 ? (
            <form onSubmit={next} className="stack" aria-label={steps[step]?.name}>
              <label htmlFor="asp" className="sr">{steps[step]?.question}</label>
              <input id="asp" value={draft} maxLength={300} onChange={(e) => setDraft(e.target.value)} autoFocus
                placeholder={step === 3 ? "예: 피곤하면 오 분만 하고 자겠다" : "편하게 적어 주세요"} />
              <div className="row">
                <button type="submit" className="primary" disabled={!draft.trim()}>다음</button>
                <button type="button" onClick={() => decline("skip")}>이번엔 넘어가기</button>
                <button type="button" onClick={() => decline("stop")}>그만 묻기</button>
              </div>
            </form>
          ) : (
            <div className="stack">
              <fieldset>
                <legend>기대는 가치를 골라 주세요(고르지 않아도 돼요)</legend>
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
        </section>
      )}

      {mode === "done" && <p className="toast" role="status">북극성으로 띄웠어요. 예전 모습은 이력에 남겨 둘게요.</p>}

      {data.current && mode !== "form" && <AspirationCard a={data.current} title="지금의 북극성" />}
      {mode !== "form" && !showAsk && <button onClick={() => { setMode("form"); setStep(0); setAns({}); setValues([]); }}>{data.current ? "새로 적기" : "적어 보기"}</button>}

      {data.history.length > 0 && (
        <details className="card" style={{ marginTop: 14 }}>
          <summary>이력 보기 ({data.history.length})</summary>
          <div style={{ marginTop: 10 }}>{data.history.map((a) => <AspirationCard key={a.id} a={a} title={a.said_at.slice(0, 10) + "에 말한 모습"} />)}</div>
        </details>
      )}
    </main>
  );
}
