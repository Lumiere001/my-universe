"use client";
// 목소리로 이야기하기(2026-11-03 동규 「헤이링처럼 고른 시각에 화면 전체에서 대화」 → 「통화보다 나의 우주를 만들어 가는 느낌」).
// 별이 태어나는 대화(동규 11/3 A안): 말 걸어 옴(내 우주 + 가운데 흐린 성운 · 받기 | 나중에) → 대화 중(가운데 원이 별지기가 말할 땐 커지고 들을 땐 내 목소리만큼 움직임, 마지막 한 줄 자막) →
// 끝(별지기 · 나 대본 전체 → 일기로 정리하기). 대화 내용은 이야기 대화(startTalk · sayTalk)에 그대로 쌓여, 정리하기는 이야기 탭의 정리 확인을 다시 쓴다.
// 받기를 눌러야 시작한다: 휴대폰 브라우저는 사람이 누른 뒤에만 마이크 · 소리를 열 수 있다(앱 스토어 앱의 진짜 전화 화면은 웹앱으로는 못 띄움).
// 엔진(같은 모양 Engine): 실제는 ElevenLabs 실시간 대화 + 별지기 머리는 Solar(동규 11/3 A안) — 서버가 대화를 열고 짧은 토큰을 주면
// 브라우저가 WebRTC 로 붙고, 별지기 답은 ElevenLabs 가 우리 서버(/voice/llm)로 물어 기존 이야기 턴(가명 · 위기 · 저장)을 그대로 지난다.
// 가짜 데이터 모드는 연습 엔진(정해 둔 문장으로 주고받기).
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import CallCosmos from "@/components/CallCosmos";
import CallNebula, { type NebulaState } from "@/components/CallNebula";
import Icon from "@/components/Icon";
import { useKeeperName } from "@/components/Keeper";
import { getMe, getUniverse, MOCK, sayTalk, startCall, startTalk, why } from "@/lib/api";
import { useLoad } from "@/lib/use";

type Line = { role: "keeper" | "me"; text: string };
type Mode = "speaking" | "listening";
type Engine = { level: () => number; mute: (m: boolean) => void; end: () => void };
type Hooks = { onLine: (l: Line) => void; onMode: (m: Mode) => void };

// 연습 엔진: 가상 인물 하늘이 말한 셈 치는 문장. 별지기 답은 가짜 데이터의 이야기 대화(sayTalk)에서 받는다
const DEMO = ["오늘 드디어 관심 있던 팀 한 곳에 메일을 보냈어.", "보내고 나니 후련했는데 답장이 올지 좀 떨려.", "응, 오늘은 여기까지 할게."];
const wait = (ms: number) => new Promise((ok) => setTimeout(ok, ms));

function demoEngine({ onLine, onMode }: Hooks): Engine {
  let mode: Mode = "listening", talking = false, muted = false, over = false;
  const run = async () => {
    const c = await startTalk();
    for (let i = 0; !over; i++) {
      const said = c.turns.at(-1)!.text;
      mode = "speaking"; onMode(mode); onLine({ role: "keeper", text: said });
      await wait(Math.min(6000, 900 + said.length * 55));   // 별지기가 말하는 시간(글 길이만큼)
      mode = "listening"; onMode(mode);
      if (i >= DEMO.length) return;                         // 할 말을 다 하면 끊기를 기다린다
      await wait(1400);
      if (over) return;
      talking = true; await wait(1200 + DEMO[i].length * 45); talking = false;
      if (over) return;
      onLine({ role: "me", text: DEMO[i] });
      const next = await sayTalk(c.id, DEMO[i], () => {}, "voice");
      c.turns = next.turns;
    }
  };
  run().catch(() => onLine({ role: "keeper", text: "연결이 잠시 끊겼어요. 끊고 이야기 탭에서 이어 가 주세요." }));
  const t0 = performance.now();
  return {
    // 0~1: 말하는 쪽 소리 크기. 실제 엔진은 들리는 소리(출력) · 마이크(입력) 크기를 준다
    level: () => {
      const t = (performance.now() - t0) / 1000;
      if (mode === "speaking") return .45 + .35 * Math.abs(Math.sin(t * 7.3) * Math.sin(t * 2.1));
      return talking && !muted ? .2 + .3 * Math.abs(Math.sin(t * 9.1) * Math.cos(t * 3.7)) : .04 + .03 * Math.sin(t * 2);
    },
    mute: (m) => { muted = m; },
    end: () => { over = true; },
  };
}

