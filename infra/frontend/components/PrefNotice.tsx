"use client";
// 내 반응에 맞춰 바꾼 설정(개인 고리, 2026-10-30 · docs/content/C-01 「내 반응에 맞춰 바꾼 설정」). 반응이 한쪽으로 쌓이면 서버가
// 묻지 않고 그 사람 설정을 한 칸 옮긴다(POST /feedback → tuned). 여기서 알리고 되돌릴 수 있다. 반응을 누른 화면 어디서든 뜬다(Shell).
import { useEffect, useState } from "react";
import { getPrefSuggestions, markPrefSeen, undoPref, type PrefNote } from "@/lib/api";

const LABEL = { cross_links: "다른 영역과 이어진 선 보이기", suggestions: "다음 걸음 제안 빈도" } as const;

export default function PrefNotice() {
  const [list, setList] = useState<PrefNote[]>([]);
  useEffect(() => {
    const load = () => getPrefSuggestions().then((r) => setList(r.applied), () => { /* 알림은 없어도 됨 */ });
    load();
    window.addEventListener("pref-tuned", load);
    return () => window.removeEventListener("pref-tuned", load);
  }, []);
  if (!list.length) return null;
  const undo = async (id: string) => {
    await undoPref(id).catch(() => { /* 다음에 다시 보일 뿐 */ });
    setList((l) => l.filter((x) => x.id !== id));
  };
  const keep = async () => {
    await markPrefSeen().catch(() => { /* 다음에 다시 보일 뿐 */ });
    setList([]);
  };
  return (
    <section className="card stack pref-note" role="status" aria-label="내 반응에 맞춰 바꾼 설정">
      <h2>내 반응에 맞춰 설정을 바꿨어요</h2>
      {list.map((x) => (
        <div key={x.id} className="pref-item">
          <p><b>{LABEL[x.setting]}</b>: {x.from} → <b>{x.to}</b><br /><span className="sub">{x.reason}</span></p>
          <button className="small" onClick={() => undo(x.id)}>되돌리기</button>
        </div>
      ))}
      <button className="small primary" onClick={keep}>이대로 둘게요</button>
    </section>
  );
}
