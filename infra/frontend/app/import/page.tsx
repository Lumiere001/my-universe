"use client";
// 인스타그램 ZIP 가져오기(WS17). ZIP 을 브라우저에서 풀어(zip.ts) 글 목록 · 예상 시간 · 비용을 먼저 보여 주고,
// 사용자가 '전부 / 최근 N편'을 고르면 고른 글 중 오래된 것부터 한 편씩 /diary/stream 으로 보낸다(다짐 · 질문 상태가 글 순서대로 바뀌게).
// 상한 없음(결정 12, 서버 IMPORT_MAX_POSTS 가 있으면 그 안). 멈추면 지금 글까지 정리하고 서고, 이어 하기는 다음 글부터.
// 새로고침한 뒤에는 ZIP 을 다시 고르면 된다: 이미 가져온 글은 서버가 표시하고(imported), 같은 원본을 또 보내도 새 기록을 만들지 않는다.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  getDiary, previewInstagram, resumeDiary, writeDiary, type EntryResult, type ImportPost, type ImportPreview, type Progress,
  type StreamError,
} from "@/lib/api";
import { chunks, readPosts } from "./zip";

type Done = { post: ImportPost; id: string | null; dup: boolean; failed: string | null };
type Phase = "pick" | "reading" | "preview" | "running" | "paused" | "done";

const minutes = (s: number) => (s < 3600 ? `${Math.max(1, Math.round(s / 60))}분` : `${Math.floor(s / 3600)}시간 ${Math.round((s % 3600) / 60)}분`);
const label = (p: ImportPost) => p.title || (p.text.length > 24 ? p.text.slice(0, 24) + "…" : p.text);
const sleep = (ms: number) => new Promise((ok) => setTimeout(ok, ms));

