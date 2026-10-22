"use client";
// (사) 지난 기록: 달별 파일 목록(옵시디언 느낌). 누르면 그 글의 결과 카드(+ 지우기). /history?id=<기록> 이면 그 기록을 바로 연다
// (사이드바 '지난 기록'에서 누를 때마다 주소의 id 가 바뀌므로 useSearchParams 로 따라간다).
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { DeleteEntry } from "@/components/EntryTools";
import ResultCard from "@/components/ResultCard";
import { DownloadJson } from "@/components/ResultCard";
import { getDiary, listDiary, type EntryResult, type EntrySummary } from "@/lib/api";
import { useLoad } from "@/lib/use";

const month = (e: EntrySummary) => (e.day ?? e.written_at).slice(0, 7);

function History() {
  const router = useRouter();
  const id = useSearchParams().get("id");
  const [data, err] = useLoad(listDiary);
  const [more, setMore] = useState<EntrySummary[]>([]);
  const [end, setEnd] = useState(false);
  const [open, setOpen] = useState<EntryResult | null>(null);
  const [openErr, setOpenErr] = useState("");
  const [gone, setGone] = useState<string[]>([]);   // 지운 기록
  useEffect(() => {
    setOpen(null); setOpenErr("");
    if (id) getDiary(id).then(setOpen, () => setOpenErr("이 기록을 불러오지 못했어요. 지워졌거나 연결이 끊겼을 수 있어요."));
  }, [id]);
  const show = (x: string | null) => router.push(x ? `/history?id=${encodeURIComponent(x)}` : "/history");

  if (id) return (
    <main>
      <button className="small" onClick={() => show(null)} style={{ marginBottom: 12 }}>← 목록으로</button>
      {openErr ? <p className="err" role="alert">{openErr}</p> : !open ? <p className="sub">기록을 여는 중…</p> : (
        <>
          <ResultCard r={open} onChange={setOpen} />
          <p><Link href={`/?from=${encodeURIComponent(open.id)}`}>이 이야기 이어 하기</Link></p>
          <DeleteEntry id={open.id} onDeleted={() => { setGone([...gone, open.id]); show(null); }} />
        </>
      )}
    </main>
  );

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub">불러오는 중…</p></main>;
  const list = [...data.entries, ...more].filter((e) => !gone.includes(e.id));
  const months = [...new Set(list.map(month))];

  const loadMore = async () => {
    const r = await listDiary(list[list.length - 1]?.written_at);
    setMore([...more, ...r.entries.filter((e) => !list.some((x) => x.id === e.id))]);
    if (r.entries.length < 20) setEnd(true);
  };

  return (
    <main>
      <h1>지난 기록</h1>
      {gone.length > 0 && <p className="toast" role="status">기록을 지웠어요.</p>}
      {list.length === 0 && <p className="sub">아직 쓴 글이 없어요.</p>}
      {list.length > 0 && <div style={{ marginBottom: 12 }}><DownloadJson label="전체 기록 JSON 내려받기" /></div>}
      {months.map((m) => (
        <section key={m} className="files" aria-label={`${+m.slice(0, 4)}년 ${+m.slice(5)}월`}>
          <h2>{+m.slice(0, 4)}년 {+m.slice(5)}월</h2>
          {list.filter((e) => month(e) === m).map((e) => (
            <button key={e.id} className="file" onClick={() => show(e.id)}>
              <b>{e.title}</b>
              <span className="meta">{e.day ?? e.written_at.slice(0, 10)}{e.day_check ? " · 날짜 확인 필요" : ""}{e.weather ? ` · ${e.weather}` : ""}{e.sun ? ` · ${e.sun}` : ""}{e.star ? ` › ${e.star}` : ""}</span>
              <span className="sum">{e.summary}</span>
            </button>
          ))}
        </section>
      ))}
      {list.length >= 20 && !end && <button onClick={loadMore}>더 보기</button>}
    </main>
  );
}

export default function HistoryPage() {
  return <Suspense fallback={<main><p className="sub">불러오는 중…</p></main>}><History /></Suspense>;
}
