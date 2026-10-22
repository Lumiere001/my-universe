"use client";
// 피드백으로 본 "이 설정으로 바꿀까요?"(WS22 — PRD §8.0 선호 · §8.7 바로 반영). 영역을 넘는 선 · 제안 빈도만, 바꾸는 것은 사용자.
// 바꾸든 그대로 두든 고르면 서버가 그때를 기억하고, 그 뒤의 피드백만 다시 센다(같은 피드백으로 거듭 묻지 않게).
import { useEffect, useState } from "react";
import { getPrefSuggestions, markPrefSeen, type PrefSuggestion, type Settings } from "@/lib/api";

const LABEL = { cross_links: "다른 영역과 이어진 선 보이기", suggestions: "다음 걸음 제안 빈도" } as const;

export default function PrefSuggest({ onApply }: { onApply: (p: Partial<Settings>) => Promise<void> }) {
  const [list, setList] = useState<PrefSuggestion[]>([]);
  useEffect(() => { getPrefSuggestions().then((r) => setList(r.suggestions), () => { /* 제안은 없어도 됨 */ }); }, []);
  if (!list.length) return null;
  const pick = async (apply: boolean) => {
    if (apply) await onApply(Object.fromEntries(list.map((x) => [x.setting, x.to])) as Partial<Settings>);
    await markPrefSeen().catch(() => { /* 다음에 다시 물을 뿐 */ });
    setList([]);
  };
  return (
    <section className="card stack" aria-label="설정 제안">
      <h2 style={{ margin: 0 }}>이 설정으로 바꿀까요?</h2>
      {list.map((x) => (
        <p key={x.setting} style={{ margin: 0 }}>
          <b>{LABEL[x.setting]}</b>: {x.from} → <b>{x.to}</b><br /><span className="sub">{x.reason}</span>
        </p>
      ))}
      <div className="row">
        <button onClick={() => pick(true)}>제안대로 바꾸기</button>
        <button onClick={() => pick(false)}>그대로 두기</button>
      </div>
    </section>
  );
}
