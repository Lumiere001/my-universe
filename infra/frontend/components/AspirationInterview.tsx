"use client";
// 되고 싶은 모습 인터뷰(PRD v9 Q3): 별지기와 대화하듯 다섯 질문(방향 · 이유 · 장면 · 안쪽 걸림 · 그때) → 한 화면 요약 → 고칠 것은 다시 묻기.
// 질문 · 받아 주는 말 · 예시는 온톨로지 aspiration.ask_steps(LLM 없음). '몰라요'나 아주 짧은 답이면 예시로 한 번만 더 묻고,
// 그래도 모르면 그 칸은 비워 두고 다음으로. 방향이 피하는 말이면 왜 묻는지와 함께 한 번만 돌려 묻고, '처음 말 그대로 둘래요'로 그대로 둘 수도 있다
// (2026-11-04 사용자 불편 「두 질문의 차이를 모르겠다」). 답은 사용자가 한 말 그대로 남긴다.
import { useEffect, useRef, useState } from "react";
import Icon from "@/components/Icon";
import { useKeeperName } from "@/components/Keeper";
import MicButton from "@/components/MicButton";
import { saveAspiration, suggestValues, why as whyOf, type Aspiration } from "@/lib/api";
import { useOntology } from "@/lib/use";

type Key = "want" | "why" | "scene" | "obstacle" | "if_then";
type Line = { who: "keeper" | "me"; text: string };
const DONT_KNOW = /^(몰라|모르|글쎄|없어|없음|잘 ?모르|패스|pass)/i;
const AVOID = /(않는|안 하는|안하는|안 되는|하지 않|말자|않기)/;
const PRE = { whiteSpace: "pre-line" } as const;

