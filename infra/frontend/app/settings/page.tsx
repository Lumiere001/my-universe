"use client";
// (바) 설정(옵시디언 설정처럼): 묶음 다섯 개 중 하나만 보이고, 설정 하나 = 한 줄(이름 · 한 줄 설명 | 고르는 것).
// 말투 5종 + 미리보기(v8.json 예문, LLM 호출 없음). 팩폭은 경고 확인 뒤에만, 직접 정하기는 원하는 말투를 적은 뒤에만.
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import InstallGuide from "@/components/InstallGuide";
import { KeeperNameField, KEEPER, rememberSettings } from "@/components/Keeper";
import { OneLine } from "@/components/ResultCard";
import { KEEPER_LOOKS, KEEPER_SVG, THEME_NAMES, THEMES, themeOf } from "@/components/universeLook";
import { deleteMe, getMe, MOCK, patchSettings, supabase, why, type Settings, type Tone } from "@/lib/api";
import { useLoad, useOntology } from "@/lib/use";

const GROUPS = ["별지기", "우주와 화면", "말 걸기", "앱", "개인정보와 계정"] as const;
type Group = (typeof GROUPS)[number];
let lastGroup: Group = "별지기";   // 같은 탭 안에서 설정에 다시 오면 마지막에 본 묶음
const CUSTOM: Tone = "직접 정하기";
const NOTE_MAX = 200;
const hex = (n: number) => "#" + n.toString(16).padStart(6, "0");
// 읽어 주기 목소리: 서버 app/core/config.py TTS_VOICES 와 같은 이름 · 순서(첫 값 = 기본). 미리 듣기 = public/voices/ 의 짧은 녹음(유료 호출 없음)
const VOICES = { "따뜻한": "george", "차분한": "matilda", "부드러운": "sarah", "밝은": "will" } as const;
type Voice = keyof typeof VOICES;
const VOICE_NAMES = Object.keys(VOICES) as Voice[];
let sample: HTMLAudioElement | null = null;   // 미리 듣기는 한 번에 하나만
const listen = (v: Voice) => { sample?.pause(); sample = new Audio(`/voices/${VOICES[v]}.mp3`); sample.play().catch(() => { /* 못 틀어도 고른 목소리는 그대로 */ }); };

// 설정 한 줄: 이름 · 한 줄 설명이 먼저, 고르는 것이 그 뒤(넓은 화면은 오른쪽, 휴대폰은 아래). htmlFor 가 있으면 이름이 입력 칸 이름표.
function Row({ name, desc, htmlFor, children }: { name: string; desc?: string; htmlFor?: string; children: (id: string) => React.ReactNode }) {
  const id = useId();
  return (
    <div className="set-row">
      <div className="set-k">
        {htmlFor ? <label htmlFor={htmlFor} id={id}>{name}</label> : <b id={id}>{name}</b>}
        {desc && <p className="sub">{desc}</p>}
      </div>
      <div className="set-v">{children(id)}</div>
    </div>
  );
}

function Seg<T extends string>({ by, options, value, onPick, label }:
  { by: string; options: readonly T[]; value: T; onPick: (v: T) => void; label?: (v: T) => string }) {
  return (
    <div className="seg" role="group" aria-labelledby={by}>
      {options.map((o) => <button key={o} type="button" className="small" aria-pressed={value === o} onClick={() => onPick(o)}>{label ? label(o) : o}</button>)}
    </div>
  );
}

