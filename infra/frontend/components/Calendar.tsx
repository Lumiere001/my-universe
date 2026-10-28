"use client";
// 달력(지난 기록 화면 · 사이드바 작은 달력, docs/content/U-04 · C-01). 일요일부터 한 주, 기록이 있는 날에 점, 오늘은 테두리.
// 접근성: role="grid" 표 하나, 날마다 「10월 3일, 기록 2편」 이름의 단추. 탭 키로는 한 날만 들어가고(고른 날 · 오늘 · 1일 순),
// 화살표 ±1일 · ±1주, Home/End 한 주의 처음/끝, PageUp/PageDown 앞/다음 달. 달 넘김은 달 이름을 aria-live 로 읽는다.
import { useEffect, useId, useRef, useState } from "react";
import { localToday } from "@/components/EntryTools";
import { listDiary, why, type EntrySummary } from "@/lib/api";

const pad = (n: number) => String(n).padStart(2, "0");
const iso = (d: Date) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
const at = (day: string) => new Date(+day.slice(0, 4), +day.slice(5, 7) - 1, +day.slice(8, 10));
const addDays = (day: string, n: number) => { const d = at(day); d.setDate(d.getDate() + n); return iso(d); };
const addMonths = (day: string, n: number) => {   // 같은 날(없으면 그 달 끝날)
  const d = at(day), last = new Date(d.getFullYear(), d.getMonth() + n + 1, 0).getDate();
  return iso(new Date(d.getFullYear(), d.getMonth() + n, Math.min(d.getDate(), last)));
};
export const WEEK = "일월화수목금토";
export const monthDay = (day: string) => `${+day.slice(5, 7)}월 ${+day.slice(8, 10)}일`;

// 기록이 놓이는 날: 글이 다루는 날, 없으면 쓴 날(이 기기 날짜)
export const dayOf = (e: EntrySummary) => e.day ?? iso(new Date(e.written_at));
export function countByDay(list: EntrySummary[]): Record<string, number> {
  const n: Record<string, number> = {};
  for (const e of list) n[dayOf(e)] = (n[dayOf(e)] ?? 0) + 1;
  return n;
}

const FAIL = "지난 기록을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.";
// 지난 기록 전부(lib/api.ts listDiary 의 한 번 읽기를 나눠 씀). 기록이 바뀌면('entries' 알림) 다시 읽는다. [목록, 오류 문장]
export function useEntries(): [EntrySummary[] | null, string] {
  const [list, setList] = useState<EntrySummary[] | null>(null);
  const [err, setErr] = useState("");
  useEffect(() => {
    const load = () => listDiary().then((r) => { setList(r); setErr(""); }, (e) => setErr(why(e, FAIL)));
    load();
    window.addEventListener("entries", load);
    return () => window.removeEventListener("entries", load);
  }, []);
  return [list, err];
}

const Chevron = ({ left }: { left?: boolean }) => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
    <path d={left ? "m15 18-6-6 6-6" : "m9 18 6-6-6-6"} />
  </svg>
);

// marks: 날 → 기록 수. selected: 고른 날(바뀌면 그 달로 넘어감). compact: 사이드바용(점 하나)
export default function Calendar({ marks, selected, onPick, compact }: {
  marks: Record<string, number>; selected: string | null; onPick: (day: string) => void; compact?: boolean;
}) {
  const today = localToday();
  const [month, setMonth] = useState((selected ?? today).slice(0, 7));
  const [focus, setFocus] = useState<string | null>(null);
  const moved = useRef(false);   // 화살표로 옮겼을 때만 그 날에 초점
  const grid = useRef<HTMLTableElement>(null);
  const label = useId();
  useEffect(() => { if (selected) setMonth(selected.slice(0, 7)); }, [selected]);
  useEffect(() => {
    if (!moved.current || !focus) return;
    moved.current = false;
    grid.current?.querySelector<HTMLButtonElement>(`[data-day="${focus}"]`)?.focus();
  }, [focus, month]);

  const first = at(month + "-01"), days = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  const inMonth = (d: string | null) => !!d && d.startsWith(month);
  const tab = [focus, selected, today].find(inMonth) ?? month + "-01";
  const cells: (string | null)[] = [...Array(first.getDay()).fill(null), ...Array.from({ length: days }, (_, i) => `${month}-${pad(i + 1)}`)];
  while (cells.length % 7) cells.push(null);
  const weeks = Array.from({ length: cells.length / 7 }, (_, i) => cells.slice(i * 7, i * 7 + 7));

  const go = (d: string) => { moved.current = true; setFocus(d); setMonth(d.slice(0, 7)); };
  const key = (e: React.KeyboardEvent, d: string) => {
    const wd = at(d).getDay();
    const to = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7, Home: -wd, End: 6 - wd }[e.key];
    const next = to !== undefined ? addDays(d, to) : e.key === "PageUp" ? addMonths(d, -1) : e.key === "PageDown" ? addMonths(d, 1) : null;
    if (!next) return;
    e.preventDefault();
    go(next);
  };
  const shift = (n: number, from = month + "-01") => { setFocus(null); setMonth(addMonths(from, n).slice(0, 7)); };

  return (
    <div className={compact ? "cal compact" : "cal"}>
      <div className="cal-head">
        <button type="button" className="icon" aria-label="이전 달" onClick={() => shift(-1)}><Chevron left /></button>
        <b id={label} aria-live="polite">{+month.slice(0, 4)}년 {+month.slice(5)}월</b>
        <button type="button" className="icon" aria-label="다음 달" onClick={() => shift(1)}><Chevron /></button>
        {month !== today.slice(0, 7) && <button type="button" className="small" onClick={() => shift(0, today)}>이번 달</button>}
      </div>
      <table role="grid" ref={grid} aria-labelledby={label}>
        <thead><tr>{[...WEEK].map((w) => <th key={w} scope="col" abbr={w + "요일"}>{w}</th>)}</tr></thead>
        <tbody>
          {weeks.map((w, i) => (
            <tr key={i}>
              {w.map((d, j) => {
                if (!d) return <td key={j} />;
                const n = marks[d] ?? 0;
                return (
                  <td key={j} aria-selected={d === selected || undefined}>
                    <button type="button" className={n ? "has" : undefined} data-day={d} tabIndex={d === tab ? 0 : -1} aria-current={d === today ? "date" : undefined}
                      aria-label={`${monthDay(d)}${n ? `, 기록 ${n}편` : ""}`} onClick={() => onPick(d)} onKeyDown={(e) => key(e, d)}>
                      {+d.slice(8)}
                      {n > 0 && <span className="cal-dots" aria-hidden>{Array.from({ length: compact ? 1 : Math.min(n, 3) }, (_, k) => <i key={k} />)}</span>}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
