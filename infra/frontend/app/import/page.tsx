"use client";
// 지난 일기 가져오기(WS17 + 2026-10-28 글 파일). 두 가지에서 가져온다(docs/content/U-08).
// - 글 파일 여러 개: .txt · .md 를 한꺼번에(또는 그런 파일을 묶은 ZIP). 파일 하나 = 일기 한 편. 제목 · 날짜는 쓰기 화면과 같은 규칙(readDiaryFile).
//   서버 미리 보기(인스타그램 전용)는 쓰지 않고 화면에서 목록을 만든다. 어림값은 서버 값(빈 미리 보기)을 받는다.
//   이미 가져온 파일인지는 미리 모른다: 같은 원본(source_ref = 파일 이름 + 글의 해시)을 /diary/stream 이 알아보고 다시 정리하지 않는다(duplicate).
// - 인스타그램 ZIP: ZIP 을 브라우저에서 풀어(zip.ts) 서버 미리 보기로 글 목록 · 이미 가져온 글을 받는다.
// 두 쪽 다 '전부 / 최근 N편'을 고르면 고른 글 중 오래된 것부터 한 편씩 /diary/stream 으로 보낸다(다짐 · 질문 상태가 글 순서대로 바뀌게).
// 상한 없음(결정 12, 서버 IMPORT_MAX_POSTS 가 있으면 그 안). 멈추면 지금 글까지 정리하고 서고, 이어 하기는 다음 글부터.
// 새로고침한 뒤에는 파일을 다시 고르면 된다: 같은 원본을 또 보내도 새 기록을 만들지 않는다.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  getDiary, previewInstagram, resumeDiary, writeDiary, type EntryResult, type ImportPost, type ImportPreview, type Progress,
  type StreamError, why,
} from "@/lib/api";
import { readDiaryFile } from "@/components/WriteParts";
import { chunks, localDay, readPosts, readTextFiles, titleDay, type TextFile } from "./zip";

// pick = 그대로 '글이 다루는 날'로 보냄(파일 이름 속 날짜), skip = 건너뛰는 까닭, modified = 파일을 저장한 때(같은 날이면 차례)
type Post = ImportPost & { pick?: string; skip?: string; modified?: number };
type Done = { post: Post; id: string | null; dup: boolean; failed: string | null };
type Phase = "pick" | "reading" | "preview" | "running" | "paused" | "done";
type Kind = "files" | "instagram";

const MAX_TEXT = 8000;   // 백엔드 MAX_TEXT_CHARS 기본값(넘으면 서버도 422, components/WriteParts.tsx 와 같음)
const LONG = `너무 길어 건너뜀(${MAX_TEXT.toLocaleString()}자까지)`;
const minutes = (s: number) => (s < 3600 ? `${Math.max(1, Math.round(s / 60))}분` : `${Math.floor(s / 3600)}시간 ${Math.round((s % 3600) / 60)}분`);
const label = (p: ImportPost) => p.title || (p.text.length > 24 ? p.text.slice(0, 24) + "…" : p.text);
const sleep = (ms: number) => new Promise((ok) => setTimeout(ok, ms));
const STEPS = ["고르기", "확인", "가져오기"];

