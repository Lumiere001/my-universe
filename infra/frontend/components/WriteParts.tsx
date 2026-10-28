"use client";
// 쓰기 화면 조각(WS13): 별지기 말풍선 · 제목 · 날짜 칸 · 글 파일(.txt · .md) 불러오기(+ 예시 일기 내려받기) · 이미 정리한 글 안내.
// 일기장 모양(2026-10-28): 맨 위 날짜 줄(= 글이 다루는 날 칸) · 접힌 별지기 한 줄 · 도구 줄 아이콘 · 쓰는 방법 풍선 · 마크다운 미리보기.
import Link from "next/link";
import { useId, useState } from "react";
import { getPrompt, type Weather } from "@/lib/api";
import Icon from "./Icon";
import { useLoad } from "@/lib/use";
import { localToday, WeatherSkip } from "./EntryTools";
import { useKeeperName } from "./Keeper";
import { VOICE_HELP } from "./MicButton";
import { PHOTO_NOTE } from "./PhotoInput";
import { FeedbackButtons, unquote } from "./ResultCard";

// 쓰기 화면 위 말풍선: 첫 만남 질문 또는 지난번 '다음에 써 볼 질문' + 다짐 안부(GET /diary/prompt, LLM 없음).
// 접힌 한 줄(별지기 · 첫 문장 · 〔다짐 안부〕)로 두고 누르면 펼친다(한 화면 규칙).
export function KeeperPrompt() {
  const name = useKeeperName();
  const [p] = useLoad(getPrompt);
  const [skipped, setSkipped] = useState(false);
  if (!p || (p.kind === "none" && !p.vow)) return null;
  const vow = p.vow && `지난번에 적은 다짐, “${unquote(p.vow.text)}” 요즘은 어때요? 떠오르면 가볍게 적어 줘요.`;
  const peek = p.kind !== "none" && !skipped ? p.text : vow ?? "";
  return (
    <section className="keeper-line" aria-label="별지기 말풍선">
      <details>
        <summary className="voice">
          <span className="who" aria-hidden>{name.slice(0, 1)}</span>
          <span className="name">{name}</span>
          <span className="peek">{peek}</span>
          {p.vow && <span className="badge g">다짐 안부</span>}
        </summary>
        <div className="stack keeper-body">
          {p.kind !== "none" && (
            <div className="bubble" data-testid="prompt-question">
              {!skipped && <p style={{ margin: 0, whiteSpace: "pre-line" }}>{p.text}</p>}
              {p.kind === "aspiration" && <p style={{ margin: "8px 0 0" }}><Link href="/aspiration">되고 싶은 모습 적어 보기</Link></p>}
              {p.kind === "weather" && <WeatherSkip onDone={() => setSkipped(true)} />}
            </div>
          )}
          {p.vow && (
            <div className="bubble" data-testid="prompt-vow">
              <p style={{ margin: "0 0 8px" }}>{vow}</p>
              <FeedbackButtons label="다짐 안부" target="vow" targetId={p.vow.thought_id} values={["지켰어요", "그만둘래요"]} />
            </div>
          )}
        </div>
      </details>
    </section>
  );
}

