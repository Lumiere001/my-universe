"use client";
// 나에 대해 알게 된 것(docs/content/U-11): GET /insight 를 해마다 — 자주 쓴 주제(작은 별) | 바뀐 · 맞서는 · 정리된 · 이어 온 · 다른 영역과 이어진 생각.
// AI 요약 · 판정 없이 날짜와 원문 인용만(서버 app/service/rules/insight.py). 날짜를 누르면 그 기록(/history?id=).
// 한 화면: PC 두 칸 · 휴대폰 위아래, 목록은 그 칸 안에서만 넘긴다. 묶음은 한 줄 고르기(탭), 처음에는 내용이 있는 첫 묶음.
// 점선(AI 추정) 카드에는 '이 연결이 맞나요? 맞아요 · 아니에요'(우주의 점선과 같은 POST /feedback) — 사용자가 매긴 정답이 개인 고리로 간다.
import Link from "next/link";
import { useState } from "react";
import { unquote } from "@/components/ResultCard";
import { CONFLICT } from "@/components/universeLook";
import { getInsight, sendFeedback, type InsightEnd, type InsightPair } from "@/lib/api";
import { useKindName, useLoad } from "@/lib/use";

const LINE = { 실선: "실선 · 글에 직접 씀", 점선: "점선 · AI 추정" };

// 2026-07-11 → 7월 11일(마지막 날과 해가 다르면 2025년 7월 11일)
const josa = (w: string) => { const c = w.charCodeAt(w.length - 1) - 0xac00; return c >= 0 && c < 11172 && c % 28 ? "과" : "와"; };   // 받침 있으면 '과'
const day = (d: string, year?: string) => { const [y, m, dd] = d.split("-"); return `${y === year ? "" : `${y}년 `}${+m}월 ${+dd}일`; };

// more: 같은 기록의 다른 문장(두 기록 사이 관계를 카드 하나로 합쳤을 때, rules.insight._cards)
function End({ e, more = [], label, year, o }: { e: InsightEnd; more?: InsightEnd[]; label?: string; year: string; o?: boolean }) {
  return (
    <div className={o ? "ins-q o" : "ins-q"}>
      <span className="ins-when">{label && <>{label} · </>}<Link href={`/history?id=${encodeURIComponent(e.record_id)}`}>{day(e.day, year)}</Link></span>
      <div className="ins-qs">{[e, ...more.filter((x) => x.thought_id !== e.thought_id)].map((x) => <p key={x.thought_id}>“{unquote(x.quote)}”</p>)}</div>
    </div>
  );
}

type Said = Record<string, "맞아요" | "아니에요">;
type Say = (rids: string[], v: "맞아요" | "아니에요") => void;
const ridsOf = (p: { rid?: string | null; rids?: string[] }) => p.rids ?? (p.rid ? [p.rid] : []);   // 합친 카드는 점선 관계 모두

function Card({ title, meta, line, rids = [], said, onSay, children }: { title: React.ReactNode; meta?: string; line?: keyof typeof LINE | null;
  rids?: string[]; said?: Said; onSay?: Say; children: React.ReactNode }) {
  const shown = rids.length && rids.every((r) => said?.[r] === "맞아요") ? "실선" : line;   // 맞아요 → 실선(우주와 같음)
  return (
    <li className="ins-card">
      <div className="ins-card-head">{title}{meta && <span className="sub">{meta}</span>}{shown && <span className="badge">{LINE[shown]}</span>}</div>
      {children}
      {shown === "점선" && rids.length > 0 && onSay && (
        <div className="ins-check" role="group" aria-label="이 연결이 맞나요?">
          <span className="sub">이 연결이 맞나요?</span>
          <button className="small" onClick={() => onSay(rids, "맞아요")}>맞아요</button>
          <button className="small" onClick={() => onSay(rids, "아니에요")}>아니에요</button>
        </div>
      )}
    </li>
  );
}

