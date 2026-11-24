/*
 * analysisACE service worker: shows browser notifications for alerts (D26).
 * It only handles push messages; it does not cache pages.
 */

self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
  let data = {};
  try {
    data = event.data ? event.data.json() : {};
  } catch {
    data = {};
  }
  const title = typeof data.title === "string" ? data.title : "analysisACE";
  event.waitUntil(
    self.registration.showNotification(title, {
      body: typeof data.body === "string" ? data.body : "",
      icon: "/icon-512.png",
      badge: "/icon-512.png",
      data: { url: typeof data.url === "string" ? data.url : "/" },
    }),
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  // Only ever open a page on this site, whatever the message says.
  let target = new URL("/", self.location.origin);
  try {
    const wanted = new URL(event.notification.data && event.notification.data.url, self.location.origin);
    if (wanted.origin === self.location.origin) target = wanted;
  } catch {
    // keep the home page
  }
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
      for (const client of windows) {
        if (client.url === target.href && "focus" in client) return client.focus();
      }
      return self.clients.openWindow(target.href);
    }),
  );
});
