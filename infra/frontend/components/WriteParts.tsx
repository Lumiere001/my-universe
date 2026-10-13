"use client";
// 쓰기 화면 조각(WS13): 별지기 말풍선 · 제목 · 날짜 칸 · MD · TXT 불러오기(+ 예시 일기 받기) · 이미 정리한 글 안내.
import Link from "next/link";
import { useState } from "react";
import { getPrompt } from "@/lib/api";
import { useLoad } from "@/lib/use";
import { localToday, WeatherSkip } from "./EntryTools";
import { useKeeperName } from "./Keeper";
import { FeedbackButtons, unquote } from "./ResultCard";

// 쓰기 화면 위 말풍선: 첫 만남 질문 또는 지난번 '다음에 써 볼 질문' + 다짐 안부(GET /diary/prompt, LLM 없음)
export function KeeperPrompt() {
  const name = useKeeperName();
  const [p] = useLoad(getPrompt);
  const [skipped, setSkipped] = useState(false);
  if (!p || (p.kind === "none" && !p.vow)) return null;
  return (
    <section className="voice" aria-label="별지기 말풍선" style={{ margin: "0 0 14px" }}>
      <span className="who" aria-hidden>{name.slice(0, 1)}</span>
      <div className="stack" style={{ flex: 1, minWidth: 0 }}>
        <div className="sub">{name}</div>
        {p.kind !== "none" && (
          <div className="bubble" data-testid="prompt-question">
            {!skipped && <p style={{ margin: 0, whiteSpace: "pre-line" }}>{p.text}</p>}
            {p.kind === "aspiration" && <p style={{ margin: "8px 0 0" }}><Link href="/aspiration">되고 싶은 모습 적어 보기</Link></p>}
            {p.kind === "weather" && <WeatherSkip onDone={() => setSkipped(true)} />}
          </div>
        )}
        {p.vow && (
          <div className="bubble" data-testid="prompt-vow">
            <p style={{ margin: "0 0 8px" }}>지난번에 적은 다짐, “{unquote(p.vow.text)}” 요즘은 어때요? 떠오르면 가볍게 적어 줘요.</p>
            <FeedbackButtons label="다짐 안부" target="vow" targetId={p.vow.thought_id} values={["지켰어요", "그만둘래요"]} />
          </div>
        )}
      </div>
    </section>
  );
}

// 제목 · 글이 다루는 날. 날을 비우면 오늘(제목 · 짧은 첫 줄에 날짜가 있으면 그날, 서버 G2)
export function EntryMeta({ title, day, onTitle, onDay, disabled }:
  { title: string; day: string; onTitle: (v: string) => void; onDay: (v: string) => void; disabled?: boolean }) {
  return (
    <div className="row" style={{ alignItems: "flex-end" }}>
      <div style={{ flex: "2 1 220px" }}>
        <label htmlFor="title">제목 (비워도 돼요)</label>
        <input id="title" value={title} maxLength={120} disabled={disabled} onChange={(e) => onTitle(e.target.value)} placeholder="예: 10/3 토요일 일기" />
      </div>
      <div style={{ flex: "1 1 150px" }}>
        <label htmlFor="day">글이 다루는 날 (비우면 오늘)</label>
        <input id="day" type="date" value={day} max={localToday()} disabled={disabled} onChange={(e) => onDay(e.target.value)} />
      </div>
    </div>
  );
}

/* ---------- MD · TXT 파일 → 쓰기 칸 ---------- */
const MAX_TEXT = 8000;         // 백엔드 MAX_TEXT_CHARS 기본값(넘으면 서버도 422)
const MAX_BYTES = 1_000_000;   // 입력 검사(상한 아님): 일기 한 편 파일
export type Loaded = { title: string; text: string; day: string; ref: string };

// 짧은 첫 줄(40자 이하) · 제목 줄(#)은 제목으로, 나머지는 본문(마크다운 제목 표시 # 는 뗌). 파일 이름 속 YYYY-MM-DD → 글이 다루는 날.
export function readDiaryFile(name: string, raw: string): Omit<Loaded, "ref"> {
  const lines = raw.replace(/\r\n?/g, "\n").trim().split("\n");
  const head = lines[0].trim();
  const titled = lines.length > 1 && (head.startsWith("#") || head.length <= 40);
  const title = titled ? head.replace(/^#+\s*/, "").slice(0, 120) : "";
  const text = (titled ? lines.slice(1) : lines).map((l) => l.replace(/^#+\s+/, "")).join("\n").trim();
  const m = /(\d{4})-(\d{2})-(\d{2})/.exec(name);
  const ok = m && new Date(Date.UTC(+m[1], +m[2] - 1, +m[3])).toISOString().slice(0, 10) === m[0];   // 2026-02-30 같은 날은 버림
  return { title, text, day: ok ? m![0] : "" };
}

export function FilePick({ onLoad, disabled }: { onLoad: (f: Loaded) => void; disabled?: boolean }) {
  const [err, setErr] = useState("");
  const [name, setName] = useState("");
  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";   // 같은 파일을 다시 골라도 다시 읽게
    if (!f) return;
    setErr(""); setName("");
    if (!/\.(md|txt)$/i.test(f.name)) return setErr("MD · TXT 파일만 불러올 수 있어요.");
    if (f.size > MAX_BYTES) return setErr("파일이 너무 커요. 일기 한 편씩 올려 주세요.");
    const r = readDiaryFile(f.name, await f.text());
    if (!r.text) return setErr("파일에 글이 없어요.");
    if (r.text.length > MAX_TEXT) return setErr(`글이 길어요(${MAX_TEXT.toLocaleString()}자까지). 나눠서 올려 주세요.`);
    setName(f.name);
    onLoad({ ...r, ref: `파일:${f.name}:${f.size}:${f.lastModified}` });   // 같은 파일 다시 올리기 막기(고치면 지움)
  };
  return (
    <div className="stack">
      <div>
        <label htmlFor="file">MD · TXT 파일에서 불러오기</label>
        <input id="file" type="file" accept=".md,.txt,text/markdown,text/plain" disabled={disabled} onChange={pick} />
      </div>
      <p className="sub" style={{ margin: 0 }}>
        불러온 글은 위 칸에 채워져요. 고친 뒤 띄워도 돼요. · <a href="/samples/haneul-2026-10-03.txt" download="하늘-2026-10-03-일기.txt">예시 일기 받기</a>
      </p>
      {name && <p className="toast" role="status" style={{ margin: 0 }}>‘{name}’을 불러왔어요.</p>}
      {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
    </div>
  );
}

// 같은 글을 다시 보냈을 때(서버 duplicate: true): 다시 정리하지 않고 그 기록의 결과를 보여 준다
export function DuplicateNote({ id }: { id: string }) {
  return (
    <section className="card" role="status" aria-label="이미 정리한 글">
      <p style={{ margin: 0 }}>이미 정리한 글이에요. 다시 정리하지 않고, 그때 정리한 결과를 보여 드려요.</p>
      <p style={{ margin: "6px 0 0" }}><Link href={`/history?id=${encodeURIComponent(id)}`}>지난 기록에서 보기</Link></p>
    </section>
  );
}
