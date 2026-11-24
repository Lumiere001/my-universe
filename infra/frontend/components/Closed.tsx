"use client";
// 시험 기간 끝(2026-11-25 동규 「닫고 일기 받기 · 써 본 의견 받기」): 닫힌 서비스의 화면은 이것 하나(Shell 이 모든 주소에서 보임,
// 개인정보처리방침 · 이용약관 · 운영 화면만 그대로). 서버도 새 기록 · 대화 · 고치기를 403 service_closed 로 막는다(config.SERVICE_CLOSED).
//  로그인 전 = 인사 + 내 일기를 받으려면 구글 로그인
//  로그인 뒤 = 인사 + 내 일기 받기(읽기 좋은 .md · 정리까지 JSON) + 써 보니 어땠는지(마치며 의견 → POST /feedback, 운영자가 읽음) + 계정 지우기
import Link from "next/link";
import { useEffect, useState } from "react";
import DeleteAccount from "@/components/DeleteAccount";
import { localToday } from "@/components/EntryTools";
import { DownloadJson } from "@/components/ResultCard";
import { exportDiary, getMe, MOCK, sendFeedback, supabase, why, type EntryResult } from "@/lib/api";
import { KEEP_UNTIL } from "@/lib/site";


type Rec = Pick<EntryResult, "status" | "title" | "written_at" | "day" | "info" | "message"> & { text?: string };
const quote = (label: string, t: string) => `> **${label}** ${t.trim().replace(/\n+/g, "\n> ")}`;

// 받은 JSON(GET /export, 먼저 쓴 것부터) → 사람이 읽는 글 한 편. 원문이 먼저, 별지기 정리 · 한마디는 인용으로 아래에.
export function diaryMarkdown(records: Rec[], today: string) {
  const parts = records.map((r) => {
    const day = (r.day || r.written_at || "").slice(0, 10);
    const out = [`## ${day}${r.title ? ` · ${r.title}` : ""}`, "", (r.text || "").trim() || "(글이 없어요)"];
    const notes = [r.info?.summary && quote("별지기 정리", r.info.summary), r.message?.text && quote("별지기 한마디", r.message.text)].filter(Boolean);
    if (notes.length) out.push("", notes.join("\n>\n"));
    if (r.status === "failed") out.push("", "_(정리하지 못한 글이에요. 쓴 글은 그대로 남아 있어요.)_");
    return out.join("\n");
  });
  return [`# 나의 우주 — 내 일기 ${records.length}편\n\n받은 날: ${today}`, ...parts].join("\n\n---\n\n") + "\n";
}

function DownloadText() {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const all = (await exportDiary()) as { records: Rec[] };
      const url = URL.createObjectURL(new Blob([diaryMarkdown(all.records, localToday())], { type: "text/markdown;charset=utf-8" }));
      const a = document.createElement("a");
      a.href = url;
      a.download = `나의우주-일기-${localToday()}.md`;
      a.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (x) { setErr(why(x, "받지 못했어요. 잠시 뒤 다시 해 주세요.")); } finally { setBusy(false); }
  };
  return (
    <div className="stack">
      <button type="button" disabled={busy} onClick={go}>{busy ? "일기를 모으는 중…" : "내 일기 받기"}</button>
      {err && <p className="err" role="alert">{err}</p>}
    </div>
  );
}

function ClosingNote() {
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [err, setErr] = useState("");
  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return setErr("하고 싶은 말을 적어 주세요.");
    setBusy(true); setErr("");
    try { await sendFeedback({ target: "app", value: "마치며 의견", text: text.trim().slice(0, 500), ops: true }); setDone(true); }
    catch (x) { setErr(why(x, "보내지 못했어요. 잠시 뒤 다시 해 주세요.")); } finally { setBusy(false); }
  };
  if (done) return <p className="toast" role="status">고마워요. 보내 주신 말은 다음 서비스를 만들 때 꼭 읽을게요.</p>;
  return (
    <form onSubmit={send} className="stack" aria-label="써 보니 어땠나요">
      <label htmlFor="closing-note" className="sub">좋았던 점, 아쉬웠던 점, 다시 쓰고 싶은지… 편하게 알려 주세요.</label>
      <textarea id="closing-note" value={text} maxLength={500} rows={5} style={{ minHeight: 0 }} onChange={(e) => setText(e.target.value)}
        placeholder="예: 별지기가 지난 생각을 꺼내 줄 때 좋았어요. 정리가 오래 걸려서 아쉬웠어요." />
      <p className="sub">보내면 운영자가 읽고 다음 서비스를 만드는 데만 써요. 다른 사람 이름은 가명으로 바꿔 읽어요.</p>
      <button type="submit" disabled={busy}>{busy ? "보내는 중…" : "보내기"}</button>
      {err && <p className="err" role="alert">{err}</p>}
    </form>
  );
}

export default function Closed({ signedIn }: { signedIn: boolean }) {
  const [count, setCount] = useState<number | null>(null);
  useEffect(() => { if (signedIn) getMe().then((m) => setCount(m.onboarding.entries), () => setCount(null)); }, [signedIn]);
  const login = () => supabase()?.auth.signInWithOAuth({ provider: "google", options: { redirectTo: window.location.origin } });

  return (
    <main className="stack">
      <section className="card stack">
        <h1>시험 기간이 끝났어요</h1>
        <p>그동안 나의 우주에 하루를 들려주셔서 고마워요. 시험 기간이 끝나 이제 새 일기는 받지 않아요.</p>
        <p>기회가 되면 더 좋은 서비스로 다시 찾아올게요.</p>
      </section>

      {!signedIn ? (
        <section className="card stack">
          <h2>내 일기 받기</h2>
          <p className="sub">지금까지 쓴 일기는 {KEEP_UNTIL}까지 받을 수 있어요. 쓰던 구글 계정으로 로그인해 주세요.</p>
          <button onClick={login}>구글로 로그인</button>
        </section>
      ) : (
        <>
          <section className="card stack" aria-label="내 일기 받기">
            <h2>내 일기 받기</h2>
            {count === 0 ? <p className="sub">받을 일기가 없어요.</p> : <>
              <p className="sub">
                지금까지 쓴 {count ? `일기 ${count}편을` : "일기를"} 글 파일 하나로 받아요. <b>{KEEP_UNTIL}까지</b> 받을 수 있고, 그 뒤에는 모든 기록을 지워요.
              </p>
              <DownloadText />
              <DownloadJson label="별지기 정리까지 모두 받기(JSON)" />
            </>}
          </section>

          <section className="card stack" aria-label="써 보니 어땠나요">
            <h2>써 보니 어땠나요?</h2>
            <ClosingNote />
          </section>

          <section className="card stack">
            <h2>지금 지우고 싶다면</h2>
            <p className="sub">{KEEP_UNTIL}을 기다리지 않고 지금 지울 수도 있어요. 받을 일기는 먼저 받아 두세요.</p>
            <DeleteAccount />
            {!MOCK && <button className="small" onClick={() => supabase()?.auth.signOut()}>로그아웃</button>}
          </section>
        </>
      )}
      <p className="sub"><Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link></p>
    </main>
  );
}
