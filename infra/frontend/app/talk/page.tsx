"use client";
// 이야기하기(WS19, 주 화면): 별지기가 먼저 묻고 한 턴씩 이어 간다. 대화는 서버에 암호화해 두어 다른 기기에서도 이어 한다.
// '지금까지 정리'(접이식) → '대화 마치고 정리하기' → 요약 확인(ConfirmCard) → 저장 뒤 한마디 · 안부는 이 화면의 별지기 말풍선.
// /?from=<기록 id>(옛 주소 /talk?from=) 는 그 기록을 첫 맥락으로 새 대화를 연다('이 이야기 이어 하기').
// 말 보내기는 send(text) 하나 — 마이크(WS21)도 받아쓴 글을 여기로 보낸다.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ConfirmCard from "@/components/ConfirmCard";
import { useKeeperName } from "@/components/Keeper";
import MicButton, { useReadAloud } from "@/components/MicButton";
import {
  deleteTalk, finishTalk, getDiary, getTalk, listTalks, sayTalk, startTalk,
  type Conversation, type EntryResult, type StreamError,
} from "@/lib/api";

const PRE = { whiteSpace: "pre-line" } as const;

export default function TalkPage() {
  const keeper = useKeeperName();
  const [c, setC] = useState<Conversation | null>(null);
  const [others, setOthers] = useState<Conversation[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState("");             // 진행 문구(비면 쉬는 중)
  const [err, setErr] = useState("");
  const [steps, setSteps] = useState<string[]>([]);   // 정리하기 진행 단계
  const [draft, setDraft] = useState<EntryResult | null>(null);   // 확인을 기다리는 정리
  const [saved, setSaved] = useState<EntryResult | null>(null);   // 저장한 결과(한마디)
  const endRef = useRef<HTMLDivElement>(null);
  const voice = useReadAloud();   // 별지기 답 읽어 주기(WS21, 기본 꺼짐)
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [c?.turns.length, busy, saved, draft]);

  const open = async (x: Conversation) => {
    setC(x); setSaved(null); setDraft(null); setErr("");
    if (x.entry_id) {
      const r = await getDiary(x.entry_id).catch(() => null);
      if (r?.status === "confirm") setDraft(r);
    }
  };
  const fresh = async (from?: string) => {
    setBusy("별지기를 부르는 중…");
    try { await open(await startTalk(from)); } catch (e) { setErr((e as Error).message || "대화를 열지 못했어요."); } finally { setBusy(""); }
  };
  // 처음: ?from 이 있으면 그 기록에서 새 대화, 아니면 이어 할 대화(가장 최근) 또는 새 대화
  useEffect(() => {
    const from = new URLSearchParams(window.location.search).get("from");
    if (from) { fresh(from); return; }
    listTalks().then(({ conversations: [first, ...rest] }) => {
      setOthers(rest);
      return first ? open(first) : fresh();
    }, (e) => setErr(e?.message || "대화를 불러오지 못했어요."));
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (said: string, via: "text" | "voice" = "text") => {
    if (!c || !said.trim() || busy) return;
    setErr(""); setBusy("별지기가 듣는 중…");
    try {
      const next = await sayTalk(c.id, said.trim(), (p) => setBusy(p.label + "…"), via);
      setC(next);
      setText("");
      voice.say(next.turns[next.turns.length - 1]?.text);
    } catch (e) {
      const x = e as StreamError;
      setErr(x.message || "보내지 못했어요. 다시 보내 주세요.");
      if (via === "voice") setText(said);   // 받아쓴 말은 칸에 남겨 다시 보내게
      if (x.code === "disconnected") {   // 서버는 끝까지 처리했을 수 있다: 다시 불러와 붙었으면 칸을 비운다
        const now = await getTalk(c.id).catch(() => null);
        if (now && now.turn_count > c.turn_count) { setC(now); setText(""); setErr(""); }
      }
    } finally { setBusy(""); }
  };
  const finish = async () => {
    if (!c) return;
    setErr(""); setSteps([]); setBusy("정리하는 중…");
    try {
      const r = await finishTalk(c.id, { onProgress: (p) => setSteps((s) => (s.includes(p.label) ? s : [...s, p.label])) });
      if (r.status === "confirm") setDraft(r); else setSaved(r);
    } catch (e) { setErr((e as StreamError).message || "정리하지 못했어요. 다시 눌러 주세요."); }
    finally { setBusy(""); setSteps([]); }
  };
  const remove = async () => {
    if (!c || !window.confirm("이 대화를 지울까요? 확인 전 정리도 같이 지워져요.")) return;
    await deleteTalk(c.id).catch(() => {});
    setC(null);
    fresh();
  };

  const bubble = (t: Conversation["turns"][number], i: number) => t.role === "user" ? (
    <div key={i} className="bubble me" style={{ margin: "0 0 12px auto" }}><p style={{ margin: 0, ...PRE }}>{t.text}</p></div>
  ) : (
    <div key={i} className="voice" style={{ marginBottom: 12 }}>
      <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
      <div style={{ minWidth: 0, maxWidth: "85%" }}>
        <div className="bubble"><p style={{ margin: 0, ...PRE }}>{t.text}</p></div>
        {t.check_in && <p className="sub" data-testid="check-in" style={{ margin: "6px 0 0", ...PRE }}>{t.check_in}</p>}
      </div>
    </div>
  );
  const m = saved?.message;
  // 받아쓴 말은 바로 대화 턴으로. 한 번에 보낼 수 있는 길이를 넘으면 칸에 두고 줄여 달라고 한다.
  const heard = (t: string) => {
    if (t.length <= 8000) return send(t, "voice");
    setText(t); setErr("받아쓴 말이 8000자를 넘어요. 조금 줄여서 보내 주세요.");
  };

  return (
    <main onClickCapture={voice.on ? voice.unlock : undefined}>
      <div className="row" style={{ justifyContent: "space-between", marginBottom: 8 }}>
        <h1 style={{ margin: 0 }}>이야기하기</h1>
        <div className="row">
          <button className="small" aria-pressed={voice.on} onClick={voice.toggle}>읽어 주기 {voice.on ? "켜짐" : "꺼짐"}</button>
          <button className="small" onClick={() => { if (c?.turn_count && !saved) setOthers([c, ...others]); fresh(); }}
            disabled={!!busy}>새 대화</button>
          {c && !saved && <button className="small danger" onClick={remove} disabled={!!busy}>이 대화 지우기</button>}
        </div>
      </div>
      <p className="sub">별지기와 이야기하면 내 말로 일기를 정리해 드려요. 글로 쓰고 싶으면 <Link href="/write">직접 쓰기</Link>.</p>

      {c?.summary && !saved && (
        <details className="card" style={{ padding: "10px 14px" }}>
          <summary>지금까지 정리</summary>
          <p className="sub" style={{ margin: "8px 0 0" }}>내가 한 말만으로 정리했어요. 대화를 마치면 이걸 바탕으로 일기를 만들어요.</p>
          <p style={{ margin: "6px 0 0", ...PRE }}>{c.summary}</p>
        </details>
      )}

      <section aria-label="대화" aria-live="polite" style={{ margin: "12px 0" }}>
        {c?.turns.map(bubble)}
        {m && (
          <div className="voice" style={{ marginBottom: 12 }} data-testid="saved-message">
            <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
            <div style={{ minWidth: 0 }}>
              <div className="bubble"><p style={{ margin: 0, ...PRE }}>{m.text}</p></div>
              {m.check_in && <p className="sub" style={{ margin: "6px 0 0", ...PRE }}>{m.check_in}</p>}
            </div>
          </div>
        )}
        {busy && <p className="sub" role="status">{busy}</p>}
        {steps.length > 0 && <ol className="steps">{steps.map((s, i) => <li key={s} className={i < steps.length - 1 ? "done" : "now"}>{s}</li>)}</ol>}
        {err && <p className="err" role="alert">{err}</p>}
        <div ref={endRef} />
      </section>

      {saved ? (
        <section className="card stack" aria-label="저장했어요">
          <p style={{ margin: 0 }}>우주에 저장했어요.</p>
          <div className="row">
            <Link className="btn" href="/universe">우주에서 보기</Link>
            <Link className="btn" href={`/history?id=${encodeURIComponent(saved.id)}`}>결과 카드 보기</Link>
            <button onClick={() => fresh()}>새 대화</button>
          </div>
        </section>
      ) : draft ? (
        <ConfirmCard r={draft} onSaved={(r) => { setSaved(r); setDraft(null); voice.say(r.message?.text); }} />
      ) : c && (
        <form className="stack" aria-label="말하기" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <div>
            <label htmlFor="talk-input">별지기에게 답하기</label>
            <textarea id="talk-input" value={text} onChange={(e) => setText(e.target.value)} disabled={!!busy} style={{ minHeight: 88 }}
              placeholder="편하게 적어 주세요. (Ctrl · ⌘ + Enter 로 보내기)" maxLength={8000}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(text); } }} />
          </div>
          <MicButton onText={heard} disabled={!!busy} />
          <div className="row">
            <button type="submit" className="primary" disabled={!!busy || !text.trim()}>보내기</button>
            <button type="button" className={c.wrap ? "primary" : undefined} onClick={finish} disabled={!!busy || !c.turn_count}>
              대화 마치고 정리하기</button>
          </div>
        </form>
      )}

      {others.length > 0 && !saved && (
        <section className="card stack" aria-label="이어 하지 않은 대화" style={{ marginTop: 16 }}>
          <h2>이어 하지 않은 대화 {others.length}개</h2>
          {others.map((o) => (
            <div key={o.id} className="row" style={{ justifyContent: "space-between" }}>
              <span className="sub">{o.updated_at.slice(0, 10)} · {o.turns.find((t) => t.role === "user")?.text.slice(0, 30) ?? "아직 말 없음"}</span>
              <span className="row">
                <button className="small" onClick={() => { if (c) setOthers([c, ...others.filter((x) => x.id !== o.id)]); else setOthers(others.filter((x) => x.id !== o.id)); open(o); }}>이어 하기</button>
                <button className="small danger" onClick={async () => { await deleteTalk(o.id).catch(() => {}); setOthers(others.filter((x) => x.id !== o.id)); }}>지우기</button>
              </span>
            </div>
          ))}
        </section>
      )}
    </main>
  );
}
