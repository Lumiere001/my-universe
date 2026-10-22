"use client";
// (다) 3D 우주 v8 + 행성 요약 카드(원문 인용 · 그때 → 지금 · 결과 카드 링크) + 북극성(닿은 순간) + 사람 고르기(얽힌 생각) + 범례
// + 우주 고치기(WS16: 해 추가 · 작은 별 옮기기 · 합치기, 행성 카드에서 생각 종류 · 가치 고치기)
import dynamic from "next/dynamic";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import PersonThoughts from "@/components/PersonThoughts";
import { FeedbackButtons, unquote } from "@/components/ResultCard";
import type { Pick } from "@/components/Universe3D";
import { CONFLICT } from "@/components/universeLook";
import { getDiary, getMe, getUniverse, type EntryResult } from "@/lib/api";
import { useKindName, useLoad, useOntology } from "@/lib/use";
import EditPanel, { ThoughtFix } from "./EditPanel";

const Universe3D = dynamic(() => import("@/components/Universe3D"), { ssr: false, loading: () => <div className="uni" /> });
// 기호 뜻 2판 문장(docs/content/U-03). 온톨로지 legend 는 별지기 규칙과 같은 파일이라 손대지 않고 여기서 덮는다.
// ponytail: 문장이 두 곳에 있음. 온톨로지 legend 를 2판으로 바꾸기로 정하면 이 표를 지운다.
const LEGEND: Record<string, string> = {
  해: "삶의 영역이에요. 기록이 많을수록 커요. 일기에 나온 영역과 내가 추가한 해만 떠요.",
  "작은 별": "해 곁의 세부 주제예요. 기록 행성들이 그 둘레를 돌아요.",
  행성: "일기 한 편이에요. 작은 별에 가까울수록 먼저 쓴 기록이고, 생각이 많을수록 크고, 확신이 클수록 밝아요. '?'는 아직 답을 못 낸 질문이 있다는 뜻이에요.",
  쌍행성: "둘 다 아직 결론이 나지 않은, 서로 맞서는 두 생각이에요.",
  "금빛 고리": "다짐이 담긴 기록이에요. 다짐을 지키면 고리가 채워져요.",
  "영역을 넘는 선": "다른 영역과 이어진 선은 처음에는 행성을 눌렀을 때만 보여요. 설정에서 바꿀 수 있어요.",
  색: "보라는 이어지는 관계(이어짐 · 바뀜 · 해소), 주황은 맞서는 관계(긴장 · 어긋남 · 목표 충돌)예요.",
};

