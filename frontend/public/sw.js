// 캐시 정책을 바꿨으므로 버전을 올려 기존 캐시를 무효화합니다.
const CACHE_NAME = "spendwise-v2";
const CORE_ASSETS = ["/", "/index.html", "/manifest.webmanifest"];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(CORE_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  if (event.request.method !== "GET") return;

  const url = new URL(event.request.url);
  // 백엔드 API 등 다른 출처 요청은 SW가 개입하지 않습니다 (지출 데이터가 캐시에 남으면 안 됨).
  if (url.origin !== self.location.origin) return;

  // 배포 환경에선 API가 같은 출처(/api 프록시)로 들어오므로 여기도 캐시 대상에서 제외합니다.
  // /static(영수증 이미지)도 항상 서버에서 — 캐시가 쌓이면 저장공간만 차지합니다.
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/static/")) return;

  // 페이지 진입(내비게이션)은 network-first:
  // 배포 후에도 항상 최신 index.html을 받고, 오프라인일 때만 캐시로 대체합니다.
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const cloned = response.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put("/index.html", cloned));
          return response;
        })
        .catch(() => caches.match("/index.html"))
    );
    return;
  }

  // 정적 자산(JS/CSS/이미지)은 파일명에 해시가 붙어 내용이 불변이므로 cache-first가 안전합니다.
  event.respondWith(
    caches.match(event.request).then((cached) => {
      if (cached) return cached;
      return fetch(event.request).then((response) => {
        const cloned = response.clone();
        caches.open(CACHE_NAME).then((cache) => cache.put(event.request, cloned));
        return response;
      });
    })
  );
});
