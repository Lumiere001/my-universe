"use client";
// 이야기하기(WS19, 주 화면): 별지기가 먼저 묻고 한 턴씩 이어 간다. 대화는 서버에 암호화해 두어 다른 기기에서도 이어 한다.
// '지금까지 정리'(접이식) → '대화 마치고 정리하기' → 요약 확인(ConfirmCard) → 저장 뒤 한마디 · 안부는 이 화면의 별지기 말풍선.
// /?from=<기록 id>(옛 주소 /talk?from=) 는 그 기록을 첫 맥락으로 새 대화를 연다('이 이야기 이어 하기').
// 말 보내기는 send(text) 하나 — 마이크(WS21)도 받아쓴 글을 여기로 보낸다.
// 모양(2026-10-28, 한 화면 규칙): 머리줄(아이콘 셋) · 대화(그 칸 안에서만 넘김) · 아래 붙은 입력 상자(글 칸 + 도구 줄: 마이크 · 클립 | 보내기).
// 드물게 쓰는 '이어 하지 않은 대화' · '이 대화 지우기'는 '더 보기'(브라우저 기본 popover) 안에.
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import ConfirmCard from "@/components/ConfirmCard";
import Icon from "@/components/Icon";
import { useKeeperName } from "@/components/Keeper";
import MicButton, { useReadAloud } from "@/components/MicButton";
import {
  deleteTalk, finishTalk, getDiary, getTalk, listTalks, sayTalk, startTalk, why,
  type Conversation, type EntryResult, type StreamError,
} from "@/lib/api";