export default function UniversePage() {
  const [data, err, reload] = useLoad(getUniverse, "우주를 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const [me] = useLoad(getMe);
  const onto = useOntology();
  const kindName = useKindName();
  const [pick, setPick] = useState<Pick>({ kind: "none", id: null });
  const [person, setPerson] = useState<string | null>(null);
  const [entry, setEntry] = useState<EntryResult | null>(null);
  const [entryErr, setEntryErr] = useState(false);

  const planet = pick.kind === "planet" ? data?.planets.find((p) => p.id === pick.id) : undefined;
  useEffect(() => {
    setEntry(null); setEntryErr(false);
    if (planet) getDiary(planet.id).then(setEntry, () => setEntryErr(true));
  }, [planet?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // 빛남: 북극성을 누르면 닿은 순간이 있는 행성, 아니면 고른 사람이 나온 행성
  const glow = useMemo(() => {
    // 닿은 순간이 아직 없으면 아무것도 흐리게 하지 않는다
    if (pick.kind === "north" && data?.north_star) return data.north_star.reached_planets?.length ? new Set(data.north_star.reached_planets) : null;
    const p = data?.people.find((x) => x.id === person);
    return p ? new Set(p.planets) : null;
  }, [data, person, pick.kind]);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main className="wide"><div className="uni" /><p className="sub">우주를 불러오는 중…</p></main>;

  const title = (id: string) => data.planets.find((p) => p.id === id)?.title ?? id;
  const day = (id: string) => data.planets.find((p) => p.id === id)?.written_at.slice(0, 10) ?? "";
  const who = data.people.find((p) => p.id === person);
  const toPlanet = (id: string) => setPick({ kind: "planet", id });
  const links = planet ? data.links.filter((l) => l.from_planet === planet.id || l.to_planet === planet.id) : [];
  const bh = pick.kind === "blackhole" ? data.blackholes.find((b) => b.id === pick.id) : undefined;
  const close = () => setPick({ kind: "none", id: null });

  return (
    <main className="wide">
      <h1 className="sr">나의 우주</h1>
      <p className="sub" style={{ marginTop: 0 }}>행성 하나가 일기 한 편이에요. 이어진 선을 따라가면 지난 생각이 어떻게 이어지고 바뀌었는지 보여요.</p>
      {!data.planets.length && <p className="sub" role="status">아직 우주가 비어 있어요. 이야기하기나 직접 쓰기로 첫 기록을 남기면 첫 행성이 떠요.</p>}
      <Universe3D data={data} selected={planet?.id ?? null} glow={glow} crossLinks={me?.settings.cross_links ?? "눌렀을 때"} onPick={setPick}
        theme={me?.settings.theme}>
        <div className="tools" role="group" aria-label="사람 고르기">
          {data.people.map((p) => (
            <button key={p.id} className="small" aria-pressed={person === p.id} onClick={() => setPerson(person === p.id ? null : p.id)}>
              {p.name} <span className="sub">{p.relation}</span>
            </button>
          ))}
          {glow?.size === 0 && pick.kind !== "north" && <span className="badge" role="status">이 사람이 나온 기록이 아직 없어요</span>}
        </div>

        {planet && (
          <section className="pcard" aria-label="기록 요약" data-testid="planet-card">
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>{planet.title}</h2>
              <button className="small" onClick={close} aria-label="카드 닫기">닫기</button>
            </div>
            <p className="sub">{planet.written_at.slice(0, 10)}{planet.weather ? ` · ${planet.weather}` : ""}{planet.ring ? " · 금빛 고리(다짐)" : ""}
              {" · "}{data.stars.find((s) => s.id === planet.star_id)?.name}</p>
            {entry?.info ? <p>{entry.info.summary}</p> : entryErr ? <p className="err" role="alert">이 기록의 요약을 불러오지 못했어요. 잠시 뒤 행성을 다시 눌러 주세요.</p>
              : <p className="sub">요약을 불러오는 중…</p>}
            {entry && entry.thoughts.length > 0 && (
              <ul style={{ paddingLeft: 18, margin: "0 0 8px" }}>
                {entry.thoughts.map((t) => (
                  <li key={t.id}><span className="badge v">{kindName(t.kind)}</span>{t.value && <span className="badge">가치 · {t.value}</span>} {t.text}
                    {t.quote && <p className="quote">“{unquote(t.quote)}”</p>}
                    <ThoughtFix key={`${t.kind}|${t.value}`} t={t} onFixed={(x) => {
                      setEntry((e) => e && { ...e, thoughts: e.thoughts.map((y) => (y.id === x.id ? x : y)) }); reload();
                    }} /></li>
                ))}
              </ul>
            )}
            <Link href={`/universe/${encodeURIComponent(planet.id)}`}>정리한 결과 보기</Link>
            {" · "}<Link href={`/?from=${encodeURIComponent(planet.id)}`}>이 이야기 이어 하기</Link>
            {links.map((l) => {
              const other = l.from_planet === planet.id ? l.to_planet : l.from_planet;
              const q = "quote" + (CONFLICT.has(l.type) && !l.ended ? " o" : "");
              return (
                <div key={l.id} style={{ borderTop: "1px solid var(--line)", paddingTop: 8, marginTop: 8 }}>
                  <div className="row">
                    <span className={"badge " + (l.ended ? "" : CONFLICT.has(l.type) ? "o" : "v")}>{l.type}</span>
                    {l.ended && <span className="badge">끝난 목표 충돌</span>}
                    <span className="badge">{l.line === "실선" ? "실선 · 글에 직접 씀" : "점선 · AI 추정"}</span>
                    {l.cross_domain && <span className="badge">다른 영역</span>}
                    <span className="sub">{title(other)}</span>
                  </div>
                  {l.from_quote && <p className={q}>그때 {day(l.from_planet)}: “{unquote(l.from_quote)}”</p>}
                  {l.to_quote && <p className={q}>지금 {day(l.to_planet)}: “{unquote(l.to_quote)}”</p>}
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
            <h3 style={{ margin: "12px 0 4px", fontSize: "1rem" }}>닿은 순간</h3>
            {data.north_star.reached?.length ? (
              <ol data-testid="north-reached" style={{ paddingLeft: 18, margin: 0 }}>
                {data.north_star.reached.map((r) => (
                  <li key={r.entry_id + r.quote}>
                    <span className="sub">{r.at.slice(0, 10)} · </span>
                    <button className="small" onClick={() => toPlanet(r.entry_id)}>{title(r.entry_id)}</button>
                    <p className="quote" style={{ borderColor: "var(--gold)" }}>“{unquote(r.quote)}”</p>
                  </li>
                ))}
              </ol>
            ) : <p className="sub">아직 닿은 순간이 없어요. 글에서 되고 싶은 모습에 닿으면 여기에 모여요.</p>}
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
        {who && !planet && !bh && pick.kind !== "north" && (
          <section className="pcard" aria-label={`${who.name}과(와) 얽힌 생각`}>
            <div className="row" style={{ justifyContent: "space-between" }}>
              <h2 style={{ margin: 0 }}>{who.name}과(와) 얽힌 생각</h2>
              <button className="small" onClick={() => setPerson(null)}>닫기</button>
            </div>
            <PersonThoughts id={who.id} onPlanet={toPlanet} />
          </section>
        )}
      </Universe3D>

      <p className="sub" style={{ marginTop: 8 }}>끌어서 돌리고, 두 손가락이나 마우스 휠로 크게 봐요. 해를 누르면 그 영역으로 다가가고, 빈 곳을 누르면 전체로 돌아와요.</p>

      <details className="card">
        <summary>기호 뜻 보기</summary>
        <div className="legend" style={{ marginTop: 10 }}>
          {onto?.universe_symbols.map((s) => <div key={s.name}><b>{s.name}</b> · {LEGEND[s.name] ?? s.legend}</div>)}
        </div>
      </details>

      <details className="card">
        <summary>목록에서 기록 고르기</summary>
        <div className="row" style={{ marginTop: 10 }}>
          {[...data.planets].sort((a, b) => a.written_at.localeCompare(b.written_at)).map((p) => (
            <button key={p.id} className="small" onClick={() => setPick({ kind: "planet", id: p.id })}>{p.title}</button>
          ))}
        </div>
      </details>

      <EditPanel data={data} onChanged={reload} />
    </main>
  );
}
