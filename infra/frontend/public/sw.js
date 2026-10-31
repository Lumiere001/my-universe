// 설치형 웹앱 서비스 워커. 설치 조건을 채우는 최소한만 한다.
// 캐시에 두는 것은 오프라인 안내 화면 하나뿐이다. 일기 · API 응답 · 화면 파일은 캐시하지 않는다(개인정보 — tests/test_frontend_pwa.py · e2e-landing 이 지킴).
// 화면 이동(navigate)만 받아 네트워크로 보내고, 연결이 없을 때만 안내 화면을 보여 준다. 그 밖의 요청(API · SSE · 그림)은 건드리지 않는다.
const CACHE = "offline-v3";   // 오프라인 화면을 바꾸면 올린다(설치한 앱이 새 화면을 받게)
const OFFLINE = "/offline.html";

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.add(OFFLINE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((ks) => Promise.all(ks.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => caches.match(OFFLINE)));
});

// 고른 시각 알림(PRD v9 Q8): 서버가 보낸 한 줄(일기 내용 없음)을 띄우고, 누르면 이야기 화면을 연다(이미 열려 있으면 그 창으로)
self.addEventListener("push", (e) => {
  let d = { title: "나의 우주", body: "오늘 하루는 어땠어요?", url: "/" };
  try { d = { ...d, ...e.data.json() }; } catch { /* 글만 오면 기본 문장 */ }
  e.waitUntil(self.registration.showNotification(d.title, { body: d.body, icon: "/icons/icon-192.png", badge: "/icons/icon-192.png", data: { url: d.url } }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = (e.notification.data && e.notification.data.url) || "/";
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ws) => {
    const w = ws.find((x) => new URL(x.url).origin === self.location.origin);
    return w ? w.focus().then((x) => x.navigate(url)) : self.clients.openWindow(url);
  }));
});
