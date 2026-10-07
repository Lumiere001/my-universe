"use client";
// (가) 일기 쓰기 → 진행 단계 → (나) 결과 카드
import { useEffect, useRef, useState } from "react";
import ResultCard from "@/components/ResultCard";
import { getDiary, resumeDiary, writeDiary, type EntryResult, type Progress, type StreamError, type Weather } from "@/lib/api";
import { useOntology } from "@/lib/use";

// 정리 중인 기록 id. 새로고침 · 끊김 뒤에도 '이어서 하기'를 보이려고 이 탭에만 둔다.
const PENDING = "pending-entry";
const keep = (id: string | null) => { try { if (id) sessionStorage.setItem(PENDING, id); else sessionStorage.removeItem(PENDING); } catch { /* 저장소 막힘 */ } };

export default function WritePage() {
  const onto = useOntology();
  const [text, setText] = useState("");
  const [weather, setWeather] = useState<Weather | null>(null);
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState<Progress | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [err, setErr] = useState<StreamError | null>(null);
  const [result, setResult] = useState<EntryResult | null>(null);
  const [waiting, setWaiting] = useState(false);
  const progRef = useRef<HTMLElement>(null);
  // 휴대폰에서는 진행 상황이 글 칸 아래에 있으니, 시작하거나 멈추면 그쪽으로 내려 보여 준다
  useEffect(() => { if (busy || err) progRef.current?.scrollIntoView({ block: "center" }); }, [busy, err]);

  useEffect(() => { if (result) window.scrollTo(0, 0); }, [result]);
  const onProgress = (p: Progress) => { keep(p.entry_id); setWaiting(false); setProg(p); setSteps((s) => (s.includes(p.label) ? s : [...s, p.label])); };

  // 끊기면 상태를 먼저 보고, 이미 끝났으면 결과를, 아니면 "이어서 하기"를 보인다
  const fail = async (e: StreamError) => {
    if (e.entry_id && e.resumable) {
      const r = await getDiary(e.entry_id).catch(() => null);
      if (r?.status === "done") { keep(null); setResult(r); return; }
    }
    if (!e.resumable) keep(null);
    setErr(e);
  };
  const go = async (fn: () => Promise<EntryResult>) => {
    setBusy(true); setErr(null);
    try { setResult(await fn()); keep(null); } catch (e) { await fail(e as StreamError); } finally { setBusy(false); setWaiting(false); }
  };
  // 새로고침해서 돌아오면, 정리하던 기록이 있는지 본다
  useEffect(() => {
    let id: string | null = null;
    try { id = sessionStorage.getItem(PENDING); } catch { /* 저장소 막힘 */ }
    if (id) fail({ entry_id: id, code: "disconnected", message: "정리하던 글이 있어요. 이어서 할까요?", resumable: true });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // 서버가 아직 정리 중이면 끝날 때까지 기다리고, 멈췄으면 끝난 단계 다음부터 다시 돌린다
  const cont = async (id: string): Promise<EntryResult> => {
    try {
      for (;;) {
        const r = await getDiary(id);
        if (r.status === "done") return r;
        if (r.status === "failed") return await resumeDiary(id, { onProgress });
        setWaiting(true);
        await new Promise((ok) => setTimeout(ok, 3000));
      }
    } catch (e) {
      const x = e as StreamError;
      throw x.entry_id ? x : { entry_id: id, code: x.code ?? "network", message: x.message || "연결이 끊겼어요.", resumable: x.code !== "not_found" };
    }
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSteps([]); setProg(null); setResult(null);
    go(() => writeDiary({ text, weather }, { onProgress }));
  };
  const resume = () => err?.entry_id && go(() => cont(err.entry_id!));
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
          <h2>{err && !busy ? (err.resumable ? "정리가 멈췄어요" : "정리하지 못했어요") : "정리하는 중"}</h2>
          <ol className="steps">
            {steps.map((s, i) => <li key={s} className={i < steps.length - 1 || !busy ? "done" : "now"}>{s}</li>)}
          </ol>
          {prog && <p className="sub">{prog.done} / {prog.total} 단계</p>}
          {waiting && <p className="sub">화면이 끊긴 동안에도 서버에서 계속 정리하고 있어요. 끝나면 바로 보여 드릴게요.</p>}
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
