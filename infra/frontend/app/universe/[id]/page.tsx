"use client";
// 행성 카드의 '결과 카드 보기': 그 기록의 결과 카드(지난 기록 화면과 같은 카드)
import Link from "next/link";
import { useParams } from "next/navigation";
import ResultCard from "@/components/ResultCard";
import { getDiary } from "@/lib/api";
import { useLoad } from "@/lib/use";

export default function EntryPage() {
  const { id } = useParams<{ id: string }>();
  const [r, err] = useLoad(() => getDiary(decodeURIComponent(id)));
  return (
    <main>
      <Link href="/universe" className="btn" style={{ marginBottom: 12 }}>← 우주로</Link>
      {err ? <p className="err" role="alert">{err}</p> : r ? <ResultCard r={r} /> : <p className="sub">불러오는 중…</p>}
      {r && <p><Link href={`/talk?from=${encodeURIComponent(r.id)}`}>이 이야기 이어 하기</Link></p>}
    </main>
  );
}
