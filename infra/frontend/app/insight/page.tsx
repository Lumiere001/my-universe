"use client";
// 나에 대해 알게 된 것(docs/content/U-11): GET /insight 를 해마다 — 자주 쓴 주제(작은 별) | 이어 온 · 바뀐 · 맞서는 · 정리된 · 다른 영역과 이어진 생각.
// AI 요약 · 판정 없이 날짜와 원문 인용만(서버 app/service/rules/insight.py). 날짜를 누르면 그 기록(/history?id=).
// 한 화면: PC 두 칸 · 휴대폰 위아래, 목록은 그 칸 안에서만 넘긴다. 묶음은 한 번에 하나만 펼치는 접는 칸, 처음에는 내용이 있는 첫 묶음.
import Link from "next/link";
import { useState } from "react";
import { unquote } from "@/components/ResultCard";
import { CONFLICT } from "@/components/universeLook";
import { getInsight, type InsightEnd, type InsightPair } from "@/lib/api";
import { useKindName, useLoad } from "@/lib/use";

const LINE = { 실선: "실선 · 글에 직접 씀", 점선: "점선 · AI 추정" };

function End({ e, label, o }: { e: InsightEnd; label?: string; o?: boolean }) {
  return (
    <p className={o ? "quote o" : "quote"}>
      {label && <>{label} </>}<Link href={`/history?id=${encodeURIComponent(e.record_id)}`}>{e.day}</Link>: “{unquote(e.quote)}”
    </p>
  );
}

function Pair({ p, labels, o }: { p: InsightPair; labels?: [string, string]; o?: boolean }) {
  return (
    <li>
      <div className="row tight"><b>{p.star}</b>{p.axis && <span className="sub">· {p.axis}</span>}{p.line && <span className="badge">{LINE[p.line]}</span>}</div>
      <End e={p.from} label={labels?.[0]} o={o} />
      <End e={p.to} label={labels?.[1]} o={o} />
    </li>
  );
}

const Back = () => <Link href="/universe" className="btn">← 우주로 돌아가기</Link>;

export default function InsightPage() {
  const [data, err] = useLoad(getInsight, "알게 된 것을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const kindName = useKindName();
  const [pick, setPick] = useState<string | null>(null);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub" role="status">나에 대해 알게 된 것을 불러오는 중…</p></main>;
  if (!data.period || !data.suns.length) return (
    <main className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}><h1 style={{ margin: 0 }}>나에 대해 알게 된 것</h1><Back /></div>
      <p className="sub">아직 모을 생각이 없어요. <Link href="/">이야기하기</Link>나 <Link href="/write">직접 쓰기</Link>로 기록을 남기면, 쌓인 기록에서 알게 된 것을 여기에 모아요.</p>
    </main>
  );

  const { period, suns, across } = data;
  const sun = suns.find((s) => s.name === pick) ?? suns[0];
  const bare = suns.every((s) => !s.kept.length && !s.changed.length && !s.open.length && !s.settled.length) && !across.length;
  const groups: { name: string; lead: string; empty: string; items: React.ReactNode[] }[] = [
    { name: "이어 온 생각", lead: "같은 주제로 다시 쓴 생각이에요. 처음과 마지막 문장을 보여 드려요.", empty: "같은 주제를 다시 쓰면 이어 온 생각이 여기에 모여요.",
      items: sun.kept.map((k) => (
        <li key={k.star}>
          <div className="row tight"><b>{k.star}</b><span className="sub">· {k.times}번 이어졌어요</span></div>
          <End e={k.from} label="처음" /><End e={k.to} label="마지막" />
        </li>
      )) },
    { name: "바뀐 생각", lead: "같은 주제에서 예전과 다르게 쓴 생각이에요.", empty: "예전과 다르게 생각한 문장이 나오면 여기에 모여요.",
      items: sun.changed.map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} labels={["그때", "지금"]} />) },
    { name: "아직 맞서는 생각", lead: "서로 맞서는데 아직 정리한 글이 없는 두 생각이에요.", empty: "지금 서로 맞서 있는 생각은 없어요.",
      items: sun.open.map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} o />) },
    { name: "정리된 생각", lead: "맞서던 생각을 나중에 정리한 글이에요.", empty: "맞서던 생각을 정리한 문장이 나오면 여기에 모여요.",
      items: sun.settled.map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} labels={["그때", "정리"]} />) },
    { name: "다른 영역과 이어진 생각", lead: "다른 해의 생각과 이어진 것이에요.", empty: "다른 영역과 이어진 생각은 아직 없어요.",
      items: across.filter((a) => a.suns.includes(sun.name)).map((a) => {
        const o = CONFLICT.has(a.type);
        return (
          <li key={a.type + a.from.thought_id + a.to.thought_id}>
            <div className="row tight"><span className={o ? "badge o" : "badge v"}>{a.type}</span><span className="sub">{a.suns.join(" ↔ ")}</span></div>
            <End e={a.from} label={a.suns[0]} o={o} /><End e={a.to} label={a.suns[1]} o={o} />
          </li>
        );
      }) },
  ];
  const first = groups.findIndex((g) => g.items.length);

  return (
    <main className="ins">
      <div className="ins-head"><h1>나에 대해 알게 된 것</h1><Back /></div>
      <p className="ins-lead">{period.from === period.to ? period.from : `${period.from} ~ ${period.to}`}에 남긴 기록 {period.records}편에서, 내 생각이 어디에 오래 머물고 어떻게 이어지고 바뀌었는지 모았어요.</p>
      {bare && <p className="sub" role="status" style={{ margin: 0 }}>아직 서로 이어진 생각이 없어요. 기록이 쌓일수록 이어지고 바뀐 생각이 여기에 모여요.</p>}
      <p className="ins-note">내가 쓴 문장과 날짜만 그대로 옮겼어요. <span className="badge">점선 · AI 추정</span>이 붙은 연결은 AI가 짐작한 것이라 틀릴 수 있어요.</p>
      {suns.length > 1 && (
        <div className="row tight" role="group" aria-label="해 고르기">
          {suns.map((s) => (
            <button key={s.name} className="small" aria-pressed={s === sun} onClick={() => setPick(s.name)}>{s.name} <span className="sub">{s.records}편</span></button>
          ))}
        </div>
      )}
      <div className="ins-body" key={sun.name}>
        <section className="ins-stars" aria-label="자주 쓴 주제">
          <h2>자주 쓴 주제</h2>
          <ul>
            {sun.stars.map((s) => (
              <li key={s.name}>
                <b>{s.name}</b> <span className="meta">{s.records}편 · {s.first === s.last ? s.first : `${s.first} ~ ${s.last}`}</span>
                <div className="row tight">{Object.entries(s.kinds).map(([k, n]) => <span key={k} className="badge">{kindName(k)} {n}</span>)}</div>
              </li>
            ))}
          </ul>
        </section>
        <section className="ins-groups" aria-label="생각 묶음">
          {groups.map((g, i) => (
            <details key={g.name} name="ins-group" open={i === first}>
              <summary>{g.name} <span className="n">{g.items.length}</span></summary>
              <p className="sub">{g.items.length ? g.lead : g.empty}</p>
              {g.items.length > 0 && <ul>{g.items}</ul>}
            </details>
          ))}
        </section>
      </div>
    </main>
  );
}
