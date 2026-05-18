// ─────────────────────────────────────────────
// AnimaShorts Service Worker  v3
// Strategy:
//   HTML pages      → Network first (always get fresh chunk hashes)
//   /_next/static/  → Network only  (Next.js sets immutable cache headers itself)
//   Icons/manifest  → Cache first   (truly static, never change between deploys)
//   API / outputs   → Network only  (never cache dynamic data)
// Bumping CACHE_NAME forces old workers to delete their stale caches.
// ─────────────────────────────────────────────
const CACHE_NAME = "animashorts-v3";
const PRECACHE = ["/icon-192.png", "/icon-512.png", "/manifest.json"];

// ── Install: pre-cache only the stable static assets ──────────────────────
self.addEventListener("install", (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then((c) => c.addAll(PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: delete ALL old caches ───────────────────────────────────────
self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => {
          console.log("[SW] deleting old cache:", k);
          return caches.delete(k);
        })
      ))
      .then(() => self.clients.claim())
  );
});

// ── Fetch ──────────────────────────────────────────────────────────────────
self.addEventListener("fetch", (e) => {
  const { request } = e;
  const url = new URL(request.url);

  // 1. Non-GET → always pass through
  if (request.method !== "GET") return;

  // 2. API, video stream, outputs → network only, no caching
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/outputs/")
  ) {
    e.respondWith(fetch(request));
    return;
  }

  // 3. Next.js static chunks — network only (Next.js already sets
  //    Cache-Control: public, max-age=31536000, immutable on these)
  if (url.pathname.startsWith("/_next/")) {
    e.respondWith(fetch(request));
    return;
  }

  // 4. HTML pages (/, /generate/, /gallery/) — network first so the browser
  //    always gets fresh HTML with up-to-date chunk hashes after a redeploy.
  //    Fall back to cache only if completely offline.
  if (
    request.headers.get("accept")?.includes("text/html") ||
    url.pathname === "/" ||
    url.pathname.endsWith("/")
  ) {
    e.respondWith(
      fetch(request)
        .then((res) => {
          // Update cache with fresh HTML
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
          return res;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // 5. Stable static assets (icons, manifest, splash images) — cache first
  e.respondWith(
    caches.match(request).then((cached) => {
      if (cached) return cached;
      return fetch(request).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((c) => c.put(request, clone));
        }
        return res;
      });
    })
  );
});

// ── Background job watcher ─────────────────────────────────────────────────
self.addEventListener("message", (e) => {
  if (e.data?.type === "WATCH_JOB") {
    watchJob(e.data.jobId, e.data.apiBase);
  }
});

async function watchJob(jobId, apiBase) {
  const MAX = 120;
  let tries = 0;
  while (tries < MAX) {
    await sleep(3000);
    tries++;
    try {
      const res = await fetch(`${apiBase}/api/jobs/${jobId}`);
      if (!res.ok) continue;
      const job = await res.json();
      if (job.step === "done") {
        self.registration.showNotification("AnimaShorts AI", {
          body: "Your video is ready! Tap to view.",
          icon: "/icon-192.png",
          badge: "/icon-192.png",
          data: { url: `/generate/?id=${jobId}` },
        });
        return;
      }
      if (job.step === "error") {
        self.registration.showNotification("AnimaShorts AI", {
          body: "Video generation failed. Tap to retry.",
          icon: "/icon-192.png",
          data: { url: "/" },
        });
        return;
      }
    } catch (_) {}
  }
}

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = e.notification.data?.url || "/";
  e.waitUntil(
    clients.matchAll({ type: "window" }).then((cs) => {
      const existing = cs.find((c) => c.url.includes(self.location.origin));
      if (existing) { existing.focus(); existing.navigate(url); }
      else clients.openWindow(url);
    })
  );
});

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
