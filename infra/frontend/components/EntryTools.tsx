"use client";
// 기록 하나에 붙는 작은 도구: 날짜 확인(고르기) · 지우기 · 날씨 질문 건너뛰기.
import { useState } from "react";
import { deleteDiary, sendFeedback, setEntryDay, type EntryResult } from "@/lib/api";

export const localToday = () => new Date(Date.now() - new Date().getTimezoneOffset() * 60_000).toISOString().slice(0, 10);

// '날짜 확인 필요'(글 속 날짜를 하나로 읽지 못함) → 이 글이 다루는 날을 고른다(PATCH /diary/{id}/day)
export function DayFix({ r, onFixed }: { r: EntryResult; onFixed?: (r: EntryResult) => void }) {
  const [day, setDay] = useState(r.day ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!day) return;
    setBusy(true); setErr("");
    try { onFixed?.(await setEntryDay(r.id, day)); } catch (x) { setErr((x as Error).message); } finally { setBusy(false); }
  };
  return (
    <form onSubmit={save} className="stack" aria-label="날짜 확인" data-testid="day-fix" style={{ marginTop: 8 }}>
      <p className="sub" style={{ margin: 0 }}><span className="badge o">날짜 확인 필요</span> 글 속 날짜를 하나로 읽지 못했어요. 이 글이 다루는 날을 골라 주세요.</p>
      <div className="row">
        <input aria-label="글이 다루는 날" type="date" value={day} max={localToday()} onChange={(e) => setDay(e.target.value)}
          style={{ flex: "1 1 160px", width: "auto" }} required />
        <button type="submit" className="small" disabled={busy || !day}>{busy ? "고치는 중…" : "이 날로 고치기"}</button>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
    </form>
  );
}

// 지난 기록 지우기: 한 번 더 묻고 지운다(생각 · 이어진 선 · 한마디까지, 되돌릴 수 없음)
export function DeleteEntry({ id, onDeleted }: { id: string; onDeleted: () => void }) {
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!ask) return <button className="danger" onClick={() => setAsk(true)}>이 기록 지우기</button>;
  const go = async () => {
    setBusy(true); setErr("");
    try { await deleteDiary(id); onDeleted(); } catch (x) { setErr((x as Error).message); setBusy(false); }
  };
  return (
    <section className="card stack" role="alertdialog" aria-label="기록 지우기 확인">
      <p style={{ margin: 0 }}>이 기록과 그 생각 · 이어진 선 · 한마디가 모두 지워지고 우주에서도 사라져요. <b>되돌릴 수 없어요.</b></p>
      <div className="row">
        <button className="danger" disabled={busy} onClick={go}>{busy ? "지우는 중…" : "지우기"}</button>
        <button disabled={busy} onClick={() => setAsk(false)}>취소</button>
      </div>
      {err && <p className="err" role="alert">{err}</p>}
    </section>
  );
}

// 마음 날씨 질문 건너뛰기: 다음부터 묻지 않는다(피드백 '날씨 건너뜀' → weather_ask: false)
export function WeatherSkip({ onDone }: { onDone?: () => void }) {
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  if (done) return <p className="toast" role="status" style={{ margin: "8px 0 0" }}>알겠어요. 다음부터 마음 날씨는 묻지 않을게요.</p>;
  const skip = async () => {
    setErr("");
    try { await sendFeedback({ target: "weather", value: "날씨 건너뜀" }); setDone(true); onDone?.(); }
    catch { setErr("보내지 못했어요. 다시 눌러 주세요."); }
  };
  return (
    <div className="row" style={{ marginTop: 8 }}>
      <button type="button" className="small" onClick={skip}>건너뛰기 · 다음부터 묻지 않기</button>
      {err && <span className="err" role="alert">{err}</span>}
    </div>
  );
}
