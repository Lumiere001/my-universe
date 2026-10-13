"use client";
// (사) 지난 기록 목록. 누르면 그 글의 결과 카드(+ 지우기). /history?id=<기록> 이면 그 기록을 바로 연다.
import Link from "next/link";
import { useEffect, useState } from "react";
import { DeleteEntry } from "@/components/EntryTools";
import ResultCard from "@/components/ResultCard";
import { DownloadJson } from "@/components/ResultCard";
import { getDiary, listDiary, type EntryResult, type EntrySummary } from "@/lib/api";
import { useLoad } from "@/lib/use";

export default function HistoryPage() {
  const [data, err] = useLoad(listDiary);
  const [more, setMore] = useState<EntrySummary[]>([]);
  const [end, setEnd] = useState(false);
  const [open, setOpen] = useState<EntryResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [gone, setGone] = useState<string[]>([]);   // 지운 기록
  useEffect(() => {
    const id = new URLSearchParams(window.location.search).get("id");
    if (id) getDiary(id).then(setOpen, () => {});
  }, []);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub">불러오는 중…</p></main>;
  const list = [...data.entries, ...more].filter((e) => !gone.includes(e.id));

  if (open) return (
    <main>
      <button className="small" onClick={() => setOpen(null)} style={{ marginBottom: 12 }}>← 목록으로</button>
      <ResultCard r={open} onChange={setOpen} />
      <p><Link href={`/?from=${encodeURIComponent(open.id)}`}>이 이야기 이어 하기</Link></p>
      <DeleteEntry id={open.id} onDeleted={() => { setGone([...gone, open.id]); setOpen(null); }} />
    </main>
  );

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
      {list.map((e) => (
        <button key={e.id} className="card" style={{ display: "block", width: "100%", textAlign: "left" }} disabled={loading === e.id}
          onClick={async () => { setLoading(e.id); try { setOpen(await getDiary(e.id)); } finally { setLoading(null); } }}>
          <span className="sub">{e.day ?? e.written_at.slice(0, 10)}{e.day_check ? " · 날짜 확인 필요" : ""}{e.weather ? ` · ${e.weather}` : ""}{e.sun ? ` · ${e.sun}` : ""}{e.star ? ` › ${e.star}` : ""}</span>
          <b style={{ display: "block" }}>{e.title}</b>
          <span style={{ display: "block", color: "var(--muted)" }}>{e.summary}</span>
        </button>
      ))}
      {list.length >= 20 && !end && <button onClick={loadMore}>더 보기</button>}
    </main>
  );
}
