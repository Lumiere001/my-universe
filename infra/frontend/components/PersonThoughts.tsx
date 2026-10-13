"use client";
// 그 사람과 얽힌 생각(먼저 쓴 기록부터, PRD §7 '사람'). 우주에서 사람을 고르거나 사람 목록에서 펼치면 보인다.
import { useEffect, useState } from "react";
import { unquote } from "@/components/ResultCard";
import { getPersonThoughts, type PersonThoughts as Data } from "@/lib/api";
import { useKindName } from "@/lib/use";

export default function PersonThoughts({ id, onPlanet }: { id: string; onPlanet?: (entryId: string) => void }) {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const kindName = useKindName();
  useEffect(() => {
    setD(null); setErr("");
    getPersonThoughts(id).then(setD, () => setErr("불러오지 못했어요. 잠시 뒤 다시 해 주세요."));
  }, [id]);

  if (err) return <p className="err" role="alert">{err}</p>;
  if (!d) return <p className="sub">불러오는 중…</p>;
  if (!d.thoughts.length) return <p className="sub">이 사람과 얽힌 생각이 아직 없어요.</p>;
  return (
    <ol data-testid="person-thoughts" style={{ paddingLeft: 18, margin: "6px 0 0" }}>
      {d.thoughts.map((t) => (
        <li key={t.id} style={{ marginBottom: 10 }}>
          <div className="sub">
            {t.written_at.slice(0, 10)} · {onPlanet
              ? <button className="small" onClick={() => onPlanet(t.entry_id)} aria-label={`${t.title} 행성 보기`}>{t.title}</button>
              : t.title}
          </div>
          <div style={{ marginTop: 4 }}><span className="badge v">{kindName(t.kind)}</span> {t.text}</div>
          {t.quote && <p className="quote">“{unquote(t.quote)}”</p>}
        </li>
      ))}
    </ol>
  );
}
