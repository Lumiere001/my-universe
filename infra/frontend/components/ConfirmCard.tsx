"use client";
// 정리본 확인(WS20 → PRD v9 Q9): 대화를 마치면 한 화면에서 정리본(이 일기의 원문이 됨)을 보고 '맞아요, 저장할게요'.
// 글을 직접 고치는 칸은 없다. 고칠 것 · 더할 것이 있으면 '고칠 게 있어요' → 별지기가 다시 묻고(대화로 돌아감), 답한 뒤
// 다시 정리한다. 찾은 생각 · 이어진 지난 생각은 접어 두고 볼 수만 있다. 숨은 이유 한 줄(Q7)은 맨 아래.
// 한 화면 규칙(2026-10-28): 머리(제목 · 안내) · 몸(정리본, 이 칸 안에서만 넘김) · 발(단추, 늘 보임).
import { useState } from "react";
import { confirmDiary, why, type EntryResult } from "@/lib/api";
import { useKindName } from "@/lib/use";
import { unquote } from "./ResultCard";

const PRE = { whiteSpace: "pre-line" } as const;

export default function ConfirmCard({ r, reason, onSaved, onFix }:
  { r: EntryResult; reason?: string; onSaved: (r: EntryResult) => void; onFix: () => Promise<void> | void }) {
  const kindName = useKindName();
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");

  const save = async () => {
    setBusy("저장하는 중…"); setErr("");
    // 맞아요 = 정리본과 찾은 생각을 그대로 받아들임(오답 재료의 '맞아요')
    try { onSaved(await confirmDiary(r.id, { fixes: [], agreed: ["summary", ...r.thoughts.map((t) => t.id)] })); }
    catch (e) { setErr(why(e, "저장하지 못했어요. 다시 눌러 주세요.")); }
    finally { setBusy(""); }
  };
  const fix = async () => {
    setBusy("별지기를 부르는 중…"); setErr("");
    try { await onFix(); } catch (e) { setErr(why(e, "별지기를 부르지 못했어요. 다시 눌러 주세요.")); }
    finally { setBusy(""); }
  };

  return (
    <section className="card confirm" aria-label="정리본 확인" data-testid="confirm-card">
      <div className="confirm-head">
        <h2>오늘 이야기를 이렇게 정리했어요</h2>
        <p className="sub">맞으면 저장해요. 고칠 것 · 더할 것이 있으면 별지기가 다시 물어볼게요.</p>
      </div>

      <div className="confirm-body">
        <article>
          {r.title && <b>{r.title}</b>}
          <p style={{ margin: "4px 0 0", ...PRE }}>{r.text || r.info?.summary}</p>
        </article>
        {r.thoughts.length > 0 && (
          <article>
            <details>
              <summary>찾은 생각 {r.thoughts.length}개</summary>
              {r.thoughts.map((t) => (
                <div key={t.id} style={{ marginTop: 8 }}>
                  <span className="badge v">{kindName(t.kind)}</span> {t.text}
                  <p className="quote">“{unquote(t.quote)}”</p>
                </div>
              ))}
            </details>
          </article>
        )}
        {reason && <article><p className="sub reason" style={{ margin: 0 }} data-testid="reason-line">{reason}</p></article>}
      </div>

      <div className="confirm-foot">
        {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
        <button onClick={fix} disabled={!!busy}>고칠 게 있어요</button>
        <button className="primary" onClick={save} disabled={!!busy}>{busy || "맞아요, 저장할게요"}</button>
      </div>
    </section>
  );
}
