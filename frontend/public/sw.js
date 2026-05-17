const CACHE = "animashorts-v1";
const STATIC = ["/", "/gallery/", "/generate/", "/manifest.json", "/icon-192.png", "/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const url = new URL(e.request.url);

  // API and video output — always network, never cache
  if (url.pathname.startsWith("/api/") || url.pathname.startsWith("/outputs/")) {
    e.respondWith(fetch(e.request));
    return;
  }

  // Static assets — cache first, fallback to network
  e.respondWith(
    caches.match(e.request).then((cached) => cached || fetch(e.request).then((res) => {
      if (res.ok && e.request.method === "GET") {
        caches.open(CACHE).then((c) => c.put(e.request, res.clone()));
      }
      return res;
    }))
  );
});

// Background sync: poll job status and notify when done
self.addEventListener("message", (e) => {
  if (e.data?.type === "WATCH_JOB") {
    const { jobId, apiBase } = e.data;
    watchJob(jobId, apiBase);
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
  e.waitUntil(clients.matchAll({ type: "window" }).then((cs) => {
    const c = cs.find((c) => c.url.includes(self.location.origin));
    if (c) { c.focus(); c.navigate(url); }
    else clients.openWindow(url);
  }));
});

function sleep(ms) { return new Promise((r) => setTimeout(r, ms)); }