export default function ImportPage() {
  const [phase, setPhase] = useState<Phase>("pick");
  const [err, setErr] = useState("");
  const [pv, setPv] = useState<ImportPreview | null>(null);
  const [mode, setMode] = useState<"all" | "recent">("all");
  const [n, setN] = useState(10);
  const [queue, setQueue] = useState<ImportPost[]>([]);
  const [at, setAt] = useState(0);
  const [prog, setProg] = useState<Progress | null>(null);
  const [done, setDone] = useState<Done[]>([]);
  const stop = useRef(false);
  const [stopping, setStopping] = useState(false);

  // 정리하는 동안 창을 닫으려 하면 한 번 묻는다(닫아도 지금 글은 서버가 끝까지 정리함)
  useEffect(() => {
    if (phase !== "running") return;
    const warn = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [phase]);

  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setErr(""); setPhase("reading"); setDone([]);
    try {
      const posts = await readPosts(f);
      const parts = await Promise.all(chunks(posts).map(previewInstagram));
      const all = parts.flatMap((x) => x.posts).sort((a, b) => b.written_at.localeCompare(a.written_at));
      if (!all.length) throw new Error("글이 있는 게시물을 찾지 못했어요(사진만 있는 게시물은 가져오지 않아요).");
      setPv({ ...parts[0], posts: all });
      setN(Math.max(1, Math.min(10, all.filter((p) => !p.imported && !p.too_long).length)));
      setPhase("preview");
    } catch (x) {
      setErr(x instanceof SyntaxError ? "게시물 파일을 읽지 못했어요. 인스타그램에서 받은 파일 그대로 골라 주세요." : (x as Error).message || "파일을 읽지 못했어요.");
      setPhase("pick");
    }
  };

  const fresh = pv ? pv.posts.filter((p) => !p.imported && !p.too_long) : [];
  const limit = Math.min(fresh.length, pv?.max_posts ?? Infinity);
  const count = Math.max(0, Math.min(limit, mode === "all" ? limit : n));

  // 멈춘 글(같은 원본 · 끊김)은 상태를 보고 끝났으면 결과, 멈췄으면 이어 하기, 정리 중이면 기다린다(쓰기 화면과 같음)
  const cont = async (id: string): Promise<EntryResult> => {
    for (;;) {
      const r = await getDiary(id);
      if (r.status === "done") return r;
      if (r.status === "failed") return resumeDiary(id, { onProgress: setProg });
      await sleep(3000);
    }
  };
  const one = async (p: ImportPost): Promise<EntryResult> => {
    try {
      return await writeDiary({ title: p.title, text: p.text, written_at: p.written_at, source: "지난 글 묶음", source_ref: p.ref },
        { onProgress: setProg });
    } catch (e) {
      const x = e as StreamError;
      if (x.entry_id && x.resumable) return cont(x.entry_id);
      throw x;
    }
  };

  const run = async (q: ImportPost[], from: number) => {
    stop.current = false; setStopping(false); setErr(""); setPhase("running");
    const lock = await navigator.wakeLock?.request("screen").catch(() => null);   // 휴대폰 화면이 꺼져 멈추지 않게
    try {
      for (let i = from; i < q.length; i++) {
        setAt(i); setProg(null);
        if (stop.current) { setPhase("paused"); return; }
        try {
          const r = await one(q[i]);
          setDone((d) => [...d, { post: q[i], id: r.id, dup: !!r.duplicate, failed: null }]);
        } catch (e) {
          const x = e as StreamError;
          if ((x.entry_id && !x.resumable) || x.code === "invalid_input") {   // 이 글만 못 함(이름 가리기 문제 등) → 다음 글로
            setDone((d) => [...d, { post: q[i], id: x.entry_id, dup: false, failed: x.message }]);
            continue;
          }
          setErr(x.message || "잠시 멈췄어요."); setPhase("paused"); return;   // 서버 · 연결 · 동의 문제: 멈추고 이어 하기
        }
      }
      setAt(q.length); setPhase("done");
    } finally {
      lock?.release().catch(() => {});
    }
  };
  const start = () => {
    const q = fresh.slice(0, count).reverse();   // 최근 count 편을 오래된 것부터
    setQueue(q); setDone([]); run(q, 0);
  };

  const newly = done.filter((d) => d.id && !d.dup && !d.failed).length;
  const dups = done.filter((d) => d.dup).length;
  const fails = done.filter((d) => d.failed).length;

  return (
    <main>
      <h1>인스타그램에서 가져오기</h1>
      {(phase === "pick" || phase === "reading") && (
        <section className="card stack" aria-label="ZIP 고르기">
          <p style={{ margin: 0 }}>인스타그램에 써 온 일기를 한꺼번에 우주로 옮겨요.</p>
          <ol className="sub" style={{ margin: 0, paddingLeft: 20 }}>
            <li>인스타그램 앱 → 설정 → 계정 센터 → 내 정보 다운로드</li>
            <li>형식은 <b>JSON</b>을 고르고(사진 화질은 낮음이면 충분해요), 받은 ZIP 파일을 아래에서 골라요.</li>
          </ol>
          <div>
            <label htmlFor="zip">ZIP 파일(또는 posts_1.json)</label>
            <input id="zip" type="file" accept=".zip,.json,application/zip,application/json" disabled={phase === "reading"} onChange={pick} />
          </div>
          {phase === "reading" && <p className="sub" role="status" style={{ margin: 0 }}>게시물을 읽는 중…</p>}
          <p className="sub" style={{ margin: 0 }}>
            사진 · 영상은 읽지 않고 글만 가져와요. 글을 정리할 때 다른 사람 이름은 가명으로 바꿔 보내요. ·{" "}
            <a href="/samples/instagram-virtual-dodam.zip" download>예시 ZIP 받기</a>
          </p>
          {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
        </section>
      )}

      {phase === "preview" && pv && (
        <section className="card stack" aria-label="가져올 글">
          <h2 style={{ margin: 0 }}>글 {pv.posts.length}편을 찾았어요</h2>
          <p className="sub" style={{ margin: 0 }}>
            {pv.posts.some((p) => p.parts > 1) && `이어 쓴 게시물은 한 편으로 묶었어요. `}
            {pv.posts.length - fresh.length > 0 && `이미 가져왔거나 너무 긴 글 ${pv.posts.length - fresh.length}편은 건너뛰어요.`}
          </p>
          <ol aria-label="글 목록(최근 것부터)" style={{ maxHeight: 260, overflowY: "auto", margin: 0, paddingLeft: 22 }}>
            {pv.posts.map((p) => (
              <li key={p.ref} style={{ color: p.imported || p.too_long ? "var(--muted)" : undefined }}>
                <span className="sub">{p.day}{p.day_basis === "추정" ? "(게시일)" : ""}</span> {label(p)}
                {p.parts > 1 && <span className="sub"> · 게시물 {p.parts}개</span>}
                {p.imported && <span className="sub"> · 이미 가져옴</span>}
                {p.too_long && <span className="sub"> · 너무 길어 건너뜀</span>}
              </li>
            ))}
          </ol>
          {fresh.length === 0 ? <p className="toast" role="status" style={{ margin: 0 }}>새로 가져올 글이 없어요.</p> : (
            <>
              <fieldset>
                <legend>몇 편을 가져올까요?</legend>
                <label className="row" style={{ margin: 0 }}>
                  <input type="radio" name="how" checked={mode === "all"} onChange={() => setMode("all")} style={{ width: "auto" }} />
                  전부 {limit}편{pv.max_posts && fresh.length > pv.max_posts ? ` (한 번에 최근 ${pv.max_posts}편까지)` : ""}
                </label>
                <label className="row" style={{ margin: 0 }}>
                  <input type="radio" name="how" checked={mode === "recent"} onChange={() => setMode("recent")} style={{ width: "auto" }} />
                  최근
                  <input type="number" aria-label="최근 몇 편" min={1} max={limit} value={n} style={{ width: 80 }}
                    onChange={(e) => { setMode("recent"); setN(Math.max(1, Math.min(limit, Number(e.target.value) || 1))); }} />
                  편
                </label>
              </fieldset>
              <p style={{ margin: 0 }} aria-live="polite">
                <b>{count}편</b> · 예상 시간 약 {minutes(count * pv.est_seconds_per_post)} · 예상 비용 약 ${(count * pv.est_usd_per_post).toFixed(2)}
              </p>
              <p className="sub" style={{ margin: 0 }}>
                편당 약 {Math.round(pv.est_seconds_per_post / 60)}분 · ${pv.est_usd_per_post.toFixed(2)}(어림값). 고른 글 중 오래된 것부터 한 편씩 정리해요.
                정리하는 동안 이 화면을 켜 두세요. 언제든 멈추고 이어 할 수 있어요.
              </p>
              <button className="primary" onClick={start} disabled={count < 1}>가져오기 시작</button>
            </>
          )}
          <button className="small" onClick={() => { setPv(null); setPhase("pick"); }}>다른 파일 고르기</button>
        </section>
      )}

      {(phase === "running" || phase === "paused" || phase === "done") && (
        <section className="card stack" aria-label="가져오기 진행" aria-live="polite">
          <h2 style={{ margin: 0 }}>{phase === "running" ? "가져오는 중" : phase === "paused" ? "멈췄어요" : "다 가져왔어요"}</h2>
          <progress value={done.length} max={queue.length} style={{ width: "100%" }} aria-label="가져온 글 수" />
          <p style={{ margin: 0 }}>{done.length} / {queue.length}편 · 새로 정리 {newly}편{dups ? ` · 이미 있던 글 ${dups}편` : ""}{fails ? ` · 못 한 글 ${fails}편` : ""}</p>
          {phase === "running" && queue[at] && (
            <p className="sub" style={{ margin: 0 }}>지금: {queue[at].day} {label(queue[at])}{prog ? ` · ${prog.label}` : ""}</p>
          )}
          {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
          {phase === "running" && (
            <button onClick={() => { stop.current = true; setStopping(true); }} disabled={stopping}>
              {stopping ? "지금 글까지 정리하고 멈춰요…" : "멈추기"}
            </button>
          )}
          {phase === "paused" && <button className="primary" onClick={() => run(queue, at)}>이어 하기 ({queue.length - at}편 남음)</button>}
          {phase !== "running" && (
            <p style={{ margin: 0 }}><Link href="/universe">우주 보기</Link> · <Link href="/history">지난 기록</Link></p>
          )}
        </section>
      )}

      {done.length > 0 && (
        <section className="card" aria-label="가져온 글">
          <ol style={{ margin: 0, paddingLeft: 22 }}>
            {done.map((d) => (
              <li key={d.post.ref}>
                {d.id ? <Link href={`/history?id=${encodeURIComponent(d.id)}`}>{d.post.day} {label(d.post)}</Link> : <>{d.post.day} {label(d.post)}</>}
                {d.dup && <span className="sub"> · 이미 있던 글</span>}
                {d.failed && <span className="err"> · {d.failed}</span>}
              </li>
            ))}
          </ol>
        </section>
      )}
    </main>
  );
}