const PRE = { whiteSpace: "pre-line" } as const;
// 정리하다 멈춘 서버 코드(app/api/diary.py MESSAGES). 서버 문장은 직접 쓰기의 '이어서 하기'를 가리켜서 이 화면의 문장으로 바꾼다
const STOPPED = new Set(["studio_timeout", "studio_failed", "studio_bad_output", "llm_failed", "internal", "duplicate"]);
const ASK_DELETE = "이 대화를 지울까요? 아직 저장하지 않은 정리도 함께 지워져요.";

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
  const moreRef = useRef<HTMLDivElement>(null);   // '더 보기' 칸
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
    try { await open(await startTalk(from)); } catch (e) { setErr(why(e, "대화를 열지 못했어요. 잠시 뒤 '새 대화 시작'을 다시 눌러 주세요.")); } finally { setBusy(""); }
  };
  // 처음: ?from 이 있으면 그 기록에서 새 대화, 아니면 이어 할 대화(가장 최근) 또는 새 대화
  useEffect(() => {
    const from = new URLSearchParams(window.location.search).get("from");
    if (from) { fresh(from); return; }
    listTalks().then(({ conversations: [first, ...rest] }) => {
      setOthers(rest);
      return first ? open(first) : fresh();
    }, (e) => setErr(why(e, "지난 대화를 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.")));
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
      setErr(why(x, "보내지 못했어요. 다시 보내 주세요."));
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
    } catch (e) {
      const x = e as StreamError;
      setErr(STOPPED.has(x.code) ? "정리하다 멈췄어요. '대화 마치고 정리하기'를 다시 눌러 주세요."
        : why(x, "정리하지 못했어요. '대화 마치고 정리하기'를 다시 눌러 주세요."));
    }
    finally { setBusy(""); setSteps([]); }
  };
  // 대화 지우기: 한 번 묻고, 지우지 못하면 그 대화를 그대로 둔다
  const drop = async (id: string) => {
    if (!window.confirm(ASK_DELETE)) return false;
    setErr("");
    try { await deleteTalk(id); return true; }
    catch (e) { setErr(why(e, "대화를 지우지 못했어요. 잠시 뒤 다시 해 주세요.")); return false; }
  };
  const remove = async () => {
    if (!c || !(await drop(c.id))) return;
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
    setText(t); setErr("받아쓴 말이 8,000자를 넘어요. 칸에 남겨 뒀으니 조금 줄여서 보내 주세요.");
  };

  const said = c?.turns.some((t) => t.role === "user");
  const left = saved ? [] : others;   // 저장한 뒤에는 다른 대화를 보이지 않는다
  const closeMore = () => moreRef.current?.hidePopover?.();   // popover 를 모르는 옛 브라우저는 칸이 그냥 펼쳐져 있다

  return (
    <main className="chat" onClickCapture={voice.on ? voice.unlock : undefined}>
      <div className="chat-head">
        <h1>이야기하기</h1>
        <div className="row tight">
          <button className="tbtn" aria-pressed={voice.on} onClick={voice.toggle}
            aria-label="별지기 말 읽어 주기" title={`별지기 말 읽어 주기 ${voice.on ? "켜짐" : "꺼짐"}`}>
            <Icon name={voice.on ? "speaker" : "mute"} /></button>
          <button className="tbtn" onClick={() => { if (c?.turn_count && !saved) setOthers([c, ...others]); fresh(); }}
            disabled={!!busy} aria-label="새 대화 시작" title="새 대화 시작"><Icon name="newChat" /></button>
          {(left.length > 0 || (c && !saved)) && (
            <button className="tbtn" popoverTarget="talk-more" title="더 보기"
              aria-label={left.length ? `더 보기 (이어 하지 않은 대화 ${left.length}개)` : "더 보기"}>
              <Icon name="more" />{left.length > 0 && <span className="count" aria-hidden>{left.length}</span>}</button>
          )}
        </div>
      </div>
      {!said && <p className="sub chat-lead">별지기와 이야기하면 내가 한 말로 일기를 정리하고, 지난 기록과 이어 드려요. 글로 쓰고 싶으면 <Link href="/write">직접 쓰기</Link>.</p>}

      <div id="talk-more" popover="auto" ref={moreRef} className="pop">
        {left.length > 0 && (
          <section className="stack" aria-label="이어 하지 않은 대화">
            <h2>이어 하지 않은 대화 {left.length}개</h2>
            {left.map((o) => (
              <div key={o.id} className="pop-row">
                <span className="sub">{o.updated_at.slice(0, 10)} · {o.turns.find((t) => t.role === "user")?.text.slice(0, 30) ?? "아직 한 말이 없어요"}</span>
                <span className="row tight">
                  <button className="small" onClick={() => { closeMore(); if (c) setOthers([c, ...others.filter((x) => x.id !== o.id)]); else setOthers(others.filter((x) => x.id !== o.id)); open(o); }}>이어 하기</button>
                  <button className="small danger" onClick={async () => { if (await drop(o.id)) setOthers(others.filter((x) => x.id !== o.id)); }}>지우기</button>
                </span>
              </div>
            ))}
          </section>
        )}
        {c && !saved && <button className="small danger" onClick={() => { closeMore(); remove(); }} disabled={!!busy}><Icon name="trash" size={16} />이 대화 지우기</button>}
      </div>

      {c?.summary && !saved && !draft && (
        <details className="card chat-sum">
          <summary>지금까지 정리</summary>
          <div className="chat-sum-body">
            <p className="sub" style={{ margin: "8px 0 0" }}>내가 한 말만으로 정리했어요. 대화를 마치면 이걸 바탕으로 일기를 만들어요.</p>
            <p style={{ margin: "6px 0 0", ...PRE }}>{c.summary}</p>
          </div>
        </details>
      )}

      <section className="chat-log" aria-label="대화" aria-live="polite">
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
        <section className="card stack" aria-label="저장했어요" style={{ margin: 0 }}>
          <p style={{ margin: 0 }}>우주에 저장했어요. 새 행성이 떴어요.</p>
          <div className="row">
            <Link className="btn" href="/universe">우주에서 보기</Link>
            <Link className="btn" href={`/history?id=${encodeURIComponent(saved.id)}`}>정리한 결과 보기</Link>
            <button onClick={() => fresh()}>새 대화 시작</button>
          </div>
        </section>
      ) : draft ? (
        <ConfirmCard r={draft} onSaved={(r) => { setSaved(r); setDraft(null); voice.say(r.message?.text); }} />
      ) : c && (
        <form className="chat-foot" aria-label="말하기" onSubmit={(e) => { e.preventDefault(); send(text); }}>
          <button type="button" className={c.wrap ? "small primary" : "small"} onClick={finish} disabled={!!busy || !c.turn_count}>
            대화 마치고 정리하기</button>
          <div className="composer">
            <label htmlFor="talk-input" className="sr">별지기에게 답하기</label>
            <textarea id="talk-input" rows={2} value={text} onChange={(e) => setText(e.target.value)} disabled={!!busy}
              placeholder="편하게 적어 주세요. Ctrl(⌘) + Enter로 보낼 수 있어요." maxLength={8000}
              onKeyDown={(e) => { if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); send(text); } }} />
            <div className="tools">
              <MicButton onText={heard} disabled={!!busy} />
              <button type="submit" className="tbtn send" disabled={!!busy || !text.trim()}
                aria-label="보내기" title="보내기 (Ctrl(⌘) + Enter)"><Icon name="send" /></button>
            </div>
          </div>
        </form>
      )}
    </main>
  );
}