export default function SettingsPage() {
  const [me, err] = useLoad(getMe, "설정을 불러오지 못했어요. 잠시 뒤 화면을 새로 고쳐 주세요.");
  const onto = useOntology();
  const [s, setS] = useState<Settings | null>(null);
  const [group, setGroup] = useState<Group>(lastGroup);
  const [preview, setPreview] = useState<Tone | null>(null);
  const [warn, setWarn] = useState(false);
  const [note, setNote] = useState("");
  const [msg, setMsg] = useState("");
  const [fail, setFail] = useState("");
  useEffect(() => { if (me) { setS(me.settings); setNote(me.settings.tone_note ?? ""); } }, [me]);

  if (err) return <main><p className="err" role="alert">{err}</p></main>;
  if (!s || !onto) return <main><p className="sub">설정을 불러오는 중…</p></main>;

  const save = async (p: Partial<Settings>) => {
    setFail("");
    try {
      const n = await patchSettings(p);
      setS(n); setMsg("저장했어요.");
      rememberSettings(n);
      return true;
    } catch (e) { setMsg(""); setFail(why(e, "저장하지 못했어요. 잠시 뒤 다시 눌러 주세요.")); return false; }
  };
  const pickTone = (t: Tone) => {
    setPreview(t); setWarn(false);
    if (t === "팩폭" && !s.fact_bomb_ack) { setWarn(true); return; }
    if (t === CUSTOM && !s.tone_note) return;   // 원하는 말투를 먼저 적는다(아래 칸)
    save({ tone: t });
  };
  const pickGroup = (g: Group) => { lastGroup = g; setGroup(g); };
  const shownName = preview ?? s.tone;
  const shown = onto.tones.find((t) => t.name === shownName) ?? onto.tones[0];
  const keeper = s.keeper_name || KEEPER, look = s.keeper_look ?? "글자";
  const noteOk = note.trim().length > 0 && !(s.tone === CUSTOM && note.trim() === (s.tone_note ?? ""));

  return (
    <main className="set-page">
      <h1>설정</h1>
      <p className="sub">별지기의 말투와 우주 보기를 내게 맞게 바꿔요.</p>
      {msg && <p className="toast" role="status">{msg}</p>}
      {fail && <p className="err" role="alert">{fail}</p>}

      <div className="set">
        <div className="set-nav" role="group" aria-label="설정 묶음">
          {GROUPS.map((g) => <button key={g} type="button" aria-pressed={group === g} onClick={() => pickGroup(g)}>{g}</button>)}
        </div>

        <section className="set-panel" aria-label={group}>
          <h2>{group}</h2>

          {group === "별지기" && (<>
            <Row name="별지기 이름" desc="말풍선 이름표에 보여요." htmlFor="keeper">
              {() => <KeeperNameField value={keeper} onSave={(n) => save({ keeper_name: n })} />}
            </Row>
            <Row name="별지기 모습" desc="말풍선 동그라미에 들어가요.">
              {(by) => (
                <div className="seg looks" role="group" aria-labelledby={by}>
                  {KEEPER_LOOKS.map((k) => (
                    <button key={k} type="button" className="small look" aria-pressed={look === k} onClick={() => save({ keeper_look: k })}>
                      {k === "글자" ? <span className="letter" aria-hidden>{keeper.slice(0, 1)}</span>
                        : <img src={`/keeper/${KEEPER_SVG[k]}.svg`} alt="" />}<span className="look-name">{k === "글자" ? "이름 글자" : k}</span>
                    </button>
                  ))}
                </div>
              )}
            </Row>
            <section aria-label="말투">
              <Row name="별지기 말투" desc="한마디와 이야기하기에서 쓰는 말투예요.">
                {() => (
                  <div className="seg" role="group" aria-label="말투 고르기">
                    {onto.tones.map((t) => (
                      <button key={t.name} type="button" className="small" aria-pressed={s.tone === t.name} onClick={() => pickTone(t.name as Tone)}>
                        {t.name}{"warning" in t ? " ⚠" : ""}
                      </button>
                    ))}
                  </div>
                )}
              </Row>
              <div className="set-more" aria-live="polite">
                <p className="sub" style={{ margin: "0 0 6px" }}>{shown.name} · {shown.description}</p>
                <div className="voice"><span className="who" aria-hidden>{keeper.slice(0, 1)}</span><div className="bubble"><span className="sub">미리보기 · </span>{shown.example}</div></div>
              </div>

              {shownName === CUSTOM && (
                <form className="set-more stack" aria-label="직접 정하기"
                  onSubmit={async (e) => { e.preventDefault(); if (noteOk && await save({ tone: CUSTOM, tone_note: note.trim() })) setPreview(null); }}>
                  <label htmlFor="tone-note" style={{ color: "var(--text)", fontWeight: 600 }}>원하는 말투를 적어 주세요</label>
                  <textarea id="tone-note" rows={2} maxLength={NOTE_MAX} value={note} onChange={(e) => setNote(e.target.value)}
                    placeholder="예: 친한 언니처럼 반말로, 이모지 하나만" aria-describedby="tone-note-hint" />
                  <p className="sub" id="tone-note-hint" style={{ margin: 0 }}>{note.length} / {NOTE_MAX} · 말하는 방식만 바뀌어요. 위기 글 · 마음이 무거운 날엔 이 말투 대신 다정하게 위로해요.</p>
                  <div className="row">
                    <button type="submit" className="primary small" disabled={!noteOk}>이 말투로 할게요</button>
                    <button type="button" className="small" onClick={() => { setPreview(null); setNote(s.tone_note ?? ""); }}>취소</button>
                  </div>
                </form>
              )}

              {warn && (
                <div className="care stack set-more" role="alertdialog" aria-label="팩폭 경고" data-testid="fact-bomb-warning">
                  <h3 style={{ color: "var(--orange)", margin: 0 }}>⚠ {(onto.tones.find((t) => t.name === "팩폭") as { warning?: string }).warning}</h3>
                  <p style={{ margin: 0 }}>{onto.fact_bomb.strength}</p>
                  <p style={{ margin: 0 }}><b>그래도 넘지 않는 선 {onto.fact_bomb.never_cross.length}가지</b></p>
                  <ol style={{ margin: 0, paddingLeft: 20 }}>{onto.fact_bomb.never_cross.map((x) => <li key={x}>{x}</li>)}</ol>
                  <div className="row">
                    <button className="danger" onClick={async () => { await save({ tone: "팩폭", fact_bomb_ack: true }); setWarn(false); }}>알겠어요, 팩폭으로 할게요</button>
                    <button onClick={() => { setWarn(false); setPreview(null); }}>취소</button>
                  </div>
                </div>
              )}
            </section>
          </>)}

          {group === "우주와 화면" && (<>
            <Row name="우주 테마" desc="우주 화면의 바탕 · 해 · 별 · 행성 색이 바뀌어요. 선 · 고리 색은 뜻이 있어 그대로예요.">
              {(by) => (
                <div className="seg" role="group" aria-labelledby={by}>
                  {THEME_NAMES.map((t) => (
                    <button key={t} type="button" className="small look" aria-pressed={themeOf(s.theme) === t} onClick={() => save({ theme: t })}>
                      <span className="swatch" aria-hidden style={{ background: hex(THEMES[t].bg) }}>
                        {THEMES[t].sun.slice(0, 3).map((c) => <i key={c} style={{ background: hex(c) }} />)}
                      </span>{t}
                    </button>
                  ))}
                </div>
              )}
            </Row>
            <Row name="다른 영역과 이어진 선 보이기" desc="다른 삶의 영역끼리 이어진 선을 우주에 언제 보일지 골라요.">
              {(by) => <Seg by={by} options={["숨김", "눌렀을 때", "항상"] as const} value={s.cross_links} onPick={(v) => save({ cross_links: v })} />}
            </Row>
          </>)}

          {group === "말 걸기" && (<>
            <Row name="다음 걸음 제안 빈도" desc="별지기 한마디에 작은 다음 걸음을 얼마나 자주 넣을지 골라요.">
              {(by) => <Seg by={by} options={["적게", "보통", "많이"] as const} value={s.suggestions} onPick={(v) => save({ suggestions: v })} />}
            </Row>
            <Row name="마음 날씨 물어보기" desc="처음 만났을 때와 기분이 드러나지 않은 글에만 물어요.">
              {(by) => <Seg by={by} options={["묻기", "묻지 않기"] as const} value={s.weather_ask ? "묻기" : "묻지 않기"}
                onPick={(v) => save({ weather_ask: v === "묻기" })} />}
            </Row>
            <Row name="읽어 주기 목소리" desc="이야기하기에서 '읽어 주기'를 켜면 별지기 말을 이 목소리로 읽어요.">
              {(by) => {
                const v = (s.tts_voice ?? VOICE_NAMES[0]) as Voice;
                return (
                  <div className="row">
                    <Seg by={by} options={VOICE_NAMES} value={v} onPick={(x) => save({ tts_voice: x })} />
                    <button type="button" className="small" aria-label={`${v} 목소리 미리 듣기`} onClick={() => listen(v)}><span aria-hidden>▶ </span>미리 듣기</button>
                  </div>
                );
              }}
            </Row>
            <Row name="오늘 상태" desc="둘 다 별지기 한마디에 붙은 버튼으로 켜고, 그날만 이어져요.">
              {() => <p className="sub" style={{ margin: 0 }}>오늘은 살살: {s.gentle_today ? "켜짐(오늘만)" : "꺼짐"} · 오늘은 위로만: {s.comfort_only_today ? "켜짐(오늘만)" : "꺼짐"}</p>}
            </Row>
          </>)}

          {group === "앱" && (<>
            <InstallGuide />
            <div className="set-row set-one"><OneLine target="app" /></div>
          </>)}

          {group === "개인정보와 계정" && (<>
            <Row name="동의 내용" desc="선택 동의를 보고 바꿀 수 있어요.">
              {() => <Link className="btn" href="/consent">동의 내용 보기 · 바꾸기</Link>}
            </Row>
            <Row name="문서">
              {() => <p style={{ margin: 0 }}><Link href="/privacy">개인정보처리방침</Link> · <Link href="/terms">이용약관</Link></p>}
            </Row>
            {!MOCK && <Row name="로그아웃">{() => <button onClick={() => supabase()?.auth.signOut()}>로그아웃</button>}</Row>}
            {!MOCK && <DeleteAccount />}
          </>)}
        </section>
      </div>
    </main>
  );
}

