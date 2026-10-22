"use client";
// 말로 쓰기(WS21): 마이크로 녹음하거나 녹음 파일(m4a · mp3 · wav · webm, 휴대폰 음성 메모)을 올리면 받아써서 onText 로 넘긴다.
// 이야기하기 화면은 대화 턴으로 보내고, 쓰기 화면은 칸에 채운다(주소에 기대지 않는 컴포넌트).
// Vercel 본문 한도(4.5MB): 브라우저가 소리를 풀어 16kHz 모노 WAV 2분 조각(약 3.8MB)으로 나누고(조용한 곳에서 자름) 하나씩
// 보낸 뒤 받아쓴 글을 이어 붙인다. 서버는 조각을 모으지 않고 받아쓴 뒤 바로 버린다(녹음 저장 0).
// 읽어 주기(useReadAloud): 별지기 말을 ElevenLabs 목소리로. 켜고 끔은 이 기기에만 기억(기본 꺼짐).
import { useEffect, useRef, useState } from "react";
import { speak, transcribe, why } from "@/lib/api";

const RATE = 16000, PIECE_S = 120, MAX_RAW = 4 * 1024 * 1024;
const MAX_MIN = 20;   // 입력 검사: 받아쓴 글이 한 번에 보낼 수 있는 8000자를 넘지 않게(한국어 말 약 350자/분)
const ACCEPT = ".m4a,.mp3,.wav,.webm,.ogg,audio/*";

// 녹음 → 16kHz 모노 소리. 이 브라우저가 못 푸는 형식이면 null(4MB 아래면 그대로 보냄).
async function decode(b: Blob): Promise<Float32Array | null> {
  let ctx: OfflineAudioContext;
  try { ctx = new OfflineAudioContext(1, 1, RATE); } catch { ctx = new OfflineAudioContext(1, 1, 44100); }
  let a: AudioBuffer;
  try { a = await ctx.decodeAudioData(await b.arrayBuffer()); } catch { return null; }
  const n = a.length, mono = new Float32Array(n);
  for (let c = 0; c < a.numberOfChannels; c++) {
    const d = a.getChannelData(c);
    for (let i = 0; i < n; i++) mono[i] += d[i] / a.numberOfChannels;
  }
  if (a.sampleRate === RATE) return mono;
  const step = a.sampleRate / RATE, out = new Float32Array(Math.floor(n / step));
  for (let i = 0; i < out.length; i++) {   // 구간 평균으로 줄임(간단한 저역 통과)
    const s = Math.floor(i * step), e = Math.max(s + 1, Math.floor((i + 1) * step));
    let sum = 0;
    for (let j = s; j < e; j++) sum += mono[j];
    out[i] = sum / (e - s);
  }
  return out;
}

export function wav(x: Float32Array): Blob {
  const v = new DataView(new ArrayBuffer(44 + x.length * 2));
  const str = (o: number, t: string) => { for (let i = 0; i < t.length; i++) v.setUint8(o + i, t.charCodeAt(i)); };
  str(0, "RIFF"); v.setUint32(4, 36 + x.length * 2, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true); v.setUint32(24, RATE, true);
  v.setUint32(28, RATE * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true); str(36, "data"); v.setUint32(40, x.length * 2, true);
  for (let i = 0; i < x.length; i++) v.setInt16(44 + i * 2, Math.max(-1, Math.min(1, x[i])) * 0x7fff, true);
  return new Blob([v], { type: "audio/wav" });
}

// 2분마다 자르되 그 앞 5초 안에서 가장 조용한 50ms 에서 자른다(낱말을 가르지 않게). 마지막 조각은 5초 이상.
function pieces(x: Float32Array): Blob[] {
  const out: Blob[] = [], size = PIECE_S * RATE, tail = 5 * RATE, win = RATE / 20;
  let at = 0;
  while (x.length - at > size + tail) {
    let cut = at + size, low = Infinity;
    for (let s = at + size - tail; s + win <= at + size; s += win) {
      let e = 0;
      for (let i = s; i < s + win; i++) e += x[i] * x[i];
      if (e < low) { low = e; cut = s + win / 2; }
    }
    out.push(wav(x.subarray(at, cut)));
    at = cut;
  }
  out.push(wav(x.subarray(at)));
  return out;
}

