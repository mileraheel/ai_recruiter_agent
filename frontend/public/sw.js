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
  // "Role Pace" here is only a last-resort fallback for a malformed/
  // titleless payload -- the real title comes from whatever the
  // backend sends in the push payload itself (see services/push*.py),
  // which is where APP_NAME actually flows from. This file is a
  // static public/ asset (not bundled by Vite), so it can't read
  // VITE_APP_NAME at runtime the way the rest of the app does.
  let data = { title: "Role Pace", body: "", url: "/" };
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