// 계정과 모든 기록 지우기. '지우기'를 직접 입력해야 버튼이 켜진다. 끝나면 로그아웃.
function DeleteAccount() {
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const go = async () => {
    setBusy(true); setErr("");
    try { await deleteMe(); await supabase()?.auth.signOut(); }
    catch (e) { setErr(why(e, "계정을 지우지 못했어요. 잠시 뒤 다시 해 주세요.")); setBusy(false); }
  };
  return (
    <section className="set-row set-danger stack" aria-label="계정 지우기">
      <div className="set-k">
        <b>계정과 모든 기록 지우기</b>
        <p className="sub">일기 · 생각 · 사람 · 되고 싶은 모습 · 설정과 계정이 모두 지워져요. <b>되돌릴 수 없어요.</b></p>
      </div>
      <div className="set-v stack">
        <div><label htmlFor="del-confirm">확인하려면 &apos;지우기&apos;를 입력해 주세요</label>
          <input id="del-confirm" value={typed} onChange={(e) => setTyped(e.target.value)} autoComplete="off" /></div>
        <button className="danger" disabled={typed.trim() !== "지우기" || busy} onClick={go}>{busy ? "지우는 중…" : "계정과 모든 기록 지우기"}</button>
        {err && <p className="err" role="alert">{err}</p>}
      </div>
    </section>
  );
}
