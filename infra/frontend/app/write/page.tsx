"use client";
// (가) 일기 쓰기 → 진행 단계 → (나) 결과 카드
// 일기장(2026-10-28, 한 화면 규칙): 별지기 한 줄 · 종이 한 장(날짜 줄 · 제목 · 마음 날씨 · 줄 그은 글 칸 또는 미리보기 · 도구 줄) · 띄우기 줄.
// 진행 상황은 화면 아래에 뜨는 작은 칸. 별지기에게는 마크다운을 그리기 전의 쓴 글 그대로 보낸다.
import Link from "next/link";
import { useEffect, useState } from "react";
import Icon from "@/components/Icon";
import MicButton from "@/components/MicButton";   // WS21 말로 쓰기: 받아쓴 글을 칸에 채움
import PhotoInput from "@/components/PhotoInput";
import ResultCard from "@/components/ResultCard";
import { localToday } from "@/components/EntryTools";
import { DuplicateNote, EntryMeta, FilePick, KeeperPrompt, Markdown, WriteHelp } from "@/components/WriteParts";
import { FAIL, getDiary, resumeDiary, writeDiary, type EntryResult, type Progress, type StreamError, type Weather } from "@/lib/api";
import { useOntology } from "@/lib/use";

// 정리 중인 기록 id. 새로고침 · 끊김 뒤에도 '이어서 하기'를 보이려고 이 탭에만 둔다.
const PENDING = "pending-entry";
const keep = (id: string | null) => { try { if (id) sessionStorage.setItem(PENDING, id); else sessionStorage.removeItem(PENDING); } catch { /* 저장소 막힘 */ } };

