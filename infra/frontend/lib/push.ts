// 고른 시각 알림(PRD v9 Q8): 허락은 '알림 켜기'를 누를 때만 묻는다(거절해도 앱은 그대로). 아이폰은 홈 화면에 추가한 앱에서만 받는다.
// 구독(브라우저 알림 주소 · 키)은 서버에서 암호화해 둔다. 가짜 데이터 모드는 허락 없이 켜진 척만 한다.
import { getPushKey, MOCK, subscribePush, unsubscribePush } from "@/lib/api";

export type PushResult = "on" | "denied" | "unsupported" | "install" | "nokey";
export const TIMES = Array.from({ length: 36 }, (_, i) => `${String(6 + Math.floor(i / 2)).padStart(2, "0")}:${i % 2 ? "30" : "00"}`);   // 06:00 ~ 23:30
export const nowSlot = () => { const d = new Date(); return `${String(d.getHours()).padStart(2, "0")}:${d.getMinutes() < 30 ? "00" : "30"}`; };

const ios = () => /iPhone|iPad|iPod/.test(navigator.userAgent);
const standalone = () => matchMedia("(display-mode: standalone)").matches || !!(navigator as Navigator & { standalone?: boolean }).standalone;
// 아이폰 사파리(홈 화면 앱이 아님)는 웹 알림을 못 받는다 → 홈 화면에 추가 안내
export const needsInstall = () => typeof window !== "undefined" && ios() && !standalone();

const key = (b64: string) => {
  const raw = atob((b64 + "=".repeat((4 - (b64.length % 4)) % 4)).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
};

export async function turnOn(at: string): Promise<PushResult> {
  if (MOCK) { await subscribePush({ endpoint: "https://mock", keys: {}, notify_at: at }); return "on"; }
  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) return needsInstall() ? "install" : "unsupported";
  const { public_key } = await getPushKey();
  if (!public_key) return "nokey";
  if ((await Notification.requestPermission()) !== "granted") return "denied";
  const reg = await navigator.serviceWorker.ready;
  const sub = (await reg.pushManager.getSubscription()) ?? await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: key(public_key) });
  const j = sub.toJSON();
  await subscribePush({ endpoint: j.endpoint!, keys: (j.keys ?? {}) as Record<string, string>, notify_at: at });
  return "on";
}

export async function turnOff() {
  if (!MOCK) await (await navigator.serviceWorker?.ready)?.pushManager.getSubscription().then((s) => s?.unsubscribe());
  await unsubscribePush();
}

export const WHY: Record<Exclude<PushResult, "on">, string> = {
  denied: "알림을 허락하지 않아서 켜지 못했어요. 휴대폰 설정에서 이 앱의 알림을 허락하면 다시 켤 수 있어요.",
  unsupported: "이 브라우저는 알림을 받을 수 없어요.",
  install: "아이폰은 홈 화면에 추가한 앱에서만 알림을 받아요. 아래 방법으로 추가한 뒤 그 앱에서 켜 주세요.",
  nokey: "지금은 알림을 켤 수 없어요(서버 설정이 아직이에요).",
};
