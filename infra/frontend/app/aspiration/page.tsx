"use client";
// (마) 되고 싶은 모습(PRD v9): 별지기와 대화하듯 다섯 질문(components/AspirationInterview) → 한 화면 요약 → 북극성. 이력 보존.
// ?interview=1 = 처음 시작 인터뷰(온보딩, Shell 이 보냄): 띄우거나 '나중에 할래요'면 첫 대화(/)로 간다.
// 며칠 뒤 다시 권할 때(should_ask)는 허락을 구한 뒤 같은 인터뷰를 연다. 지금 모습 카드는 다섯 답 · 닿은 순간.
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import AspirationInterview from "@/components/AspirationInterview";
import { useKeeperName } from "@/components/Keeper";
import { unquote } from "@/components/ResultCard";
import { declineAspiration, getAspiration, why, type Aspiration } from "@/lib/api";
import { useLoad } from "@/lib/use";

function AspirationCard({ a, title }: { a: Aspiration; title: string }) {
  return (
    <section className="card asp-card" aria-label={title}>
      <h2>{title}</h2>
      <p className="quote" style={{ borderColor: "var(--gold)" }}>“{a.said}”</p>
      <div className="row" style={{ marginBottom: 6 }}>{a.values.map((v) => <span key={v} className="badge g">{v}</span>)}</div>
      <dl className="asp-facts">
        {a.why && <><dt>이유</dt><dd>{a.why}</dd></>}
        {a.scene && <><dt>장면</dt><dd>{a.scene}</dd></>}
        <dt>걸림돌</dt><dd>{a.obstacle}</dd>
        <dt>그때 해 볼 것</dt><dd>{a.if_then}</dd>
        <dt>말한 날</dt><dd>{a.said_at.slice(0, 10)}</dd>
      </dl>
      {a.reached.length > 0 && (
        <div className="asp-reached">
          <b>닿은 순간</b>
          <ul>{a.reached.map((r) => <li key={r.entry_id + r.quote} className="quote" style={{ borderColor: "var(--gold)" }}>{r.at.slice(0, 10)} · “{unquote(r.quote)}”</li>)}</ul>
        </div>
      )}
    </section>
  );
}

export default function AspirationPage() {
  return <Suspense fallback={<main><p className="sub">되고 싶은 모습을 불러오는 중…</p></main>}><Page /></Suspense>;
}

function Page() {
  const router = useRouter();
  const intro = useSearchParams().has("interview");
  const [data, err, reload] = useLoad(getAspiration, "되고 싶은 모습을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const keeper = useKeeperName();
  const [fail, setFail] = useState("");
  const [mode, setMode] = useState<"view" | "talk" | "done" | "declined">(intro ? "talk" : "view");
  const [declined, setDeclined] = useState("");

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!data) return <main><p className="sub">되고 싶은 모습을 불러오는 중…</p></main>;
  const showAsk = mode === "view" && !data.current && data.ask.should_ask;

  const decline = async (m: "skip" | "stop" | "later") => {
    setFail("");
    try { await declineAspiration(m); }
    catch (e) { return setFail(why(e, "고른 것을 저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.")); }
    if (intro) return router.replace("/");
    setDeclined(m === "stop" ? "더 묻지 않을게요. 언제든 여기서 다시 적을 수 있어요." : "알겠어요. 지금은 묻지 않을게요. 나중에 계기가 생기면 다시 여쭤볼게요.");
    setMode("declined");
  };
  const done = () => { if (intro) return router.replace("/"); setMode("done"); reload(); };

  if (mode === "talk") return (
    <main className="asp-page">
      <h1 className="sr">되고 싶은 모습</h1>
      <AspirationInterview first={intro} onDone={done} onLater={() => decline(intro ? "later" : "skip")} />
      {fail && <p className="err" role="alert">{fail}</p>}
    </main>
  );

  return (
    <main>
      <h1 className="sr">되고 싶은 모습</h1>
      <p className="sub">내가 말한 되고 싶은 모습이 우주의 북극성이 돼요. 거리나 점수로 재지 않고, 글에서 그 모습에 닿은 순간을 짚고, 멀어질 때는 내가 정한 걸음을 건네요.</p>

      {mode === "declined" && <p className="toast" role="status">{declined}</p>}
      {mode === "done" && <p className="toast" role="status">북극성으로 띄웠어요. 예전 모습은 &apos;예전 모습 보기&apos;에 남겨 둘게요.</p>}

      {showAsk && (
        <section className="card stack" aria-label="되고 싶은 모습 묻기">
          <div className="voice"><span className="who" aria-hidden>{keeper.slice(0, 1)}</span>
            <div><div className="sub">{keeper}</div>
              <div className="bubble">며칠 동안 써 온 글을 보니, 되고 싶은 모습을 한번 같이 적어 보면 좋겠어요. 다섯 가지만 천천히 물어봐도 될까요?</div></div></div>
          <div className="row">
            <button className="primary" onClick={() => setMode("talk")}>좋아요</button>
            <button onClick={() => decline("skip")}>이번엔 넘어가기</button>
            <button onClick={() => decline("stop")}>그만 묻기</button>
          </div>
          {fail && <p className="err" role="alert" style={{ margin: 0 }}>{fail}</p>}
        </section>
      )}

      {data.current && <AspirationCard a={data.current} title="지금의 북극성" />}
      {!showAsk && (
        <div className="row">
          <button onClick={() => setMode("talk")}>{data.current ? "새로 적기" : "되고 싶은 모습 적어 보기"}</button>
          {data.history.length > 0 && (
            <details className="asp-history">
              <summary className="btn">예전 모습 보기 ({data.history.length})</summary>
              <ul>
                {data.history.map((a) => (
                  <li key={a.id}>
                    <span className="meta">{a.said_at.slice(0, 10)}</span> “{a.said}”
                    {a.values.map((v) => <span key={v} className="badge g">{v}</span>)}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </main>
  );
}
