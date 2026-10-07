"use client";
// (사) 지난 기록 목록. 누르면 그 글의 결과 카드.
import { useState } from "react";
import ResultCard from "@/components/ResultCard";
import { getDiary, listDiary, type EntryResult, type EntrySummary } from "@/lib/api";
import { useLoad } from "@/lib/use";

export default function HistoryPage() {
  const [data, err] = useLoad(listDiary);
  const [more, setMore] = useState<EntrySummary[]>([]);
  const [end, setEnd] = useState(false);
  const [open, setOpen] = useState<EntryResult | null>(null);
  const [loading, setLoading] = useState<string | null>(null);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub">불러오는 중…</p></main>;
  const list = [...data.entries, ...more];

  if (open) return (
    <main>
      <button className="small" onClick={() => setOpen(null)} style={{ marginBottom: 12 }}>← 목록으로</button>
      <ResultCard r={open} />
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
      {list.length === 0 && <p className="sub">아직 쓴 글이 없어요.</p>}
      {list.map((e) => (
        <button key={e.id} className="card" style={{ display: "block", width: "100%", textAlign: "left" }} disabled={loading === e.id}
          onClick={async () => { setLoading(e.id); try { setOpen(await getDiary(e.id)); } finally { setLoading(null); } }}>
          <span className="sub">{e.written_at.slice(0, 10)}{e.weather ? ` · ${e.weather}` : ""}{e.sun ? ` · ${e.sun}` : ""}{e.star ? ` › ${e.star}` : ""}</span>
          <b style={{ display: "block" }}>{e.title}</b>
          <span style={{ display: "block", color: "var(--muted)" }}>{e.summary}</span>
        </button>
      ))}
      {list.length >= 20 && !end && <button onClick={loadMore}>더 보기</button>}
    </main>
  );
}
