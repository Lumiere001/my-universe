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