// 일기장 머리: 날짜 줄(= 글이 다루는 날, 누르면 날짜 고르기) + 보기 바꾸기(children) · 큰 제목 칸 · 마음 날씨 한 줄.
// 날을 비우면 오늘(제목 · 짧은 첫 줄에 날짜가 있으면 그날, 서버 G2). 마음 날씨는 골라도 되고 건너뛰어도 된다.
const longDay = new Intl.DateTimeFormat("ko-KR", { month: "long", day: "numeric", weekday: "long" });
export function EntryMeta({ title, day, weather, weathers, onTitle, onDay, onWeather, disabled, children }: {
  title: string; day: string; weather: Weather | null; weathers: { name: string; words: string[] }[];
  onTitle: (v: string) => void; onDay: (v: string) => void; onWeather: (w: Weather | null) => void; disabled?: boolean;
  children?: React.ReactNode;
}) {
  const d = day || localToday();
  return (
    <>
      <div className="diary-head">
        <span className="diary-date" title="글이 다루는 날 (비우면 오늘)">
          <Icon name="calendar" size={16} />
          <span>{longDay.format(new Date(+d.slice(0, 4), +d.slice(5, 7) - 1, +d.slice(8, 10)))}</span>
          <input id="day" type="date" aria-label="글이 다루는 날" value={day} max={localToday()} disabled={disabled}
            onChange={(e) => onDay(e.target.value)}
            onClick={(e) => { try { e.currentTarget.showPicker?.(); } catch { /* 고르기 창을 못 열면 칸에 바로 입력 */ } }} />
        </span>
        {day && (
          <button type="button" className="tbtn" disabled={disabled} onClick={() => onDay("")}
            aria-label="오늘로 되돌리기" title="오늘로 되돌리기"><Icon name="close" size={14} /></button>
        )}
        {children}
      </div>
      <input id="title" className="inline-title" aria-label="제목 (비워도 돼요)" value={title} maxLength={120} disabled={disabled}
        onChange={(e) => onTitle(e.target.value)} placeholder="제목 (비워도 돼요)" />
      <div className="prop weather-prop" title="마음 날씨 (고르지 않아도 돼요)">
        <span className="k" id="weather-k"><Icon name="weather" size={16} />마음 날씨</span>
        <div className="row chips" role="group" aria-labelledby="weather-k">
          {weathers.map((w) => (
            <button type="button" key={w.name} className="small" aria-pressed={weather === w.name} disabled={disabled} title={w.words.join(" · ")}
              onClick={() => onWeather(weather === w.name ? null : (w.name as Weather))}>{w.name}</button>
          ))}
        </div>
      </div>
    </>
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

const FILE_HELP = "불러온 글은 글 칸에 채워져요. 고친 뒤 띄워도 돼요.";
export function FilePick({ onLoad, disabled }: { onLoad: (f: Loaded) => void; disabled?: boolean }) {
  const helpId = useId();
  const [err, setErr] = useState("");
  const [name, setName] = useState("");
  const pick = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";   // 같은 파일을 다시 골라도 다시 읽게
    if (!f) return;
    setErr(""); setName("");
    if (!/\.(md|txt)$/i.test(f.name)) return setErr(".txt · .md 파일만 불러올 수 있어요.");
    if (f.size > MAX_BYTES) return setErr("파일이 너무 커요. 일기 한 편씩 올려 주세요.");
    const r = readDiaryFile(f.name, await f.text());
    if (!r.text) return setErr("파일에 글이 없어요.");
    if (r.text.length > MAX_TEXT) return setErr(`글이 너무 길어요(${MAX_TEXT.toLocaleString()}자까지). 나눠서 올려 주세요.`);
    setName(f.name);
    onLoad({ ...r, ref: `파일:${f.name}:${f.size}:${f.lastModified}` });   // 같은 파일 다시 올리기 막기(고치면 지움)
  };
  // 조각으로 돌려줘서 도구 줄에 아이콘으로 서고, 알림은 줄 아래로(.tool-msg)
  return (
    <>
      <label className="tbtn" title={`글 파일(.txt · .md)에서 불러오기\n${FILE_HELP}`}>
        <Icon name="fileText" />
        <input id="file" type="file" className="sr" accept=".md,.txt,text/markdown,text/plain" disabled={disabled} onChange={pick}
          aria-label="글 파일(.txt · .md)에서 불러오기" aria-describedby={helpId} />
      </label>
      <span id={helpId} className="sr">{FILE_HELP}</span>
      {name && <p className="tool-msg toast" role="status">‘{name}’을 불러왔어요.</p>}
      {err && <p className="tool-msg err" role="alert">{err}</p>}
    </>
  );
}

// 쓰는 방법(도구 줄의 ? 단추): 마크다운 · 도구마다의 안내를 한 풍선에 모아 화면에는 늘 보이지 않게(브라우저 기본 popover)
export function WriteHelp() {
  return (
    <>
      <button type="button" className="tbtn" popoverTarget="write-help" aria-label="쓰는 방법" title="쓰는 방법"><Icon name="help" /></button>
      <div id="write-help" popover="auto" className="pop">
        <h2>쓰는 방법</h2>
        <p><b>마크다운</b> # 제목 · ## 작은 제목 · **굵게** · *기울임* · - 목록 · 1. 번호 목록 · &gt; 인용 · --- 나눔 선. ‘미리보기’로 꾸민 모습을 볼 수 있어요. 별지기에게는 쓴 글 그대로 가요.</p>
        <p><b>말로 쓰기</b> {VOICE_HELP}</p>
        <p><b>글 파일</b> {FILE_HELP} · <a href="/samples/haneul-2026-10-03.txt" download="하늘-2026-10-03-일기.txt">예시 일기 내려받기</a></p>
        <p><b>사진</b> {PHOTO_NOTE}</p>
      </div>
    </>
  );
}

// 미리보기용 작은 마크다운: # · ## · ### 제목, **굵게**, *기울임*, - · 1. 목록, > 인용, --- 나눔 선, 줄바꿈.
// HTML 문자열을 만들지 않고 React 요소로 바로 그려서 글 속 <태그>는 글자 그대로 보인다(React 가 글자를 이스케이프, innerHTML 안 씀).
type Block = { t: "p" | "q" | "ul" | "ol"; lines: string[] } | { t: "h"; n: number; s: string } | { t: "hr" };
function blocks(text: string): Block[] {
  const out: Block[] = [];
  let gap = true;   // 빈 줄 뒤에는 새 묶음
  const add = (t: "p" | "q" | "ul" | "ol", s: string) => {
    const last = out[out.length - 1];
    if (!gap && last && "lines" in last && last.t === t) last.lines.push(s); else out.push({ t, lines: [s] });
    gap = false;
  };
  for (const line of text.replace(/\r\n?/g, "\n").split("\n")) {
    let m: RegExpExecArray | null;
    if (!line.trim()) gap = true;
    else if ((m = /^(#{1,3})\s+(.+)$/.exec(line))) { out.push({ t: "h", n: m[1].length, s: m[2] }); gap = true; }
    else if (/^\s*([-*_])(\s*\1){2,}\s*$/.test(line)) { out.push({ t: "hr" }); gap = true; }
    else if ((m = /^\s*>\s?(.*)$/.exec(line))) add("q", m[1]);
    else if ((m = /^\s*[-*+]\s+(.*)$/.exec(line))) add("ul", m[1]);
    else if ((m = /^\s*\d+[.)]\s+(.*)$/.exec(line))) add("ol", m[1]);
    else add("p", line);
  }
  return out;
}
const inline = (s: string, k: string | number) => s.split(/(\*\*[^*\n]+\*\*|\*[^*\s](?:[^*\n]*[^*\s])?\*)/g)
  .map((x, i) => (i % 2 === 0 ? x : x.startsWith("**") ? <strong key={`${k}-${i}`}>{x.slice(2, -2)}</strong> : <em key={`${k}-${i}`}>{x.slice(1, -1)}</em>));
const HEADS = ["h2", "h3", "h4"] as const;   // 화면 제목(h1) 아래로
export function Markdown({ text }: { text: string }) {
  return <>{blocks(text).map((b, i) => {
    if (b.t === "hr") return <hr key={i} />;
    if (b.t === "h") { const H = HEADS[b.n - 1]; return <H key={i}>{inline(b.s, i)}</H>; }
    if (b.t === "ul" || b.t === "ol") { const L = b.t; return <L key={i}>{b.lines.map((l, j) => <li key={j}>{inline(l, j)}</li>)}</L>; }
    const body = b.lines.flatMap((l, j) => (j ? [<br key={`br${j}`} />, ...inline(l, j)] : inline(l, j)));
    return b.t === "q" ? <blockquote key={i}>{body}</blockquote> : <p key={i}>{body}</p>;
  })}</>;
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
