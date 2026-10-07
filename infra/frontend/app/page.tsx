"use client";
// (가) 일기 쓰기 → 진행 단계 → (나) 결과 카드
import { useEffect, useRef, useState } from "react";
import ResultCard from "@/components/ResultCard";
import { getDiary, resumeDiary, writeDiary, type EntryResult, type Progress, type StreamError, type Weather } from "@/lib/api";
import { useOntology } from "@/lib/use";

export default function WritePage() {
  const onto = useOntology();
  const [text, setText] = useState("");
  const [weather, setWeather] = useState<Weather | null>(null);
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState<Progress | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [err, setErr] = useState<StreamError | null>(null);
  const [result, setResult] = useState<EntryResult | null>(null);
  const progRef = useRef<HTMLElement>(null);
  // 휴대폰에서는 진행 상황이 글 칸 아래에 있으니, 시작하거나 멈추면 그쪽으로 내려 보여 준다
  useEffect(() => { if (busy || err) progRef.current?.scrollIntoView({ block: "center" }); }, [busy, err]);

  const onProgress = (p: Progress) => { setProg(p); setSteps((s) => (s.includes(p.label) ? s : [...s, p.label])); };

  // 끊기면 상태를 먼저 보고, 이미 끝났으면 결과를, 아니면 "이어서 하기"를 보인다
  const fail = async (e: StreamError) => {
    if (e.entry_id && e.resumable) {
      const r = await getDiary(e.entry_id).catch(() => null);
      if (r?.status === "done") { setResult(r); return; }
    }
    setErr(e);
  };
  const go = async (fn: () => Promise<EntryResult>) => {
    setBusy(true); setErr(null);
    try { setResult(await fn()); } catch (e) { await fail(e as StreamError); } finally { setBusy(false); }
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSteps([]); setProg(null); setResult(null);
    go(() => writeDiary({ text, weather }, { onProgress }));
  };
  const resume = () => err?.entry_id && go(() => resumeDiary(err.entry_id!, { onProgress }));
  const again = () => { setText(""); setWeather(null); setResult(null); setSteps([]); setProg(null); window.scrollTo(0, 0); };

  if (result) return (
    <main>
      <ResultCard r={result} />
      {!result.crisis && <button onClick={again}>새 글 쓰기</button>}
    </main>
  );

  return (
    <main>
      <form onSubmit={submit} className="stack" aria-label="일기 쓰기">
        <h1>오늘의 일기</h1>
        <div>
          <label htmlFor="diary">마음껏 적어 주세요. 별지기가 생각 단위로 나눠 우주에 띄워요.</label>
          <textarea id="diary" value={text} onChange={(e) => setText(e.target.value)} disabled={busy}
            placeholder="오늘 있었던 일, 떠오른 생각, 다짐…" />
        </div>
        <fieldset>
          <legend>마음 날씨 (고르지 않아도 돼요)</legend>
          <div className="row">
            {onto?.weather.map((w) => (
              <button type="button" key={w.name} className="small" aria-pressed={weather === w.name} disabled={busy}
                onClick={() => setWeather(weather === w.name ? null : (w.name as Weather))}>
                {w.name} <span className="sub">({w.words.join(" · ")})</span>
              </button>
            ))}
          </div>
        </fieldset>
        <button type="submit" className="primary" disabled={busy || !text.trim()}>{busy ? "정리하는 중…" : "우주에 띄우기"}</button>
      </form>

      {(busy || steps.length > 0 || err) && (
        <section ref={progRef} className="card" style={{ marginTop: 16 }} aria-label="진행 상황" aria-live="polite">
          <h2>정리하는 중</h2>
          <ol className="steps">
            {steps.map((s, i) => <li key={s} className={i < steps.length - 1 || !busy ? "done" : "now"}>{s}</li>)}
          </ol>
          {prog && <p className="sub">{prog.done} / {prog.total} 단계</p>}
          {err && (
            <div className="stack" role="alert">
              <p className="err">{err.message}</p>
              {err.resumable && err.entry_id ? <button className="primary" onClick={resume} disabled={busy}>이어서 하기</button>
                : <p className="sub">글은 화면에 그대로 있어요. 잠시 뒤 다시 띄워 주세요.</p>}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
