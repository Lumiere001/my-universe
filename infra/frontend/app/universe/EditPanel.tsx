"use client";
// 우주 고치기(WS16): 해 추가(가까운 기준 축은 AI 가 제안, 바꿀 수 있음) · 작은 별을 다른 해로 옮기기 · 합치기 제안 확인,
// 행성 카드의 생각 종류 · 가치 고치기(ThoughtFix). 고친 내용은 오답 재료로 남는다(docs/api-v8.md §4.1).
import { useState } from "react";
import {
  addSun, declineMerge, fixThought, getMergeCandidates, getSuns, mergeStars, moveStar, setSunAxis,
  type Thought, type Universe,
} from "@/lib/api";
import { useKindName, useLoad, useOntology } from "@/lib/use";

const BASIS: Record<string, string> = { 낱말: "이름이 그 영역의 대표 낱말과 겹쳐요", 임베딩: "뜻이 가장 가까워요", 없음: "맞는 기준 축을 찾지 못했어요" };

export default function EditPanel({ data, onChanged }: { data: Universe; onChanged: () => void }) {
  const [suns, , reloadSuns] = useLoad(getSuns);
  const [cands, , reloadCands] = useLoad(getMergeCandidates);
  const [name, setName] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const run = async (f: () => Promise<string>) => {
    setBusy(true); setErr("");
    try { setMsg(await f()); reloadSuns(); reloadCands(); onChanged(); }
    catch (e) { setMsg(""); setErr((e as Error).message); }
    finally { setBusy(false); }
  };
  const all = suns?.suns ?? [];
  const sunName = (id: string) => all.find((s) => s.id === id)?.name ?? data.suns.find((s) => s.id === id)?.name ?? "";
  const own = all.filter((s) => !suns?.axes.includes(s.name));   // 기준 축 이름이 아닌 해(사용자 해 · 9개 밖 영역)

  return (
    <details className="card" data-testid="edit-panel">
      <summary>우주 고치기</summary>
      <div className="stack" style={{ marginTop: 10 }}>
        {msg && <p className="toast" role="status">{msg}</p>}
        {err && <p className="err" role="alert">{err}</p>}

        <form className="stack" aria-label="해 추가" onSubmit={(e) => {
          e.preventDefault();
          const n = name.trim();
          if (n) run(async () => {
            const s = await addSun(n); setName("");
            return `“${s.name}” 해를 띄웠어요. 가까운 기준 축은 ${s.axis}(으)로 이어 뒀어요(${BASIS[s.suggested.basis] ?? ""}). 아래에서 바꿀 수 있어요.`;
          });
        }}>
          <h3 style={{ margin: 0, fontSize: "1rem" }}>해 추가</h3>
          <p className="sub" style={{ margin: 0 }}>내 삶의 영역을 직접 띄워요(예: 통일 사역). 작은 별을 옮겨 오면 그 해를 돌아요.</p>
          <div className="row">
            <input aria-label="새 해 이름" aria-describedby="sun-name-hint" value={name} maxLength={20} placeholder="새 해 이름" onChange={(e) => setName(e.target.value)} style={{ flex: "1 1 160px", width: "auto" }} />
            <button type="submit" className="small primary" disabled={busy || !name.trim()}>해 추가</button>
          </div>
          {/* 해 이름은 암호화하지 않고 그대로 둔다(2026-10-14 결정) — 그래서 사람 이름을 넣지 않게 안내 */}
          <p className="sub" id="sun-name-hint" style={{ margin: 0 }}>사람 이름은 빼 주세요. 해 이름은 암호화하지 않고 그대로 저장해요.</p>
        </form>

        {own.length > 0 && (
          <section className="stack" aria-label="해와 기준 축">
            <h3 style={{ margin: 0, fontSize: "1rem" }}>해와 기준 축</h3>
            <p className="sub" style={{ margin: 0 }}>뒤에서는 해마다 기준 축 9개 중 가장 가까운 것을 이어 두어 시간에 따라 비교해요.</p>
            {own.map((s) => (
              <div key={s.id} className="row">
                <b style={{ flex: "1 1 120px" }}>{s.name}</b>
                <select aria-label={`${s.name}의 기준 축`} value={s.axis ?? ""} disabled={busy} style={{ flex: "1 1 160px", width: "auto" }}
                  onChange={(e) => { const a = e.target.value; run(async () => { await setSunAxis(s.id, a); return `“${s.name}”을(를) ${a}에 이었어요.`; }); }}>
                  {!s.axis && <option value="">아직 안 이음</option>}
                  {suns?.axes.map((a) => <option key={a} value={a}>{a}</option>)}
                </select>
              </div>
            ))}
          </section>
        )}

        {data.stars.length > 0 && (
          <section className="stack" aria-label="작은 별 옮기기">
            <h3 style={{ margin: 0, fontSize: "1rem" }}>작은 별 옮기기</h3>
            <p className="sub" style={{ margin: 0 }}>주제가 다른 영역에 더 맞으면 옮겨요. 그 별의 행성과 다음에 쓰는 같은 주제도 따라가요.</p>
            {data.stars.map((st) => (
              <div key={st.id} className="row">
                <span style={{ flex: "1 1 120px" }}>{st.name} <span className="sub">· 행성 {st.planet_count}</span></span>
                <select aria-label={`${st.name}이(가) 도는 해`} value={st.sun_id} disabled={busy || !all.length} style={{ flex: "1 1 160px", width: "auto" }}
                  onChange={(e) => { const to = e.target.value; run(async () => { await moveStar(st.id, to); return `“${st.name}”을(를) ${sunName(to)} 해로 옮겼어요.`; }); }}>
                  {!all.some((s) => s.id === st.sun_id) && <option value={st.sun_id}>{sunName(st.sun_id)}</option>}
                  {all.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            ))}
          </section>
        )}

        <section className="stack" aria-label="작은 별 합치기 제안">
          <h3 style={{ margin: 0, fontSize: "1rem" }}>작은 별 합치기 제안</h3>
          {cands?.candidates.length ? cands.candidates.map((c) => (
            <div key={c.a.id + c.b.id} className="stack" style={{ borderTop: "1px solid var(--line)", paddingTop: 8 }}>
              <p style={{ margin: 0 }}>“{c.a.name}” · “{c.b.name}” <span className="sub">{c.sun ? `${c.sun} 해 · ` : ""}{c.why}</span></p>
              <div className="row">
                <button className="small" disabled={busy} onClick={() => run(async () => { await mergeStars(c.b.id, c.a.id); return `“${c.b.name}”을(를) “${c.a.name}”(으)로 합쳤어요.`; })}>“{c.a.name}”(으)로 합치기</button>
                <button className="small" disabled={busy} onClick={() => run(async () => { await mergeStars(c.a.id, c.b.id); return `“${c.a.name}”을(를) “${c.b.name}”(으)로 합쳤어요.`; })}>“{c.b.name}”(으)로 합치기</button>
                <button className="small" disabled={busy} onClick={() => run(async () => { await declineMerge(c.a.id, c.b.id); return "따로 둘게요. 이 둘은 다시 묻지 않아요."; })}>따로 두기</button>
              </div>
            </div>
          )) : <p className="sub" style={{ margin: 0 }}>지금은 합칠 만한 작은 별이 없어요.</p>}
        </section>
      </div>
    </details>
  );
}

// 행성 카드의 생각 하나: 종류 · 가치가 틀렸으면 고친다(고친 값은 오답 재료).
export function ThoughtFix({ t, onFixed }: { t: Thought; onFixed: (t: Thought) => void }) {
  const onto = useOntology();
  const kindName = useKindName();
  const [open, setOpen] = useState(false);
  const [kind, setKind] = useState(t.kind);
  const [value, setValue] = useState(t.value ?? "");
  const [err, setErr] = useState("");
  if (!open) return <button className="small" onClick={() => setOpen(true)} aria-label="이 생각의 종류 · 가치 고치기">고치기</button>;
  return (
    <form className="row" aria-label="생각 고치기" style={{ marginTop: 6 }} onSubmit={async (e) => {
      e.preventDefault();
      try { onFixed(await fixThought(t, { kind, value: value || null })); setOpen(false); setErr(""); }
      catch (x) { setErr((x as Error).message); }
    }}>
      <select aria-label="생각 종류" value={kind} onChange={(e) => setKind(e.target.value)} style={{ flex: "1 1 130px", width: "auto" }}>
        {onto?.kinds.map((k) => <option key={k.name} value={k.name}>{kindName(k.name)}</option>)}
      </select>
      <select aria-label="가치" value={value} onChange={(e) => setValue(e.target.value)} style={{ flex: "1 1 110px", width: "auto" }}>
        <option value="">가치 없음</option>
        {onto?.values.map((v) => <option key={v.name} value={v.name}>{v.name}</option>)}
      </select>
      <button type="submit" className="small primary">저장</button>
      <button type="button" className="small" onClick={() => setOpen(false)}>취소</button>
      {err && <span className="err" role="alert">{err}</span>}
    </form>
  );
}
