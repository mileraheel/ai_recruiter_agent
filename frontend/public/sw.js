// Minimal service worker: enables "Add to Home Screen" installability
// (required on iOS Safari for Web Push to work at all) and handles
// incoming push events + notification clicks. No offline caching here
// deliberately -- this is a live data app, not a content site; stale
// cached data would be actively misleading (approval queues, job
// statuses) so we don't cache anything.

self.addEventListener("install", (event) => {
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("push", (event) => {
  let data = { title: "AI Recruiter Agent", body: "", url: "/" };
  try {
    data = { ...data, ...event.data.json() };
  } catch {
    // non-JSON payload -- fall back to defaults above
  }

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
      icon: "/icon-192.png",
      data: { url: data.url },
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const targetUrl = event.notification.data?.url || "/";

  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && "focus" in client) {
          client.navigate(targetUrl);
          return client.focus();
        }
      }
      return self.clients.openWindow(targetUrl);
    })
  );
});