// 말 걸어 오는 소리(2026-11-03 동규 「소리도 같이」): 파일 없이 웹 오디오로, 우주가 다가온 뒤 3초마다 부드러운 두 음.
// 휴대폰은 사람이 화면을 누르기 전엔 소리를 막을 수 있어, 막혔으면 첫 손길에 시작한다(그림은 늘 나옴)
const RING_AT = 2.2, RING_EVERY = 3;
function ringSound() {
  const AC = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!AC) return () => {};
  const ctx = new AC();
  const tone = (at: number, f0: number, f1: number, dur: number, vol: number) => {
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.setValueAtTime(f0, at);
    o.frequency.exponentialRampToValueAtTime(f1, at + dur * .7);
    g.gain.setValueAtTime(.0001, at);
    g.gain.exponentialRampToValueAtTime(vol, at + .012);
    g.gain.exponentialRampToValueAtTime(.0001, at + dur);
    o.connect(g).connect(ctx.destination);
    o.start(at); o.stop(at + dur + .05);
  };
  let timer = 0, started = false;
  const t0 = performance.now();
  const start = () => {
    if (started || ctx.state !== "running") return;
    started = true;
    const late = (performance.now() - t0) / 1000;
    let n = 0;
    const chime = () => { const at = ctx.currentTime + .05; tone(at, 1319, 1319, .5, .12); tone(at + .22, 1047, 1047, .7, .12); n++; };
    timer = window.setTimeout(function loop() { if (n < 12) { chime(); timer = window.setTimeout(loop, RING_EVERY * 1000); } },
      Math.max(0, RING_AT - late) * 1000);
  };
  const touch = () => { ctx.resume().then(start, () => {}); };
  if (ctx.state === "running") start();
  else { ctx.resume().then(start, () => {}); document.addEventListener("pointerdown", touch, { once: true }); }
  return () => { clearTimeout(timer); document.removeEventListener("pointerdown", touch); ctx.close().catch(() => {}); };
}

async function voiceEngine({ onLine, onMode }: Hooks, onGone: () => void): Promise<Engine> {
  const { Conversation } = await import("@elevenlabs/client");   // 받기를 누를 때만 받는다(다른 화면은 가볍게)
  const s = await startCall();
  let mode: Mode = "speaking";
  const conv = await Conversation.startSession({
    conversationToken: s.conversation_token, connectionType: "webrtc",
    dynamicVariables: { first_line: s.first_line },          // 에이전트 첫 말 = 이야기 대화의 별지기 첫 말
    customLlmExtraBody: { call_token: s.call_token },        // ElevenLabs → 우리 서버로 올 때 이 대화 · 이 사람을 알아보는 표
    onMessage: (m) => onLine({ role: m.source === "ai" ? "keeper" : "me", text: m.message }),
    onModeChange: ({ mode: m }) => { mode = m; onMode(m); },
    onDisconnect: onGone,
  });
  return {
    level: () => (mode === "speaking" ? conv.getOutputVolume() : conv.getInputVolume()),
    mute: (m) => conv.setMicMuted(m),
    end: () => { conv.endSession().catch(() => {}); },
  };
}