function Pair({ p, labels, year, o, said, onSay }: { p: InsightPair; labels?: [string, string]; year: string; o?: boolean; said: Said; onSay: Say }) {
  return (
    <Card title={<b>{p.star}</b>} meta={p.axis} line={p.line} rids={ridsOf(p)} said={said} onSay={onSay}>
      <End e={p.from} more={p.froms} label={labels?.[0]} year={year} o={o} />
      <End e={p.to} more={p.tos} label={labels?.[1]} year={year} o={o} />
    </Card>
  );
}

const Back = () => <Link href="/universe" className="btn">← 우주로 돌아가기</Link>;

export default function InsightPage() {
  const [data, err] = useLoad(getInsight, "알게 된 것을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const kindName = useKindName();
  const [pick, setPick] = useState<string | null>(null);
  const [tab, setTab] = useState<string | null>(null);
  const [said, setSaid] = useState<Said>({});
  const say: Say = (rids, v) => rids.forEach((rid) => {
    setSaid((m) => ({ ...m, [rid]: v }));
    sendFeedback({ target: "relation", target_id: rid, value: v }).catch(() => setSaid((m) => { const n = { ...m }; delete n[rid]; return n; }));
  });
  const keep = (p: { rid?: string | null; rids?: string[] }) => !ridsOf(p).some((r) => said[r] === "아니에요");   // 아니에요 → 그 연결은 지워져 카드도 빠진다

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub" role="status">나에 대해 알게 된 것을 불러오는 중…</p></main>;
  if (!data.period || !data.suns.length) return (
    <main className="stack">
      <div className="row" style={{ justifyContent: "space-between" }}><h1 style={{ margin: 0 }}>나에 대해 알게 된 것</h1><Back /></div>
      <p className="sub">아직 모을 생각이 없어요. <Link href="/">이야기하기</Link>나 <Link href="/write">직접 쓰기</Link>로 기록을 남기면, 쌓인 기록에서 알게 된 것을 여기에 모아요.</p>
    </main>
  );

  const { period, suns, across } = data;
  const year = period.to.slice(0, 4);
  const sun = suns.find((s) => s.name === pick) ?? suns[0];
  // 다섯째 탭은 상대 해 이름으로(두 영역이면 「인간관계와 이어진」), 해가 셋 이상이면 「다른 영역과 이어진」
  const others = suns.filter((s) => s !== sun).map((s) => s.name);
  const other = others.length === 1 ? others[0] : null;
  const across1 = other ? `${other}${josa(other)} 이어진` : "다른 영역과 이어진";
  const bare = suns.every((s) => !s.kept.length && !s.changed.length && !s.open.length && !s.settled.length) && !across.length;
  const groups: { name: string; tab: string; lead: string; empty: string; items: React.ReactNode[] }[] = [
    { name: "바뀐 생각", tab: "바뀐", lead: "같은 주제에서 예전과 다르게 쓴 생각이에요.", empty: "예전과 다르게 생각한 문장이 나오면 여기에 모여요.",
      items: sun.changed.filter(keep).map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} labels={["그때", "지금"]} year={year} said={said} onSay={say} />) },
    { name: "아직 맞서는 생각", tab: "맞서는", lead: "서로 맞서는데 아직 정리한 글이 없는 두 생각이에요.", empty: "지금 서로 맞서 있는 생각은 없어요.",
      items: sun.open.filter(keep).map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} year={year} o said={said} onSay={say} />) },
    { name: "정리된 생각", tab: "정리된", lead: "맞서던 생각을 나중에 정리한 글이에요.", empty: "맞서던 생각을 정리한 문장이 나오면 여기에 모여요.",
      items: sun.settled.filter(keep).map((p) => <Pair key={p.from.thought_id + p.to.thought_id} p={p} labels={["그때", "정리"]} year={year} said={said} onSay={say} />) },
    { name: "이어 온 생각", tab: "이어 온", lead: "같은 주제로 다시 쓴 생각이에요. 처음과 마지막 문장을 보여 드려요.", empty: "같은 주제를 다시 쓰면 이어 온 생각이 여기에 모여요.",
      items: sun.kept.map((k) => (
        <Card key={k.star} title={<b>{k.star}</b>} meta={`${k.times}번 이어졌어요`}>
          <End e={k.from} label="처음" year={year} /><End e={k.to} label="마지막" year={year} />
        </Card>
      )) },
    { name: "다른 영역과 이어진 생각", tab: across1, lead: `${other ?? "다른 해"}의 생각과 이어진 것이에요.`, empty: `${across1} 생각은 아직 없어요.`,
      items: across.filter((a) => a.suns.includes(sun.name) && keep(a)).map((a) => {
        const o = CONFLICT.has(a.type);
        return (
          <Card key={a.type + a.from.thought_id + a.to.thought_id} title={<span className={o ? "badge o" : "badge v"}>{a.type}</span>} meta={a.suns.join(" ↔ ")}
            line={a.line} rids={ridsOf(a)} said={said} onSay={say}>
            <End e={a.from} label={a.suns[0]} year={year} o={o} /><End e={a.to} label={a.suns[1]} year={year} o={o} />
          </Card>
        );
      }) },
  ];
  const g = groups.find((x) => x.name === tab) ?? groups.find((x) => x.items.length) ?? groups[0];
  const most = Math.max(1, ...sun.stars.map((s) => s.records));
  const when = (a: string, b: string) => (a === b ? day(a, year) : `${day(a, year)} ~ ${day(b, year)}`);

  return (
    <main className="ins">
      <div className="ins-head"><h1>나에 대해 알게 된 것</h1><Back /></div>
      <p className="ins-lead">{period.from === period.to ? day(period.from) : `${day(period.from)} ~ ${day(period.to, period.from.slice(0, 4))}`}에 남긴 기록 {period.records}편에서, 내 생각이 어디에 오래 머물고 어떻게 이어지고 바뀌었는지 모았어요.</p>
      {bare && <p className="sub" role="status" style={{ margin: 0 }}>아직 서로 이어진 생각이 없어요. 기록이 쌓일수록 이어지고 바뀐 생각이 여기에 모여요.</p>}
      <div className="ins-bar-row">
        {suns.length > 1 && (
          <div className="row tight" role="group" aria-label="해 고르기">
            {suns.map((s) => (
              <button key={s.name} className="small" aria-pressed={s === sun} onClick={() => { setPick(s.name); setTab(null); }}>{s.name} <span className="sub">{s.records}편</span></button>
            ))}
          </div>
        )}
        <p className="ins-note">내가 쓴 문장과 날짜만 그대로 옮겼어요. <span className="badge">점선 · AI 추정</span>이 붙은 연결은 AI가 짐작한 것이라 틀릴 수 있어요.</p>
      </div>
      <div className="ins-body" key={sun.name}>
        <section className="ins-stars" aria-label="자주 쓴 주제">
          <h2>자주 쓴 주제</h2>
          <ul>
            {sun.stars.map((s) => (
              <li key={s.name}>
                <div className="ins-star"><b>{s.name}</b><span className="n">{s.records}편</span></div>
                <i className="ins-freq" style={{ width: `${(s.records / most) * 100}%` }} aria-hidden />
                <p className="meta">{[when(s.first, s.last), ...Object.entries(s.kinds).map(([k, n]) => `${kindName(k)} ${n}`)].join(" · ")}</p>
              </li>
            ))}
          </ul>
        </section>
        <section className="ins-groups" aria-label="생각 묶음">
          <h2>이어지고 바뀐 생각</h2>
          <div className="seg ins-tabs" role="group" aria-label="생각 묶음 고르기">
            {groups.map((x) => (
              <button key={x.name} aria-pressed={x === g} className={x.items.length ? undefined : "none"} onClick={() => setTab(x.name)}>
                {x.tab} <span className="n">{x.items.length}</span>
              </button>
            ))}
          </div>
          <p className="sub ins-lead2">{g.items.length ? g.lead : g.empty}</p>
          {g.items.length > 0 && <ul className="ins-list">{g.items}</ul>}
        </section>
      </div>
    </main>
  );
}
