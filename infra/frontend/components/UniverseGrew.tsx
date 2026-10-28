"use client";
// 일기에서 찾은 것으로 우주 넓히기(꾸미기 WS25, PRD §9 '우주 꾸미기'): 이 기록에서 우주에 처음 나온 해 · 작은 별 · 사람을 별지기가 알려 준다.
// LLM 호출 없음(우주 API 로 계산). 위로만 하는 글(위기 · 비 · 천둥 · '오늘은 위로만')과 같은 글 다시 보내기에는 띄우지 않는다.
import Link from "next/link";
import { useEffect, useState } from "react";
import { getUniverse, type EntryResult, type Universe } from "@/lib/api";
import { useKeeperName } from "./Keeper";
import { grewFrom } from "./universeLook";

// 결과 카드 여러 장(넓어진 우주 · 해 › 작은 별 · 같은 주제)이 우주를 한 번만 읽는다. 기록이 바뀌면(lib/api 'entries' 알림) 다시 읽는다.
// ponytail: 우주 고치기(작은 별 옮기기 · 합치기)는 알림을 내지 않아 새로 고침 전까지 옛 작은 별이 보일 수 있음. 헷갈린다는 말이 나오면 거기서도 알림
let uni: Promise<Universe> | null = null;
export const universeOnce = () => (uni ??= getUniverse().catch((e) => { uni = null; throw e; }));
if (typeof window !== "undefined") window.addEventListener("entries", () => { uni = null; });

export default function UniverseGrew({ r }: { r: EntryResult }) {
  const keeper = useKeeperName();
  const quiet = r.status !== "done" || r.crisis || r.message?.mode === "comfort" || !!r.duplicate;
  const [g, setG] = useState<ReturnType<typeof grewFrom> | null>(null);
  // ponytail: 우주 전체를 읽어 계산한다. 기록이 아주 많아 무거워지면 EntryResult 에 칸(grew)으로 옮긴다.
  useEffect(() => {
    setG(null);
    if (!quiet) universeOnce().then((u) => setG(grewFrom(u, r.id)), () => setG(null));
  }, [r.id, quiet]);
  if (quiet || !g) return null;
  const parts = ([["새 해", g.suns.map((x) => `「${x}」`)], ["새 작은 별", g.stars.map((x) => `「${x}」`)], ["처음 나온 사람", g.people]] as const)
    .filter(([, xs]) => xs.length).map(([k, xs]) => `${k} ${xs.join(" · ")}`);
  if (!parts.length) return null;
  return (
    <section className="card" aria-label="넓어진 우주" data-testid="universe-grew">
      <div className="voice">
        <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
        <div className="bubble">
          <p style={{ margin: 0 }}>이 글로 우주가 넓어졌어요. {parts.join(", ")}.</p>
          <Link href="/universe">우주에서 보기</Link>
        </div>
      </div>
    </section>
  );
}