// 대본에 되풀이된 말은 문맥을 보고 하나로(서버 chat_graph.unique_said 와 같은 규칙): 같은 사람이 사이에 다른 말 없이 같은 말 ·
// 앞 말의 조각을 이어 하면(받아쓰기 겹침 · 끊겨 들어온 앞부분) 하나로 두고 긴 쪽을 남긴다. 사이에 다른 사람 말이 있으면 다른 문맥이라 둘 다 둔다
const key = (t: string) => t.replace(/[\s.,!?~…·'"]/g, "");
const addLine = (xs: Line[], l: Line): Line[] => {
  const last = xs.at(-1), k = key(l.text);
  if (!k) return xs;
  if (last && last.role === l.role) {
    if (key(last.text).includes(k)) return xs;
    if (k.includes(key(last.text))) return [...xs.slice(0, -1), l];
  }
  return [...xs, l];
};

const clock = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

export default function CallPage() {
  const name = useKeeperName();
  const router = useRouter();
  const [stage, setStage] = useState<"ring" | "live" | "ended">("ring");
  const [lines, setLines] = useState<Line[]>([]);
  const [mode, setMode] = useState<Mode>("listening");
  const [muted, setMuted] = useState(false);
  const [sec, setSec] = useState(0);
  const engine = useRef<Engine | null>(null);
  const now = useRef<{ stage: NebulaState["stage"]; mode: Mode }>({ stage: "ring", mode: "listening" });
  now.current = { stage, mode };
  const read = useCallback((): NebulaState => ({ ...now.current, v: engine.current?.level() ?? 0 }), []);   // 성운이 매 화면 읽는다
  const [uni] = useLoad(getUniverse);
  const [me] = useLoad(getMe);

  useEffect(() => {
    if (stage !== "live") return;
    const timer = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(timer);
  }, [stage]);
  // 화면을 떠나거나 앱을 닫으면 대화도 끊는다(끊기를 안 눌러도 소리가 이어지지 않게)
  useEffect(() => {
    const off = () => engine.current?.end();
    addEventListener("pagehide", off);
    return () => { removeEventListener("pagehide", off); off(); };
  }, []);
  useEffect(() => (stage === "ring" ? ringSound() : undefined), [stage]);

  const [err, setErr] = useState("");
  const [connecting, setConnecting] = useState(false);
  const answer = async () => {
    if (connecting || engine.current) return;   // 연결되는 몇 초 사이 여러 번 눌러 대화가 겹쳐 열리던 것(2026-11-03 휴대폰 시험: 3개가 동시에)
    const hooks: Hooks = { onLine: (l) => setLines((x) => addLine(x, l)), onMode: setMode };
    if (MOCK) { setStage("live"); engine.current = demoEngine(hooks); return; }
    setErr(""); setConnecting(true);
    try {
      engine.current = await voiceEngine(hooks, () => setStage((s) => (s === "live" ? "ended" : s)));   // 저쪽에서 끊겨도 대본으로
      setStage("live");
    } catch (e) {
      setErr((e as Error)?.name === "NotAllowedError" ? "마이크를 쓸 수 있게 허락해 주세요. 휴대폰 설정에서 이 앱의 마이크를 켤 수 있어요."
        : why(e, "지금은 목소리로 이야기할 수 없어요. 잠시 뒤 다시 받거나, 이야기 탭에서 글로 이야기해 주세요."));
    } finally {
      setConnecting(false);
    }
  };
  const hangUp = () => { engine.current?.end(); setStage("ended"); };
  const last = lines.at(-1);

  return (
    <div className={`call ${stage}`} role="dialog" aria-modal="true" aria-label={`${name}와 대화`}>
      <CallCosmos data={uni} theme={me?.settings.theme} dim={stage === "ring" ? .15 : stage === "live" ? .5 : .75} />
      <CallNebula read={read} grown={lines.filter((l) => l.role === "me").length} />
      {stage === "ring" && (
        <>
          <div className="call-top"><p className="call-cap">나의 우주</p><h1>{name}</h1><p className="sub">오늘 이야기를 들으러 왔어요</p></div>
          <div className="call-acts">
            <Link className="call-btn off" href="/" aria-label="나중에"><Icon name="phone" /></Link>
            <button className="call-btn on" onClick={answer} disabled={connecting} aria-label={connecting ? "연결하는 중" : "받기"}><Icon name="phone" /></button>
          </div>
          <div className="call-acts-names" aria-hidden><span>나중에</span><span>{connecting ? "연결하는 중…" : "받기"}</span></div>
          {err && <p className="call-err" role="alert">{err}</p>}
        </>
      )}
      {stage === "live" && (
        <>
          <div className="call-top"><h1>{name}</h1><p className="call-time" aria-label="대화 시간">{clock(sec)}</p></div>
          <div className="call-space" data-mode={mode} aria-hidden />
          <p className="call-state" role="status">{mode === "speaking" ? `${name}가 말하고 있어요` : muted ? "마이크가 꺼져 있어요" : "듣고 있어요 · 편하게 말해 주세요"}</p>
          <p className="call-caption" aria-live="polite">{last ? last.text : ""}</p>
          <div className="call-acts">
            <button className="call-btn mute" aria-pressed={muted} onClick={() => { engine.current?.mute(!muted); setMuted(!muted); }}
              aria-label={muted ? "마이크 켜기" : "마이크 끄기"}><Icon name={muted ? "micOff" : "mic"} /></button>
            <button className="call-btn off" onClick={hangUp} aria-label="끊기"><Icon name="phone" /></button>
          </div>
        </>
      )}
      {stage === "ended" && (
        <>
          <div className="call-top"><h1>대화가 끝났어요</h1><p className="sub">{lines.some((l) => l.role === "me") ? "오늘 이야기로 별 하나가 생겼어요" : "다음에 또 이야기해요"} · {clock(sec)}</p></div>
          <ol className="call-script" aria-label="대화 대본">
            {lines.map((l, i) => (
              <li key={i} className={l.role}><span className="who">{l.role === "keeper" ? name : "나"}</span><p>{l.text}</p></li>
            ))}
          </ol>
          <div className="call-end">
            {lines.some((l) => l.role === "me")
              ? <button className="primary wide" onClick={() => router.push("/?finish")}>일기로 정리하기</button>
              : <p className="sub">아직 나눈 이야기가 없어서 일기로 정리할 게 없어요.</p>}
            <Link className="btn wide" href="/">닫기</Link>
          </div>
        </>
      )}
    </div>
  );
}