export default function MicButton({ onText, disabled }: { onText: (text: string) => void; disabled?: boolean }) {
  const [rec, setRec] = useState<MediaRecorder | null>(null);
  const [sec, setSec] = useState(0);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState("");
  const stream = useRef<MediaStream | null>(null);
  useEffect(() => {
    if (!rec) return;
    const t = setInterval(() => setSec((s) => s + 1), 1000);
    return () => clearInterval(t);
  }, [rec]);
  useEffect(() => () => stream.current?.getTracks().forEach((t) => t.stop()), []);   // 화면을 떠나면 마이크를 끈다

  const run = async (blob: Blob) => {
    setErr(""); setBusy("녹음을 살펴보는 중…");
    try {
      const x = await decode(blob);
      let parts: Blob[];
      if (x) {
        if (x.length < RATE / 2) throw new Error("녹음이 너무 짧아요. 조금 더 길게 말해 주세요.");
        if (x.length > MAX_MIN * 60 * RATE) throw new Error(`한 번에 ${MAX_MIN}분까지 받아요. 나눠서 올려 주세요.`);
        parts = pieces(x);
      } else if (blob.size <= MAX_RAW) parts = [blob];
      else throw new Error("이 브라우저에서 열 수 없는 녹음이에요. wav · mp3로 바꾸거나 4MB보다 작게 줄여 올려 주세요.");
      const said: string[] = [];
      for (let i = 0; i < parts.length; i++) {
        setBusy(parts.length > 1 ? `받아쓰는 중 ${i + 1}/${parts.length}…` : "받아쓰는 중…");
        said.push((await transcribe(parts[i]).catch(() => transcribe(parts[i]))).text.trim());   // 조각마다 한 번 다시
      }
      const text = said.filter(Boolean).join(" ");
      if (!text) throw new Error("목소리를 알아듣지 못했어요. 조금 더 크게 다시 말해 주세요.");
      onText(text);
    } catch (e) { setErr(why(e, "받아쓰지 못했어요. 잠시 뒤 다시 해 주세요.")); }
    finally { setBusy(""); }
  };

  const start = async () => {
    setErr("");
    let r: MediaRecorder;
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      r = new MediaRecorder(stream.current);
    } catch {
      stream.current?.getTracks().forEach((t) => t.stop());
      return setErr("마이크를 쓸 수 없어요. 브라우저에서 마이크를 허용하거나 녹음 파일을 올려 주세요.");
    }
    const chunks: Blob[] = [];
    r.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
    r.onstop = () => {
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = null; setRec(null);
      run(new Blob(chunks, { type: r.mimeType }));
    };
    r.start(1000); setSec(0); setRec(r);
  };
  const pick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    e.target.value = "";   // 같은 파일을 다시 골라도 다시 읽게
    if (f) run(f);
  };
  const off = disabled || !!busy;

  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row">
        <button type="button" aria-pressed={!!rec} disabled={off}
          onClick={() => (rec ? rec.stop() : start())}>
          {rec ? `말 마치기 (${Math.floor(sec / 60)}:${String(sec % 60).padStart(2, "0")})` : "말로 하기"}
        </button>
        <label className="btn" style={{ margin: 0, position: "relative", opacity: off || rec ? 0.5 : 1 }}>
          녹음 파일 올리기
          <input type="file" accept={ACCEPT} onChange={pick} disabled={off || !!rec} data-testid="voice-file"
            style={{ position: "absolute", width: 1, height: 1, opacity: 0 }} />
        </label>
      </div>
      <p className="sub" style={{ margin: 0 }}>
        {rec ? "듣고 있어요. 다 말했으면 ‘말 마치기’를 눌러 주세요." : "녹음 파일은 m4a · mp3 · wav · webm을 받아요. 길어도 괜찮아요. 녹음은 받아쓴 뒤 바로 버려요."}
      </p>
      {busy && <p className="sub" role="status" style={{ margin: 0 }}>{busy}</p>}
      {err && <p className="err" role="alert" style={{ margin: 0 }}>{err}</p>}
    </div>
  );
}

// 읽어 주기: on 이면 say(글)이 ElevenLabs 목소리로 읽는다. 아이폰은 사용자가 누른 순간에 한 번 소리를 틀어 둬야 해서
// 켤 때와 이 화면에서 처음 누를 때 조용한 소리로 풀어 둔다(unlock).
export function useReadAloud() {
  const [on, setOn] = useState(false);
  const audio = useRef<HTMLAudioElement | null>(null);
  const opened = useRef(false);
  useEffect(() => { try { setOn(localStorage.getItem("readAloud") === "1"); } catch { /* 저장소를 못 쓰면 꺼짐 */ } }, []);
  const el = () => (audio.current ??= new Audio());
  const unlock = () => {
    if (opened.current) return;
    opened.current = true;
    const a = el();
    a.src = URL.createObjectURL(wav(new Float32Array(RATE / 10)));
    a.play().catch(() => { opened.current = false; });
  };
  const toggle = () => {
    const v = !on;
    setOn(v);
    try { localStorage.setItem("readAloud", v ? "1" : "0"); } catch { /* 이 기기에만 기억 */ }
    if (v) unlock(); else audio.current?.pause();
  };
  const say = async (text?: string | null) => {
    if (!on || !text) return;
    try {
      const a = el(), old = a.src;
      a.src = URL.createObjectURL(await speak(text));
      if (old.startsWith("blob:")) URL.revokeObjectURL(old);
      await a.play();
    } catch { /* 읽어 주기가 안 돼도 글은 화면에 있다 */ }
  };
  return { on, toggle, unlock, say };
}
