"use client";
// (사) 지난 기록(docs/content/U-04): 머리줄(달력 | 주제별 · 찾기 · ⋯) + 달력(또는 주제 목록) + 고른 날(또는 주제 · 찾은) 기록 목록.
// 한 화면에 들어가게 PC 는 두 칸 나란히, 휴대폰은 위아래로 두고 목록만 안에서 넘긴다(globals.css 'C: 달력 · 사이드바').
// 기록을 누르면 /history?id=<기록> 로 그 결과 카드(+ 이어 하기 · 지우기). /history?day=YYYY-MM-DD 는 그날을 고른 달력(사이드바 작은 달력).
// 같은 화면 안에서 주소만 바뀌므로(useSearchParams) 보기 · 찾기 · 고른 날은 기록을 열었다 돌아와도 그대로다.
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import Calendar, { countByDay, dayOf, monthDay, useEntries, WEEK } from "@/components/Calendar";
import { DeleteEntry, localToday } from "@/components/EntryTools";
import ResultCard, { DownloadJson } from "@/components/ResultCard";
import { getDiary, type EntryResult, type EntrySummary } from "@/lib/api";

const NONE = "주제 없음";
type Pick = { sun: string; star: string };
const DAY = /^\d{4}-\d{2}-\d{2}$/;

// 해 › 작은 별을 기록 수가 많은 것부터
function topicsOf(list: EntrySummary[]) {
  const suns = new Map<string, Map<string, number>>();
  for (const e of list) {
    const m = suns.get(e.sun ?? NONE) ?? new Map<string, number>();
    m.set(e.star ?? NONE, (m.get(e.star ?? NONE) ?? 0) + 1);
    suns.set(e.sun ?? NONE, m);
  }
  const most = (a: [string, number], b: [string, number]) => b[1] - a[1] || a[0].localeCompare(b[0], "ko");
  return [...suns].map(([sun, m]) => ({ sun, n: [...m.values()].reduce((a, b) => a + b, 0), stars: [...m].sort(most) }))
    .sort((a, b) => b.n - a.n || a.sun.localeCompare(b.sun, "ko"));
}

function Item({ e, withDay, onOpen }: { e: EntrySummary; withDay: boolean; onOpen: (id: string) => void }) {
  const meta = [withDay && dayOf(e), e.day_check && "날짜 확인 필요", e.weather, e.sun && (e.star ? `${e.sun} › ${e.star}` : e.sun)];
  return (
    <li>
      <button className="file" onClick={() => onOpen(e.id)}>
        <b>{e.title || "제목 없는 글"}</b>
        <span className="meta">{meta.filter(Boolean).join(" · ")}</span>
        <span className="sum">{e.summary}</span>
      </button>
    </li>
  );
}