export default function AspirationInterview({ onDone, onLater }: { onDone: (a: Aspiration) => void; onLater: () => void }) {
  const onto = useOntology();
  const keeper = useKeeperName();
  const steps = onto?.aspiration.ask_steps ?? [];
  const [step, setStep] = useState(0);
  const [ans, setAns] = useState<Partial<Record<Key, string>>>({});
  const [lines, setLines] = useState<Line[]>([]);
  const [draft, setDraft] = useState("");
  const [retried, setRetried] = useState<number[]>([]);   // 예시로 한 번 더 물은 질문
  const [avoided, setAvoided] = useState("");   // 돌려 물은 처음 방향 답(그대로 두기 단추에 씀)
  const [fixing, setFixing] = useState<number | null>(null);   // 요약에서 '고칠래요'로 다시 묻는 질문
  const [summary, setSummary] = useState(false);
  const [values, setValues] = useState<string[]>([]);
  const [suggested, setSuggested] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [fail, setFail] = useState("");
  const endRef = useRef<HTMLDivElement>(null);
  useEffect(() => { endRef.current?.scrollIntoView({ block: "end" }); }, [lines.length, summary]);

  useEffect(() => {   // 처음 말: 인사 + 첫 질문
    if (!steps.length || lines.length) return;
    const hi = "되고 싶은 모습을 다섯 가지만 천천히 물어볼게요. 답하기 어려우면 '나중에 할래요'를 눌러도 괜찮아요.";
    setLines([{ who: "keeper", text: hi }, { who: "keeper", text: steps[0].question }]);
  }, [steps.length]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!onto) return <p className="sub">불러오는 중…</p>;
  const key = (i: number) => steps[i].key as Key;

  const toSummary = (a: Partial<Record<Key, string>>) => {
    setSummary(true); setFixing(null);
    if (a.why && !suggested.length) suggestValues(a.why).then((r) => { setSuggested(r.values); setValues(r.values); }, () => { /* 제안은 덤 */ });
  };
  const next = (a: Partial<Record<Key, string>>, said: string, reply: string) => {
    const more: Line[] = [{ who: "me", text: said }, { who: "keeper", text: reply }];
    if (fixing !== null || step + 1 >= steps.length) { setLines([...lines, ...more]); return toSummary(a); }
    setLines([...lines, ...more, { who: "keeper", text: steps[step + 1].question }]);
    setStep(step + 1);
  };
  const answer = (said: string) => {
    const t = said.trim();
    if (!t) return;
    setDraft("");
    const i = fixing ?? step;
    if (DONT_KNOW.test(t) || t.replace(/\s/g, "").length < 2) {
      if (!retried.includes(i)) { setRetried([...retried, i]); setLines([...lines, { who: "me", text: t }, { who: "keeper", text: steps[i].hint }]); return; }
      const a = { ...ans, [key(i)]: "" };
      setAns(a);
      return next(a, t, "괜찮아요. 이건 비워 두고, 나중에 다시 여쭤볼게요.");
    }
    if (i === 0 && AVOID.test(t) && !avoided) {
      setAvoided(t);
      setLines([...lines, { who: "me", text: t }, { who: "keeper", text: steps[0].avoid_ask ?? steps[0].question }]);
      return;
    }
    const a = { ...ans, [key(i)]: t };
    setAns(a);
    next(a, t, steps[i].ack);
  };
  const fix = (i: number) => {
    setSummary(false); setFixing(i);
    setLines([...lines, { who: "keeper", text: `다시 물어볼게요. ${steps[i].question}` }]);
  };
  const save = async () => {
    setBusy(true); setFail("");
    try {
      onDone(await saveAspiration({ want: ans.want ?? "", why: ans.why ?? "", scene: ans.scene ?? "",
        obstacle: ans.obstacle ?? "", if_then: ans.if_then ?? "", values }));
    } catch (e) { setFail(whyOf(e, "북극성으로 띄우지 못했어요. 적은 답은 그대로 있으니 잠시 뒤 다시 눌러 주세요.")); }
    finally { setBusy(false); }
  };

  const who = <span className="who" aria-hidden>{keeper.slice(0, 1)}</span>;
  return (
    <section className="asp-talk" aria-label="되고 싶은 모습 인터뷰">
      <div className="row" style={{ justifyContent: "space-between", flexWrap: "nowrap" }}>
        <ol className="asp-dots" aria-label={`${Math.min(step + 1, steps.length)} / ${steps.length}`}>
          {steps.map((x, i) => <li key={x.key} data-on={summary || i <= step ? "" : undefined} />)}
        </ol>
        <button type="button" className="small" onClick={onLater} disabled={busy}>나중에 할래요</button>
      </div>
      <div className="asp-log" aria-live="polite">
        {lines.map((l, i) => l.who === "me"
          ? <div key={i} className="bubble me" style={{ margin: "0 0 10px auto" }}><p style={{ margin: 0, ...PRE }}>{l.text}</p></div>
          : <div key={i} className="voice" style={{ marginBottom: 10 }}>{who}
              <div className="bubble" style={{ maxWidth: "85%" }}><p style={{ margin: 0, ...PRE }}>{l.text}</p></div></div>)}

        {summary && (
          <div className="card stack asp-sum" aria-label="이렇게 적어 둘게요">
            <h2 style={{ margin: 0 }}>이렇게 적어 둘게요</h2>
            <dl className="asp-facts">
              {steps.map((x, i) => (
                <div key={x.key} className="asp-row">
                  <dt>{x.name}</dt>
                  <dd>{ans[key(i)] ? `“${ans[key(i)]}”` : <span className="sub">비워 둠 · 나중에 물어볼게요</span>}</dd>
                  <button type="button" className="small" onClick={() => fix(i)}>고칠래요</button>
                </div>
              ))}
            </dl>
            <fieldset>
              <legend>이 모습이 기대는 가치{suggested.length > 0 && " · 별지기가 이유에서 골라 봤어요"}</legend>
              <div className="row">
                {onto.values.map((v) => (
                  <button key={v.name} type="button" className="small" title={v.definition} aria-pressed={values.includes(v.name)}
                    disabled={!values.includes(v.name) && values.length >= 3}
                    onClick={() => setValues(values.includes(v.name) ? values.filter((x) => x !== v.name) : [...values, v.name])}>{v.name}</button>
                ))}
              </div>
            </fieldset>
            {!ans.want && <p className="sub" style={{ margin: 0 }}>방향이 있어야 북극성이 떠요. &apos;고칠래요&apos;로 방향을 적어 주세요.</p>}
            <button className="primary" onClick={save} disabled={busy || !ans.want}>북극성으로 띄우기</button>
            {fail && <p className="err" role="alert" style={{ margin: 0 }}>{fail}</p>}
          </div>
        )}
        {avoided && step === 0 && fixing === null && ans.want === undefined && (   // 돌려 물은 말 바로 밑 답 단추
          <button type="button" className="small" style={{ marginLeft: 36 }} onClick={() => answer(avoided)}>처음 말 그대로 둘래요</button>)}
        <div ref={endRef} />
      </div>

      {!summary && (
        <form className="composer" aria-label="답하기" onSubmit={(e) => { e.preventDefault(); answer(draft); }}>
          <label htmlFor="asp-input" className="sr">별지기에게 답하기</label>
          <textarea id="asp-input" rows={2} value={draft} maxLength={500} onChange={(e) => setDraft(e.target.value)}
            placeholder="편하게 적어 주세요" autoFocus
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); answer(draft); } }} />
          <div className="tools">
            <MicButton onText={(t) => answer(t)} disabled={busy} />
            <button type="submit" className="tbtn send" disabled={!draft.trim()} aria-label="보내기"><Icon name="send" /></button>
          </div>
        </form>
      )}
    </section>
  );
}
