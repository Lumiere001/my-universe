"use client";
// (다) 3D 우주 v8 + 행성 요약 카드 + 사람 고르기 + 범례(/ontology 의 universe_symbols)
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { FeedbackButtons } from "@/components/ResultCard";
import type { Pick } from "@/components/Universe3D";
import { getDiary, getMe, getUniverse, type EntryResult } from "@/lib/api";
import { useKindName, useLoad, useOntology } from "@/lib/use";

const Universe3D = dynamic(() => import("@/components/Universe3D"), { ssr: false, loading: () => <div className="uni" /> });

export default function UniversePage() {
  const [data, err] = useLoad(getUniverse);
  const [me] = useLoad(getMe);
  const onto = useOntology();
  const kindName = useKindName();
  const [pick, setPick] = useState<Pick>({ kind: "none", id: null });
  const [person, setPerson] = useState<string | null>(null);
  const [entry, setEntry] = useState<EntryResult | null>(null);

  const planet = pick.kind === "planet" ? data?.planets.find((p) => p.id === pick.id) : undefined;
  useEffect(() => {
    setEntry(null);
    if (planet) getDiary(planet.id).then(setEntry, () => setEntry(null));
  }, [planet?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const glow = useMemo(() => {
    const p = data?.people.find((x) => x.id === person);
    return p ? new Set(p.planets) : null;
  }, [data, person]);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main className="wide"><div className="uni" /><p className="sub">우주를 불러오는 중…</p></main>;

  const title = (id: string) => data.planets.find((p) => p.id === id)?.title ?? id;
  const links = planet ? data.links.filter((l) => l.from_planet === planet.id || l.to_planet === planet.id) : [];
  const bh = pick.kind === "blackhole" ? data.blackholes.find((b) => b.id === pick.id) : undefined;
  const close = () => setPick({ kind: "none", id: null });

  return (
    <main className="wide">
      <h1 className="sr">나의 우주</h1>
      <Universe3D data={data} selected={planet?.id ?? null} glow={glow} crossLinks={me?.settings.cross_links ?? "눌렀을 때"} onPick={setPick}>
        <div className="tools" role="group" aria-label="사람 고르기">
          {data.people.map((p) => (
            <button key={p.id} className="small" aria-pressed={person === p.id} onClick={() => setPerson(person === p.id ? null : p.id)}>
              {p.name} <span className="sub">{p.relation}</span>
            </button>
          ))}
          {glow?.size === 0 && <span className="badge" role="status">이 사람이 나온 기록이 아직 없어요</span>}
        </div>

        {planet && (
          <section className="pcard" aria-label="기록 요약" data-testid="planet-card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>{planet.title}</h2>
              <button className="small" onClick={close} aria-label="닫기">닫기</button>
            </div>
            <p className="sub">{planet.written_at.slice(0, 10)}{planet.weather ? ` · ${planet.weather}` : ""}{planet.ring ? " · 금빛 고리(다짐)" : ""}
              {" · "}{data.stars.find((s) => s.id === planet.star_id)?.name}</p>
            {entry?.info ? <p>{entry.info.summary}</p> : <p className="sub">불러오는 중…</p>}
            {entry && entry.thoughts.length > 0 && (
              <ul style={{ paddingLeft: 18, margin: "0 0 8px" }}>
                {entry.thoughts.map((t) => <li key={t.id}><span className="badge v">{kindName(t.kind)}</span> {t.text}</li>)}
              </ul>
            )}
            {links.map((l) => {
              const other = l.from_planet === planet.id ? l.to_planet : l.from_planet;
              return (
                <div key={l.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 8 }}>
                  <div className="row">
                    <span className={"badge " + (["긴장", "어긋남", "목표 충돌"].includes(l.type) ? "o" : "v")}>{l.type}</span>
                    <span className="badge">{l.line}</span>
                    {l.cross_domain && <span className="badge">다른 영역</span>}
                    <span className="sub">{title(other)}</span>
                  </div>
                  <p className="sub" style={{ margin: "4px 0" }}>{l.explanation}</p>
                  {l.line === "점선" && l.needs_confirm && <FeedbackButtons label="이 연결이 맞나요" target="relation" targetId={l.id} values={["맞아요", "아니에요"]} />}
                </div>
              );
            })}
          </section>
        )}
        {pick.kind === "north" && data.north_star && (
          <section className="pcard" aria-label="북극성">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>북극성 · 되고 싶은 모습</h2>
              <button className="small" onClick={close}>닫기</button>
            </div>
            <p className="quote" style={{ borderColor: "var(--gold)" }}>“{data.north_star.text}”</p>
            <div className="row">{data.north_star.values.map((v) => <span key={v} className="badge g">{v}</span>)}</div>
          </section>
        )}
        {bh && (
          <section className="pcard" aria-label="블랙홀">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>오래 머문 고민</h2>
              <button className="small" onClick={close}>닫기</button>
            </div>
            <p>{bh.label} · {bh.size}번 다시 나왔어요.</p>
            <ul style={{ paddingLeft: 18 }}>{bh.planets.map((id) => <li key={id}>{title(id)}</li>)}</ul>
          </section>
        )}
      </Universe3D>

      <p className="sub" style={{ marginTop: 8 }}>한 손가락으로 돌리고, 두 손가락으로 확대해요. 해를 누르면 그 영역으로 다가가고, 빈 곳을 누르면 전체로 돌아와요.</p>

      <details className="card">
        <summary>범례</summary>
        <div className="legend" style={{ marginTop: 10 }}>
          {onto?.universe_symbols.map((s) => <div key={s.name}><b>{s.name}</b> · {s.legend}</div>)}
        </div>
      </details>

      <details className="card">
        <summary>기록 목록으로 고르기</summary>
        <div className="row" style={{ marginTop: 10 }}>
          {[...data.planets].sort((a, b) => a.written_at.localeCompare(b.written_at)).map((p) => (
            <button key={p.id} className="small" onClick={() => setPick({ kind: "planet", id: p.id })}>{p.title}</button>
          ))}
        </div>
      </details>
    </main>
  );
}
