"use client";
// 요약 확인(WS20): 대화에서 정리한 초안(status "confirm")의 요약 · 생각 목록(종류 · 원문 근거) · 이어진 지난 생각(점선)을
// 항목마다 '맞아요 / 고칠래요'로 보고 '확인하고 우주에 저장'. 고칠 수 있는 것: 요약 문장 · 생각 종류 · 생각 빼기.
// 원문 인용은 고치지 않는다(원문 근거 G1). 저장한 뒤 한마디는 대화 화면 안의 별지기 말풍선으로 보인다.
import { useState } from "react";
import { confirmDiary, type ConfirmInput, type EntryResult } from "@/lib/api";
import { useKindName, useOntology } from "@/lib/use";
import { unquote } from "./ResultCard";

type Pick = "맞아요" | "고칠래요";
const day = (iso: string | null | undefined) => (iso ?? "").slice(0, 10);

function Choice({ label, value, onPick }: { label: string; value?: Pick; onPick: (v: Pick) => void }) {
  return (
    <div className="row" role="group" aria-label={label}>
      {(["맞아요", "고칠래요"] as const).map((v) => (
        <button key={v} type="button" className="small" aria-pressed={value === v} onClick={() => onPick(v)}>{v}</button>
      ))}
    </div>
  );
}

export default function ConfirmCard({ r, onSaved }: { r: EntryResult; onSaved: (r: EntryResult) => void }) {
  const onto = useOntology();
  const kindName = useKindName();
  const [pick, setPick] = useState<Record<string, Pick>>({});   // 'summary' · 생각 id → 고른 것
  const [summary, setSummary] = useState(r.info?.summary ?? "");
  const [kinds, setKinds] = useState<Record<string, string>>({});
  const [removed, setRemoved] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const set = (k: string) => (v: Pick) => setPick({ ...pick, [k]: v });
  const past = (id: string) => r.past.find((p) => p.thought_id === id);
  const kept = r.thoughts.filter((t) => !removed[t.id]).length;

  const save = async () => {
    setBusy(true); setErr("");
    const fixed = (id: string) => pick[id] === "고칠래요";
    const body: ConfirmInput = {
      ...(fixed("summary") && summary.trim() && summary.trim() !== r.info?.summary && { summary: summary.trim() }),
      fixes: r.thoughts.filter((t) => fixed(t.id) && (removed[t.id] || (kinds[t.id] && kinds[t.id] !== t.kind)))
        .map((t) => (removed[t.id] ? { id: t.id, remove: true } : { id: t.id, kind: kinds[t.id] })),
      agreed: Object.keys(pick).filter((k) => pick[k] === "맞아요"),
    };
    try { onSaved(await confirmDiary(r.id, body)); } catch (e) { setErr((e as Error).message || "저장하지 못했어요. 다시 눌러 주세요."); }
    finally { setBusy(false); }
  };

  return (
    <section className="card stack" aria-label="요약 확인" data-testid="confirm-card">
      <h2>오늘 이야기를 이렇게 정리했어요</h2>
      <p className="sub">맞는지 봐 주세요. 확인하고 저장해야 우주에 행성으로 떠요. 원문 인용은 내가 한 말 그대로라 고치지 않아요.</p>

      <article style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
        <b>요약</b>
        {pick.summary === "고칠래요" ? (
          <div style={{ marginTop: 6 }}>
            <label htmlFor="confirm-summary">요약 고치기</label>
            <textarea id="confirm-summary" value={summary} maxLength={1000} onChange={(e) => setSummary(e.target.value)}
              style={{ minHeight: 96 }} />
          </div>
        ) : <p style={{ margin: "6px 0", whiteSpace: "pre-line" }}>{r.info?.summary}</p>}
        <Choice label="요약이 맞나요" value={pick.summary} onPick={set("summary")} />
      </article>

      {r.thoughts.map((t) => (
        <article key={t.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 10, opacity: removed[t.id] ? 0.5 : 1 }}>
          <div className="row">
            <span className="badge v">{kindName(kinds[t.id] ?? t.kind)}</span>
            <span className="badge">{t.certainty}</span>
            {t.topic && <span className="badge">{t.topic}</span>}
            {removed[t.id] && <span className="badge o">뺄 생각</span>}
          </div>
          <p style={{ margin: "6px 0 0" }}>{t.text}</p>
          <p className="quote">“{unquote(t.quote)}”</p>
          {pick[t.id] === "고칠래요" && (
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div style={{ flex: "1 1 180px" }}>
                <label htmlFor={"kind-" + t.id}>생각 종류</label>
                <select id={"kind-" + t.id} value={kinds[t.id] ?? t.kind} disabled={removed[t.id]}
                  onChange={(e) => setKinds({ ...kinds, [t.id]: e.target.value })}>
                  {onto?.kinds.map((k) => <option key={k.name} value={k.name}>{kindName(k.name)}</option>)}
                </select>
              </div>
              <label className="row" style={{ margin: 0, color: "var(--text)" }}>
                <input type="checkbox" style={{ width: "auto" }} checked={!!removed[t.id]}
                  onChange={(e) => setRemoved({ ...removed, [t.id]: e.target.checked })} /> 이 생각 빼기
              </label>
            </div>
          )}
          <Choice label="이 생각이 맞나요" value={pick[t.id]} onPick={set(t.id)} />
        </article>
      ))}

      {r.relations.length > 0 && (
        <article style={{ borderTop: "1px solid var(--line)", paddingTop: 10 }}>
          <b>이어진 지난 생각</b>
          {r.relations.map((rel) => {
            const p = past(rel.from);
            return (
              <div key={rel.id} style={{ marginTop: 8 }}>
                <div className="row"><span className="badge v">{rel.type}</span>
                  <span className="badge">{rel.line === "실선" ? "실선 · 글에 직접 씀" : "점선 · AI 추정"}</span></div>
                {p && <p className="quote">그때 {day(p.written_at)}: “{unquote(rel.quote ?? p.text)}”</p>}
                <p className="sub" style={{ margin: 0 }}>{rel.explanation}</p>
              </div>
            );
          })}
          <p className="sub" style={{ margin: "8px 0 0" }}>점선은 저장한 뒤 우주 · 지난 기록에서 맞아요 / 아니에요로 확인할 수 있어요.</p>
        </article>
      )}

      {kept === 0 && <p className="sub">생각을 모두 빼면 생각 없이 기록만 남아요.</p>}
      {err && <p className="err" role="alert">{err}</p>}
      <button className="primary" onClick={save} disabled={busy}>{busy ? "저장하는 중…" : "확인하고 우주에 저장"}</button>
    </section>
  );
}
