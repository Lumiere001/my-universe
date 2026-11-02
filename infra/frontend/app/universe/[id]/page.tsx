"use client";
// 행성 카드의 '일기 보기': 그 일기 한 편(일기장과 같은 카드). 돌아가기는 머리줄 '뒤로'(같은 단추를 두 번 두지 않음)
import Link from "next/link";
import { useParams } from "next/navigation";
import ResultCard from "@/components/ResultCard";
import { getDiary } from "@/lib/api";
import { useLoad } from "@/lib/use";

export default function EntryPage() {
  const { id } = useParams<{ id: string }>();
  const [r, err] = useLoad(() => getDiary(decodeURIComponent(id)), "이 일기를 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  return (
    <main className="stack">
      {err ? <p className="err" role="alert">{err}</p> : r ? <ResultCard r={r} /> : <p className="sub">일기를 불러오는 중…</p>}
      {r && <Link className="btn small rc-next" href={`/?from=${encodeURIComponent(r.id)}`}>이 이야기 이어 하기</Link>}
    </main>
  );
}
