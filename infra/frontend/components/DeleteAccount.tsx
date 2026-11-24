"use client";
// 계정과 모든 기록 지우기(설정 맨 아래 · 마침 화면). '지우기'를 직접 입력해야 버튼이 켜진다. 끝나면 로그아웃.
import { useState } from "react";
import { deleteMe, supabase, why } from "@/lib/api";

export default function DeleteAccount() {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try { await deleteMe(); await supabase()?.auth.signOut(); }
    catch (e) { setErr(why(e, "계정을 지우지 못했어요. 잠시 뒤 다시 해 주세요.")); setBusy(false); }
  };
  return (
    <section className="set-row set-danger stack" aria-label="계정 지우기">
      <div className="set-k">
        <b>계정과 모든 기록 지우기</b>
        <p className="sub">일기 · 생각 · 사람 · 되고 싶은 모습 · 설정과 계정이 모두 지워져요. <b>되돌릴 수 없어요.</b></p>
      </div>
      <div className="set-v stack">
        <div><label htmlFor="del-confirm">확인하려면 &apos;지우기&apos;를 입력해 주세요</label>
          <input id="del-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" /></div>
        <button className="danger" disabled={typed.trim() !== "지우기" || busy} onClick={go}>{busy ? "지우는 중…" : "계정과 모든 기록 지우기"}</button>
        {err && <p className="err" role="alert">{err}</p>}
      </div>
    </section>
  );
}