// 같은 파일이면 같은 표시(이름 + 글). 다시 가져와도 서버가 알아보게
async function fileRef(name: string, raw: string) {
  const h = new Uint8Array(await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`${name}\n${raw}`)));
  return "파일:" + [...h.slice(0, 16)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

// 글 파일 → 가져올 글. 날: 파일 이름 속 날짜(그대로 보냄) → 제목 속 날짜(서버가 다시 읽음) → 저장한 날(추정)
async function filePost(f: TextFile): Promise<Post> {
  const name = f.name.split("/").pop()!;
  const r = readDiaryFile(name, f.raw);
  const saved = new Date(f.modified);
  const day = r.day || titleDay(r.title, saved);
  const written = day ? new Date(Math.min(Date.parse(`${day}T12:00:00`), Date.now())) : saved;
  return { ref: await fileRef(name, f.raw), written_at: written.toISOString(), title: r.title, text: r.text,
    day: day || localDay(saved), day_basis: day ? "확실" : "추정", day_check: false, parts: 1, imported: false,
    too_long: r.text.length > MAX_TEXT, pick: r.day || undefined, modified: f.modified,
    skip: !r.text ? "글이 없어 건너뜀" : r.text.length > MAX_TEXT ? LONG : undefined };
}

export default function ImportPage() {
  const [kind, setKind] = useState<Kind>("files");
  const [phase, setPhase] = useState<Phase>("pick");
  const [err, setErr] = useState("");
  const [pv, setPv] = useState<(Omit<ImportPreview, "posts"> & { posts: Post[] }) | null>(null);
  const [others, setOthers] = useState(0);   // 글 파일이 아니라 뺀 수
  const [mode, setMode] = useState<"all" | "recent">("all");
  const [n, setN] = useState(10);
  const [queue, setQueue] = useState<Post[]>([]);
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

  const show = (p: ImportPreview, posts: Post[]) => {
    setPv({ ...p, posts });
    setN(Math.max(1, Math.min(10, posts.filter((x) => !x.skip).length)));
    setPhase("preview");
  };
  const pickInstagram = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";
    if (!f) return;
    setErr(""); setPhase("reading"); setDone([]); setOthers(0);
    try {
      const posts = await readPosts(f);
      const parts = await Promise.all(chunks(posts).map(previewInstagram));
      const all = parts.flatMap((x) => x.posts).sort((a, b) => b.written_at.localeCompare(a.written_at));
      if (!all.length) throw new Error("글이 있는 게시물을 찾지 못했어요(사진만 있는 게시물은 가져오지 않아요).");
      show(parts[0], all.map((p) => ({ ...p, skip: p.imported ? "이미 가져옴" : p.too_long ? LONG : undefined })));
    } catch (x) {
      setErr(x instanceof SyntaxError ? "게시물 파일을 읽지 못했어요. 인스타그램에서 받은 파일 그대로 골라 주세요." : why(x, "파일을 읽지 못했어요. 인스타그램에서 받은 파일 그대로 골라 주세요."));
      setPhase("pick");
    }
  };
  const pickFiles = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const picked = [...(e.target.files ?? [])];
    e.target.value = "";
    if (!picked.length) return;
    setErr(""); setPhase("reading"); setDone([]);
    try {
      const [{ files, skipped }, est] = await Promise.all([readTextFiles(picked), previewInstagram([])]);
      const posts = await Promise.all(files.map(filePost));
      setOthers(skipped);
      show(est, posts.sort((a, b) => b.day.localeCompare(a.day) || b.modified! - a.modified!));   // 최근 것부터(같은 날이면 나중에 저장한 것부터)
    } catch (x) {
      setErr(why(x, "파일을 읽지 못했어요. 다시 골라 주세요."));
      setPhase("pick");
    }
  };

  const fresh = pv ? pv.posts.filter((p) => !p.skip) : [];
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
  const one = async (p: Post): Promise<EntryResult> => {
    try {
      return await writeDiary({ title: p.title, text: p.text, written_at: p.written_at, day: p.pick, source: "지난 글 묶음", source_ref: p.ref },
        { onProgress: setProg });
    } catch (e) {
      const x = e as StreamError;
      if (x.entry_id && x.resumable) return cont(x.entry_id);
      throw x;
    }
  };

  const run = async (q: Post[], from: number) => {
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
            setDone((d) => [...d, { post: q[i], id: x.entry_id, dup: false, failed: why(x) }]);
            continue;
          }
          setErr(why(x, `가져오다 멈췄어요. '남은 ${q.length - i}편 이어서 가져오기'를 눌러 주세요.`)); setPhase("paused"); return;   // 서버 · 연결 · 동의 문제: 멈추고 이어 하기
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
  const step = phase === "pick" || phase === "reading" ? 0 : phase === "preview" ? 1 : 2;
  const guess = kind === "files" ? "(저장한 날)" : "(게시한 날)";

  return (
    <main className="imp">
      <h1>지난 일기 가져오기</h1>
      <p className="sub">써 둔 일기를 한꺼번에 가져와, 지난 기록으로 우주에 띄워요.</p>
      <ol className="imp-steps" aria-label="단계">
        {STEPS.map((s, i) => (
          <li key={s} aria-current={i === step ? "step" : undefined} className={i < step || phase === "done" ? "done" : ""}>{s}</li>
        ))}
      </ol>

      {(phase === "pick" || phase === "reading") && (
        <section className="card stack" aria-label="파일 고르기">
          <div className="seg" role="group" aria-label="가져올 곳">
            <button type="button" aria-pressed={kind === "files"} onClick={() => { setKind("files"); setErr(""); }}>글 파일 여러 개</button>
            <button type="button" aria-pressed={kind === "instagram"} onClick={() => { setKind("instagram"); setErr(""); }}>인스타그램 ZIP</button>
          </div>
          {kind === "files" ? (
            <>
              <p style={{ marginBottom: 0 }}>일기 한 편이 파일 하나예요. 메모장(.txt)이나 마크다운(.md) 파일을 한꺼번에 골라요. 여러 파일을 묶은 ZIP도 돼요.</p>
              <div>
                <label htmlFor="txt">글 파일(.txt · .md) 여러 개 또는 ZIP</label>
                <input id="txt" type="file" multiple accept=".txt,.md,.zip,text/plain,text/markdown,application/zip" disabled={phase === "reading"} onChange={pickFiles} />
              </div>
              <p className="sub" style={{ marginBottom: 0 }}>
                파일 고르는 창에서 Ctrl+A(맥은 ⌘+A)를 누르면 모두 골라져요. 짧은 첫 줄은 제목, 파일 이름 속 날짜(예: 2026-10-03)는 글이 다루는 날이 돼요.
              </p>
            </>
          ) : (
            <>
              <ol className="sub" style={{ margin: 0, paddingLeft: 20 }}>
                <li>인스타그램 앱 → 설정 → 계정 센터 → 내 정보 다운로드</li>
                <li>형식은 <b>JSON</b>을 고르고(사진 화질은 낮음이면 충분해요), 받은 ZIP 파일을 여기서 골라요.</li>
              </ol>
              <div>
                <label htmlFor="zip">ZIP 파일(또는 posts_1.json)</label>
                <input id="zip" type="file" accept=".zip,.json,application/zip,application/json" disabled={phase === "reading"} onChange={pickInstagram} />
              </div>
              <p className="sub" style={{ marginBottom: 0 }}>
                사진 · 영상은 읽지 않고 글만 가져와요. · <a href="/samples/instagram-virtual-dodam.zip" download>예시 ZIP 내려받기</a>
              </p>
            </>
          )}
          {phase === "reading" && <p className="sub" role="status" style={{ marginBottom: 0 }}>{kind === "files" ? "파일을 읽는 중…" : "게시물을 읽는 중…"}</p>}
          <p className="sub" style={{ marginBottom: 0 }}>파일은 이 기기에서 읽고 글만 보내요. 글을 정리할 때 다른 사람 이름은 가명으로 바꿔 보내요.</p>
          {err && <p className="err" role="alert" style={{ marginBottom: 0 }}>{err}</p>}
        </section>
      )}

      {phase === "preview" && pv && (
        <section className="card stack" aria-label="가져올 글">
          <h2 style={{ marginBottom: 0 }}>글 {pv.posts.length}편을 찾았어요</h2>
          <p className="sub" style={{ marginBottom: 0 }}>
            {kind === "instagram" ? <>
              {pv.posts.some((p) => p.parts > 1) && `이어 쓴 게시물은 한 편으로 묶었어요. `}
              {pv.posts.length - fresh.length > 0 && `이미 가져왔거나 너무 긴 글 ${pv.posts.length - fresh.length}편은 건너뛰어요.`}
            </> : <>
              {pv.posts.length - fresh.length > 0 && `건너뛰는 글 ${pv.posts.length - fresh.length}편은 목록에 까닭을 적었어요. `}
              이미 가져온 파일은 가져오면서 알아보고 다시 정리하지 않아요.
              {others > 0 && ` 글 파일이 아닌 ${others}개는 뺐어요.`}
            </>}
          </p>
          <ol className="imp-list" aria-label="글 목록(최근 것부터)">
            {pv.posts.map((p) => (
              <li key={p.ref} className={p.skip ? "skip" : undefined}>
                <span className="sub">{p.day}{p.day_basis === "추정" ? guess : ""}</span> {label(p) || "—"}
                {p.parts > 1 && <span className="sub"> · 게시물 {p.parts}개를 한 편으로</span>}
                {p.skip && <span className="sub"> · {p.skip}</span>}
              </li>
            ))}
          </ol>
          {fresh.length === 0 ? <p className="toast" role="status" style={{ marginBottom: 0 }}>새로 가져올 글이 없어요. 모두 이미 가져왔거나 건너뛰는 글이에요.</p> : (
            <>
              <fieldset className="row" style={{ gap: "4px 16px" }}>
                <legend>몇 편을 가져올까요?</legend>
                <label className="row" style={{ marginBottom: 0 }}>
                  <input type="radio" name="how" checked={mode === "all"} onChange={() => setMode("all")} style={{ width: "auto" }} />
                  전부 {limit}편{pv.max_posts && fresh.length > pv.max_posts ? ` (한 번에 최근 ${pv.max_posts}편까지)` : ""}
                </label>
                <label className="row" style={{ marginBottom: 0 }}>
                  <input type="radio" name="how" checked={mode === "recent"} onChange={() => setMode("recent")} style={{ width: "auto" }} />
                  최근
                  <input type="number" aria-label="최근 몇 편" min={1} max={limit} value={n} style={{ width: 80 }}
                    onChange={(e) => { setMode("recent"); setN(Math.max(1, Math.min(limit, Number(e.target.value) || 1))); }} />
                  편
                </label>
              </fieldset>
              <p style={{ marginBottom: 0 }} aria-live="polite">
                <b>{count}편</b> · 예상 시간 약 {minutes(count * pv.est_seconds_per_post)} · 예상 비용 약 ${(count * pv.est_usd_per_post).toFixed(2)}
              </p>
              <p className="sub" style={{ marginBottom: 0 }}>
                편당 약 {Math.round(pv.est_seconds_per_post / 60)}분 · ${pv.est_usd_per_post.toFixed(2)}(어림값). 고른 글 중 오래된 것부터 한 편씩 정리해요.
                정리하는 동안 이 화면을 켜 두세요. 언제든 멈추고 이어 할 수 있어요.
              </p>
            </>
          )}
          <div className="row">
            {fresh.length > 0 && <button className="primary" onClick={start} disabled={count < 1}>가져오기 시작</button>}
            <button onClick={() => { setPv(null); setPhase("pick"); }}>다른 파일 고르기</button>
          </div>
        </section>
      )}

      {(phase === "running" || phase === "paused" || phase === "done") && (
        <section className="card stack" aria-label="가져오기 진행">
          <div className="stack" aria-live="polite">
            <h2 style={{ marginBottom: 0 }}>{phase === "running" ? "가져오는 중" : phase === "paused" ? "멈췄어요" : "다 가져왔어요"}</h2>
            <progress value={done.length} max={queue.length} style={{ width: "100%" }} aria-label="가져온 글 수" />
            <p style={{ marginBottom: 0 }}>{done.length} / {queue.length}편 · 새로 정리 {newly}편{dups ? ` · 이미 있던 글 ${dups}편` : ""}{fails ? ` · 가져오지 못한 글 ${fails}편` : ""}</p>
            {phase === "running" && queue[at] && (
              <p className="sub" style={{ marginBottom: 0 }}>지금: {queue[at].day} {label(queue[at])}{prog ? ` · ${prog.label}` : ""}</p>
            )}
            {err && <p className="err" role="alert" style={{ marginBottom: 0 }}>{err}</p>}
          </div>
          {phase === "running" && (
            <button onClick={() => { stop.current = true; setStopping(true); }} disabled={stopping}>
              {stopping ? "지금 글까지 정리하고 멈춰요…" : "멈추기"}
            </button>
          )}
          {phase === "paused" && <button className="primary" onClick={() => run(queue, at)}>남은 {queue.length - at}편 이어서 가져오기</button>}
          {phase !== "running" && (
            <p style={{ marginBottom: 0 }}><Link href="/universe">우주에서 보기</Link> · <Link href="/history">지난 기록 보기</Link></p>
          )}
          {phase === "done" && <button onClick={() => { setPv(null); setPhase("pick"); }}>다른 파일 고르기</button>}
          {done.length > 0 && (
            <ol className="imp-list" aria-label="가져온 글">
              {done.map((d) => (
                <li key={d.post.ref}>
                  {d.id ? <Link href={`/history?id=${encodeURIComponent(d.id)}`}>{d.post.day} {label(d.post)}</Link> : <>{d.post.day} {label(d.post)}</>}
                  {d.dup && <span className="sub"> · 이미 있던 글</span>}
                  {d.failed && <span className="err"> · {d.failed}</span>}
                </li>
              ))}
            </ol>
          )}
        </section>
      )}
    </main>
  );
}
