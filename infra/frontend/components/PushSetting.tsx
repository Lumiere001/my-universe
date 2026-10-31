"use client";
// 고른 시각 알림 켜기 · 끄기(PRD v9 Q8 · Q13). 설정에서는 줄 하나, 첫 일기를 저장한 뒤에는 '내일도 이 시간쯤 먼저 말 걸어 드릴까요?' 카드.
// 켰는데 서버에 구독이 없으면(만료로 지워짐) '알림이 꺼졌어요'(이 기기에 켰던 기억만 둔다).
import { useEffect, useState } from "react";
import InstallGuide from "@/components/InstallGuide";
import { listPush, why } from "@/lib/api";
import { needsInstall, nowSlot, TIMES, turnOff, turnOn, WHY, type PushResult } from "@/lib/push";

const WAS_ON = "push-was-on";
const ASKED = "push-asked";   // 첫 일기 뒤 안내를 이 기기에서 이미 보였나
const store = (k: string, v?: string) => { try { if (v === undefined) return localStorage.getItem(k); localStorage.setItem(k, v); } catch { /* 저장소 막힘 */ } return null; };

export function PushRow() {
  const [at, setAt] = useState<string | null>(null);   // 켜진 시각(없으면 꺼짐)
  const [pick, setPick] = useState("21:00");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [install, setInstall] = useState(false);
  useEffect(() => {
    listPush().then((r) => {
      const on = r.subs[0]?.notify_at ?? null;
      setAt(on); if (on) setPick(on);
      if (!on && store(WAS_ON) === "1") setMsg("알림이 꺼졌어요. 다시 켤 수 있어요.");
    }, () => setAt(null));
  }, []);
  const on = async (t: string) => {
    setBusy(true); setMsg(""); setInstall(false);
    try {
      const r: PushResult = await turnOn(t);
      if (r === "on") { setAt(t); store(WAS_ON, "1"); } else { setMsg(WHY[r]); setInstall(r === "install"); }
    } catch (e) { setMsg(why(e, "알림을 켜지 못했어요. 잠시 뒤 다시 눌러 주세요.")); } finally { setBusy(false); }
  };
  const off = async () => {
    setBusy(true); setMsg("");
    try { await turnOff(); setAt(null); store(WAS_ON, "0"); } catch (e) { setMsg(why(e, "알림을 끄지 못했어요.")); } finally { setBusy(false); }
  };
  return (
    <div className="stack" style={{ gap: 6 }}>
      <div className="row" style={{ flexWrap: "nowrap" }}>
        <label htmlFor="push-at" className="sr">알림 시각</label>
        <select id="push-at" value={pick} disabled={busy} style={{ width: "auto" }}
          onChange={(e) => { setPick(e.target.value); if (at) on(e.target.value); }}>
          {TIMES.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        {at ? <button className="small" onClick={off} disabled={busy}>알림 끄기</button>
          : <button className="small primary" onClick={() => on(pick)} disabled={busy}>알림 켜기</button>}
      </div>
      <p className="sub" style={{ margin: 0 }} role="status">{at ? `켜짐 · 매일 ${at}쯤, 그날 일기를 아직 안 썼을 때만` : msg || "꺼져 있어요. 켜면 하루 한 번, 고른 별지기 말투로 먼저 말을 걸어요."}</p>
      {at && msg && <p className="sub" style={{ margin: 0 }}>{msg}</p>}
      {(install || (!at && needsInstall())) && <InstallGuide />}
    </div>
  );
}

// 첫 일기 저장 뒤 한 번(Q13): 가치를 한 번 느낀 뒤에 묻는다
export function PushAsk({ first }: { first: boolean }) {
  const [show, setShow] = useState(false);
  const [done, setDone] = useState("");
  useEffect(() => {
    if (!first || store(ASKED) === "1") return;
    listPush().then((r) => setShow(!r.subs.length), () => setShow(false));
  }, [first]);
  if (!show) return null;
  const later = () => { store(ASKED, "1"); setShow(false); };
  const yes = async () => {
    store(ASKED, "1");
    const t = nowSlot();
    try {
      const r = await turnOn(t);
      if (r === "on") { store(WAS_ON, "1"); setDone(`좋아요. 내일 ${t}쯤 먼저 말 걸게요. 시각은 설정에서 바꿀 수 있어요.`); }
      else setDone(WHY[r]);
    } catch (e) { setDone(why(e, "알림을 켜지 못했어요. 설정에서 다시 켤 수 있어요.")); }
  };
  return (
    <div className="card stack check-card" aria-label="알림 켜기" data-testid="push-ask">
      {done ? <p style={{ margin: 0 }}>{done}</p> : (<>
        <b>내일도 이 시간쯤 먼저 말 걸어 드릴까요?</b>
        <p className="sub" style={{ margin: 0 }}>하루 한 번, 그날 일기를 아직 안 썼을 때만 보내요. 잠금 화면에는 일기 내용을 넣지 않아요.</p>
        <div className="row">
          <button className="small primary" onClick={yes}>알림 켜기</button>
          <button className="small link" onClick={later}>나중에</button>
        </div>
        {needsInstall() && <InstallGuide />}
      </>)}
    </div>
  );
}