function History() {
  const router = useRouter();
  const params = useSearchParams();
  const id = params.get("id"), dayParam = params.get("day");
  const [list, err] = useEntries();
  const [view, setView] = useState<"cal" | "topic">("cal");
  const [sel, setSel] = useState<string | null>(null);   // 고른 날(없으면 가장 최근 기록의 날)
  const [star, setStar] = useState<Pick | null>(null);   // 고른 작은 별(없으면 가장 많은 것)
  const [find, setFind] = useState("");
  const [open, setOpen] = useState<EntryResult | null>(null);
  const [openErr, setOpenErr] = useState("");
  const [gone, setGone] = useState<string[]>([]);   // 지운 기록
  const fromList = useRef(false);   // 이 화면 목록에서 열었으면 '돌아가기' = 뒤로(고른 날 · 보기 · 찾기 그대로)
  const applied = useRef<string | null>(null);
  useEffect(() => {
    setOpen(null); setOpenErr("");
    if (id) getDiary(id).then(setOpen, () => setOpenErr("이 기록을 열지 못했어요. 잠시 뒤 다시 눌러 주세요."));
    else fromList.current = false;
  }, [id]);
  // ?day= 는 새 날일 때만 따른다(기록을 열었다 같은 주소로 돌아올 때 보기를 바꾸지 않게)
  useEffect(() => {
    if (!dayParam || !DAY.test(dayParam) || dayParam === applied.current) return;
    applied.current = dayParam;
    setSel(dayParam); setView("cal"); setFind("");
  }, [dayParam]);

  const openEntry = (x: string) => { fromList.current = true; router.push(`/history?id=${encodeURIComponent(x)}`); };
  const back = (day?: string) => {
    if (fromList.current) router.back();
    else router.push(day ? `/history?day=${day}` : "/history");
  };
  const pickDay = (d: string) => {
    applied.current = d;
    setSel(d); setFind("");
    window.history.replaceState(null, "", `/history?day=${d}`);   // 주소만(서버에 묻지 않음). 사이드바 작은 달력도 같은 날을 보인다
  };

  if (id) return (
    <main>
      <button className="small" onClick={() => back(open?.day)} style={{ marginBottom: 12 }}>← 목록으로 돌아가기</button>
      {openErr ? <p className="err" role="alert">{openErr}</p> : !open ? <p className="sub">기록을 여는 중…</p> : (
        <>
          <ResultCard r={open} onChange={setOpen} />
          <p><Link href={`/?from=${encodeURIComponent(open.id)}`}>이 이야기 이어 하기</Link></p>
          <DeleteEntry id={open.id} onDeleted={() => { setGone([...gone, open.id]); back(open.day); }} />
        </>
      )}
    </main>
  );

  if (err && !list) return <main><p className="err" role="alert">{err}</p></main>;
  if (!list) return <main><p className="sub">지난 기록을 불러오는 중…</p></main>;
  const all = list.filter((e) => !gone.includes(e.id));
  const latest = all.reduce((m, e) => (dayOf(e) > m ? dayOf(e) : m), "");
  const day = sel ?? (latest || localToday());
  const topics = topicsOf(all);
  const pick = star ?? (topics[0] ? { sun: topics[0].sun, star: topics[0].stars[0][0] } : null);
  const words = find.trim().toLowerCase();

  const found = words ? all.filter((e) => `${e.title}\n${e.summary}`.toLowerCase().includes(words)) : null;
  const [title, items, withDay, empty]: [string, EntrySummary[], boolean, string] = found
    ? [`찾은 기록 ${found.length}편`, found, true, "맞는 기록이 없어요."]
    : view === "topic"
      ? [pick ? `${pick.sun} › ${pick.star}` : "", all.filter((e) => pick && (e.sun ?? NONE) === pick.sun && (e.star ?? NONE) === pick.star), true, ""]
      : [`${monthDay(day)} ${WEEK[new Date(day + "T00:00").getDay()]}요일`, all.filter((e) => dayOf(e) === day), false, "이날은 남긴 기록이 없어요."];

  return (
    <main className="hist">
      <div className="hist-head">
        <h1>지난 기록</h1>
        <div className="seg" role="group" aria-label="보기">
          <button type="button" aria-pressed={view === "cal"} onClick={() => setView("cal")}>달력</button>
          <button type="button" aria-pressed={view === "topic"} onClick={() => setView("topic")}>주제별</button>
        </div>
        <input type="search" aria-label="찾기" placeholder="제목 · 요약에서 찾기" value={find} onChange={(e) => setFind(e.target.value)} />
        {all.length > 0 && (
          <details className="pop">
            <summary aria-label="더 보기">⋯</summary>
            <div><DownloadJson label="모든 기록 파일로 내려받기(JSON)" /></div>
          </details>
        )}
      </div>
      <p className="sub hist-lead">지난 글을 다시 열면, 그 글이 어떤 지난 생각과 이어졌는지 함께 보여요.</p>
      {all.length === 0 ? (
        <>
          {gone.length > 0 && <p className="toast" role="status">기록을 지웠어요.</p>}
          <p className="sub">아직 남긴 기록이 없어요. 이야기하기나 직접 쓰기로 첫 기록을 남겨 보세요.</p>
        </>
      ) : (
        <div className="hist-body">
          <section className="hist-pane" aria-label={view === "cal" ? "달력" : "주제별"}>
            {view === "cal" ? <Calendar marks={countByDay(all)} selected={day} onPick={pickDay} /> : (
              <div className="topics">
                {topics.map((t) => (
                  <div key={t.sun}>
                    <h2>{t.sun} <span className="n">{t.n}<span className="sr">편</span></span></h2>
                    <ul>
                      {t.stars.map(([s, n]) => (
                        <li key={s}>
                          <button type="button" aria-pressed={pick?.sun === t.sun && pick.star === s} aria-label={`${s}, 기록 ${n}편`}
                            onClick={() => { setStar({ sun: t.sun, star: s }); setFind(""); }}>
                            <span>{s}</span><span className="n">{n}</span>
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            )}
          </section>
          <section className="hist-list" aria-labelledby="hist-list-h">
            <h2 id="hist-list-h">{title}</h2>
            {gone.length > 0 && <p className="toast" role="status">기록을 지웠어요.</p>}
            {items.length > 0
              ? <ul>{items.map((e) => <Item key={e.id} e={e} withDay={withDay} onOpen={openEntry} />)}</ul>
              : empty && <p className="sub">{empty}</p>}
          </section>
        </div>
      )}
    </main>
  );
}

export default function HistoryPage() {
  return <Suspense fallback={<main><p className="sub">지난 기록을 불러오는 중…</p></main>}><History /></Suspense>;
}