export default function WritePage() {
  const onto = useOntology();
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [day, setDay] = useState("");   // 글이 다루는 날(비우면 오늘 · 글 속 날짜)
  const [ref, setRef] = useState("");   // 불러온 파일 표시(고치면 지움)
  const [photo, setPhoto] = useState(false);   // 사진에서 읽은 글(source=사진, 고쳐도 사진 출처 그대로)
  const [weather, setWeather] = useState<Weather | null>(null);
  const [busy, setBusy] = useState(false);
  const [prog, setProg] = useState<Progress | null>(null);
  const [steps, setSteps] = useState<string[]>([]);
  const [err, setErr] = useState<StreamError | null>(null);
  const [result, setResult] = useState<EntryResult | null>(null);
  const [waiting, setWaiting] = useState(false);
  const [preview, setPreview] = useState(false);   // 쓰기 | 미리보기

  useEffect(() => { if (result) window.scrollTo(0, 0); }, [result]);
  const onProgress = (p: Progress) => { keep(p.entry_id); setWaiting(false); setProg(p); setSteps((s) => (s.includes(p.label) ? s : [...s, p.label])); };

  // 끊기면 상태를 먼저 보고, 이미 끝났으면 결과를, 아니면 "이어서 하기"를 보인다
  const fail = async (e: StreamError) => {
    if (e.entry_id && e.resumable) {
      const r = await getDiary(e.entry_id).catch(() => null);
      if (r?.status === "done") { keep(null); setResult(r); return; }
    }
    if (!e.resumable) keep(null);
    setErr(e);
  };
  const go = async (fn: () => Promise<EntryResult>) => {
    setBusy(true); setErr(null);
    try { setResult(await fn()); keep(null); } catch (e) { await fail(e as StreamError); } finally { setBusy(false); setWaiting(false); }
  };
  // 지난 기록 달력의 '일기 쓰기'에서 오면(?day=YYYY-MM-DD) 그날을 글이 다루는 날로(오늘 뒤는 버림)
  useEffect(() => {
    const d = new URLSearchParams(window.location.search).get("day");
    if (d && /^\d{4}-\d{2}-\d{2}$/.test(d) && d <= localToday()) setDay(d);
  }, []);
  // 새로고침해서 돌아오면, 정리하던 기록이 있는지 본다
  useEffect(() => {
    let id: string | null = null;
    try { id = sessionStorage.getItem(PENDING); } catch { /* 저장소 막힘 */ }
    if (id) fail({ entry_id: id, code: "disconnected", message: "정리하던 글이 있어요. 이어서 할까요?", resumable: true });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps
  // 서버가 아직 정리 중이면 끝날 때까지 기다리고, 멈췄으면 끝난 단계 다음부터 다시 돌린다
  const cont = async (id: string): Promise<EntryResult> => {
    try {
      for (;;) {
        const r = await getDiary(id);
        if (r.status === "done") return r;
        if (r.status === "failed") return await resumeDiary(id, { onProgress });
        setWaiting(true);
        await new Promise((ok) => setTimeout(ok, 3000));
      }
    } catch (e) {
      const x = e as StreamError;
      throw x.entry_id ? x : { entry_id: id, code: x.code ?? "network", message: x.message || "연결이 끊겼어요.", resumable: x.code !== "not_found" };
    }
  };
  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setSteps([]); setProg(null); setResult(null);
    go(() => writeDiary({ text, title, weather, ...(day && { day }), ...(ref && { source_ref: ref }), ...(photo && { source: "사진" as const }) }, { onProgress }));
  };
  const resume = () => err?.entry_id && go(() => cont(err.entry_id!));
  const again = () => { setText(""); setTitle(""); setDay(""); setRef(""); setPhoto(false); setWeather(null); setResult(null); setSteps([]); setProg(null); setPreview(false); window.scrollTo(0, 0); };

  if (result) return (
    <main>
      {result.duplicate && <DuplicateNote id={result.id} />}
      <ResultCard r={result} onChange={setResult} />
      <button onClick={again}>새 글 쓰기</button>
    </main>
  );

  const empty = !text.trim();
  return (
    <main className="write">
      <h1 className="sr">직접 쓰기</h1>
      <p className="sub" style={{ margin: 0 }}>글로 적으면 별지기가 생각 단위로 나눠 우주에 띄우고, 지난 기록과 이어 보여 드려요.</p>
      <KeeperPrompt />
      <form onSubmit={submit} className="diary-form" aria-label="일기 쓰기">
        <div className="paper">
          <EntryMeta title={title} day={day} weather={weather} weathers={onto?.weather ?? []} disabled={busy}
            onTitle={(v) => { setTitle(v); setRef(""); }} onDay={setDay} onWeather={setWeather}>
            <div className="seg" role="group" aria-label="보기">
              <button type="button" aria-pressed={!preview} onClick={() => setPreview(false)}>쓰기</button>
              <button type="button" aria-pressed={preview} onClick={() => setPreview(true)}>미리보기</button>
            </div>
          </EntryMeta>
          <div className="diary-body">
            <label htmlFor="diary" className="sr">마음껏 적어 주세요.</label>
            <textarea id="diary" className="editor diary-text" value={text} onChange={(e) => { setText(e.target.value); setRef(""); }} disabled={busy}
              placeholder="오늘 있었던 일, 떠오른 생각, 다짐…" hidden={preview} />
            {preview && (
              <article className="diary-text diary-view" aria-label="미리보기">
                {empty ? <p className="sub">오늘 있었던 일, 떠오른 생각, 다짐…</p> : <Markdown text={text} />}
              </article>
            )}
          </div>
          <div className="tools" role="group" aria-label="다른 방법으로 쓰기">
            <MicButton disabled={busy} onText={(t) => { setText((v) => (v.trim() ? `${v.trimEnd()}\n${t}` : t)); setRef(""); }} />
            <FilePick disabled={busy} onLoad={(f) => { setTitle(f.title); setText(f.text); setDay(f.day); setRef(f.ref); setPhoto(false); }} />
            <PhotoInput disabled={busy} onRead={(t) => { setText((x) => (x.trim() ? x.trimEnd() + "\n" + t : t)); setRef(""); setPhoto(true); }} />
            <Link className="tbtn import" href="/import" title="지난 일기 한꺼번에 가져오기"><Icon name="files" /><span>지난 일기 한꺼번에 가져오기</span></Link>
            <WriteHelp />
          </div>
        </div>
        <div className="diary-foot">
          <p className="sub"># 제목 · **굵게** · - 목록처럼 마크다운으로 써도 돼요.</p>
          <button type="submit" className="primary" disabled={busy || empty} aria-describedby={empty && !busy ? "write-empty" : undefined}
            title={empty && !busy ? "글을 한 줄이라도 적으면 띄울 수 있어요." : undefined}>{busy ? "정리하는 중…" : "우주에 띄우기"}</button>
          <span id="write-empty" className="sr">글을 한 줄이라도 적으면 띄울 수 있어요.</span>
        </div>
      </form>

      {(busy || steps.length > 0 || err) && (
        <section className="card progress-pop" aria-label="진행 상황" aria-live="polite">
          <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
            <h2 style={{ margin: 0 }}>{err && !busy ? (err.resumable ? "정리가 멈췄어요" : "정리하지 못했어요") : "정리하는 중"}</h2>
            {!busy && <button type="button" className="tbtn" aria-label="닫기" title="닫기"
              onClick={() => { setErr(null); setSteps([]); setProg(null); }}><Icon name="close" /></button>}
          </div>
          <ol className="steps">
            {steps.map((s, i) => <li key={s} className={i < steps.length - 1 || !busy ? "done" : "now"}>{s}</li>)}
          </ol>
          {prog && <p className="sub" style={{ margin: 0 }}>{prog.done} / {prog.total} 단계</p>}
          {waiting && <p className="sub" style={{ margin: 0 }}>화면이 끊긴 동안에도 서버에서 계속 정리하고 있어요. 끝나면 바로 보여 드릴게요.</p>}
          {err && (
            <div className="stack" role="alert">
              <p className="err" style={{ margin: 0 }}>{err.message || FAIL}</p>
              {err.resumable && err.entry_id ? <button className="primary" onClick={resume} disabled={busy}>이어서 하기</button>
                : err.code !== "duplicate" && <p className="sub" style={{ margin: 0 }}>글은 화면에 그대로 있어요. 잠시 뒤 다시 띄워 주세요.</p>}
            </div>
          )}
        </section>
      )}
    </main>
  );
}
