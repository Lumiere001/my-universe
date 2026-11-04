"use client";
// 정리가 끝나면 알림(2026-11-04 동규): 정리는 1분쯤 걸려서, 정리 중에 '끝나면 알림 받기'를 누르면(허락은 이때만 묻는다)
// 앱을 닫아도 끝나면 이 기기로 알림 한 줄(일기 내용 없음). 이미 허락한 기기면 단추 없이 바로 맡긴다.
// 알림을 못 받는 곳(카톡 · 인스타그램 안 브라우저, 홈 화면에 없는 아이폰 사파리, 거절)은 앱을 닫아도 정리는 이어진다는 말만(later).
// ponytail: 기록 id 는 초안을 만든 뒤에 와서, 그 전(첫 몇 초)에 앱을 닫으면 알림이 안 간다. 정리는 서버에서 이어진다.
import { useEffect, useState } from "react";
import { inAppName } from "@/components/InstallGuide";
import { MOCK, type DeviceSub } from "@/lib/api";
import { deviceSub, needsInstall, notifyHere } from "@/lib/push";

type State = "ask" | "want" | "on" | "denied" | "none";

export default function DoneNotify({ entryId, later }: { entryId: string | null; later: string }) {
  const [st, setSt] = useState<State>("ask");
  const [sub, setSub] = useState<DeviceSub | null>(null);
  const get = async () => {
    const d = await deviceSub().catch(() => "unsupported" as const);
    if (typeof d === "string") return setSt(d === "denied" ? "denied" : "none");
    setSub(d); setSt("want");
  };
  useEffect(() => {
    if (inAppName() || needsInstall() || !("Notification" in window)) setSt("none");
    else if (MOCK) return;   // 가짜 모드는 허락 창 없이 맡김(헤드리스 크롬은 허락해도 늘 '거절'로 보임)
    else if (Notification.permission === "denied") setSt("denied");
    else if (Notification.permission === "granted") get();   // 이미 허락한 기기: 묻지 않고 맡김
  }, []);
  useEffect(() => {
    if (st === "want" && sub && entryId) notifyHere(entryId, sub).then(() => setSt("on"), () => setSt("none"));
  }, [st, sub, entryId]);

  const line = (t: string) => <p className="sub" style={{ margin: 0 }}>{t}</p>;
  return (
    <div className="done-notify" role="status">
      {st === "ask" && <>{line("정리에 1분쯤 걸려요. 끝나면 알림으로 알려 드릴까요?")}
        <button type="button" className="small" onClick={get}>끝나면 알림 받기</button></>}
      {(st === "want" || st === "on") && line("끝나면 알림으로 알려 드릴게요. 앱을 닫아도 괜찮아요.")}
      {st === "denied" && line(`알림을 허락하지 않아서 알림은 못 보내요. ${later}`)}
      {st === "none" && line(`정리에 1분쯤 걸려요. ${later}`)}
    </div>
  );
}
