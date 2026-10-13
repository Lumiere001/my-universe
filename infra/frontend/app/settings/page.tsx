"use client";
// (바) 설정: 말투 4종 + 미리보기(v8.json 예문, LLM 호출 없음). 팩폭은 경고 확인 뒤에만. 제안 빈도 · 영역 넘는 선 · 날씨 묻기.
import Link from "next/link";
import { useEffect, useState } from "react";
import InstallGuide from "@/components/InstallGuide";
import { KeeperNameField, KEEPER, rememberKeeperName } from "@/components/Keeper";
import { OneLine } from "@/components/ResultCard";
import { deleteMe, getMe, MOCK, patchSettings, supabase, type Settings, type Tone } from "@/lib/api";
import { useLoad, useOntology } from "@/lib/use";

function Choice<T extends string>({ legend, options, value, onPick }: { legend: string; options: readonly T[]; value: T; onPick: (v: T) => void }) {
  return (
    <fieldset className="card">
      <legend>{legend}</legend>
      <div className="row">
        {options.map((o) => <button key={o} type="button" className="small" aria-pressed={value === o} onClick={() => onPick(o)}>{o}</button>)}
      </div>
    </fieldset>
  );
}

export default function SettingsPage() {
  const [me, err] = useLoad(getMe);
  const onto = useOntology();
  const [s, setS] = useState<Settings | null>(null);
  const [preview, setPreview] = useState<Tone | null>(null);
  const [warn, setWarn] = useState(false);
  const [msg, setMsg] = useState("");
  useEffect(() => { if (me) setS(me.settings); }, [me]);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!s || !onto) return <main><p className="sub">불러오는 중…</p></main>;

  const save = async (p: Partial<Settings>) => {
    try {
      const n = await patchSettings(p);
      setS(n); setMsg("저장했어요.");
      if (n.keeper_name) rememberKeeperName(n.keeper_name);
    } catch (e) { setMsg((e as Error).message); }
  };
  const pickTone = (t: Tone) => {
    setPreview(t);
    if (t === "팩폭" && !s.fact_bomb_ack) { setWarn(true); return; }
    setWarn(false); save({ tone: t });
  };
  const shown = onto.tones.find((t) => t.name === (preview ?? s.tone))!;

  return (
    <main>
      <h1>설정</h1>
      {msg && <p className="toast" role="status">{msg}</p>}

      <section className="card stack" aria-label="말투">
        <KeeperNameField value={s.keeper_name ?? KEEPER} onSave={(n) => save({ keeper_name: n })} />
        <h2>별지기 말투</h2>
        <div className="row" role="group" aria-label="말투 고르기">
          {onto.tones.map((t) => (
            <button key={t.name} className="small" aria-pressed={s.tone === t.name} onClick={() => pickTone(t.name as Tone)}>
              {t.name}{"warning" in t ? " ⚠" : ""}
            </button>
          ))}
        </div>
        <div aria-live="polite">
          <p className="sub" style={{ margin: "4px 0" }}>{shown.name} · {shown.description}</p>
          <div className="voice"><span className="who" aria-hidden>별</span><div className="bubble"><span className="sub">미리보기 · </span>{shown.example}</div></div>
        </div>

        {warn && (
          <div className="care stack" role="alertdialog" aria-label="팩폭 경고" data-testid="fact-bomb-warning">
            <h3 style={{ color: "var(--orange)" }}>⚠ {(onto.tones.find((t) => t.name === "팩폭") as { warning?: string }).warning}</h3>
            <p>{onto.fact_bomb.strength}</p>
            <p style={{ margin: 0 }}><b>그래도 넘지 않는 선 {onto.fact_bomb.never_cross.length}가지</b></p>
            <ol style={{ margin: 0, paddingLeft: 20 }}>{onto.fact_bomb.never_cross.map((x) => <li key={x}>{x}</li>)}</ol>
            <div className="row">
              <button className="danger" onClick={async () => { await save({ tone: "팩폭", fact_bomb_ack: true }); setWarn(false); }}>알겠어요, 팩폭으로 할게요</button>
              <button onClick={() => { setWarn(false); setPreview(null); }}>취소</button>
            </div>
          </div>
        )}
      </section>

      <Choice legend="다음 걸음 제안 빈도" options={["적게", "보통", "많이"] as const} value={s.suggestions} onPick={(v) => save({ suggestions: v })} />
      <Choice legend="다른 영역과 이어진 선 보이기" options={["숨김", "눌렀을 때", "항상"] as const} value={s.cross_links} onPick={(v) => save({ cross_links: v })} />
      <Choice legend="마음 날씨 물어보기(첫 만남 · 기분이 안 드러난 글에만)" options={["묻기", "묻지 않기"] as const}
        value={s.weather_ask ? "묻기" : "묻지 않기"} onPick={(v) => save({ weather_ask: v === "묻기" })} />

      <section className="card">
        <p className="sub" style={{ marginTop: 0 }}>오늘은 살살: {s.gentle_today ? "켜짐(오늘만)" : "꺼짐"} · 오늘은 위로만: {s.comfort_only_today ? "켜짐(오늘만)" : "꺼짐"}</p>
        <OneLine target="app" />
      </section>

      <InstallGuide />
      {!MOCK && <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>}
      {!MOCK && <DeleteAccount />}
      <p className="sub"><Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link> · <Link href="/consent">동의 내용 보기 · 바꾸기</Link></p>
    </main>
  );
}

// 맨 아래: 계정과 모든 기록 지우기. '지우기'를 직접 입력해야 버튼이 켜진다. 끝나면 로그아웃.
function DeleteAccount() {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try { await deleteMe(); await supabase()?.auth.signOut(); }
    catch (e) { setErr((e as Error).message); setBusy(false); }
  };
  return (
    <section className="card stack" aria-label="계정 지우기" style={{ marginTop: 32 }}>
      <h2>계정과 모든 기록 지우기</h2>
      <p className="sub" style={{ margin: 0 }}>일기 · 생각 · 사람 · 되고 싶은 모습 · 설정과 계정이 모두 지워져요. <b>되돌릴 수 없어요.</b></p>
      <div><label htmlFor="del-confirm">확인하려면 &apos;지우기&apos;를 입력해 주세요</label>
        <input id="del-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" /></div>
      <button className="danger" disabled={typed.trim() !== "지우기" || busy} onClick={go}>{busy ? "지우는 중…" : "계정과 모든 기록 지우기"}</button>
      {err && <p className="err" role="alert">{err}</p>}
    </section>
  );
}
