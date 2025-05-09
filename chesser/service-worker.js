const CACHE_NAME = "chesser-cache";

// const urlsToPrecache = [];

self.addEventListener("install", (event) => {
  // console.log("📦 Installing service worker...");

  // immediately activate after install 🚀
  // consider revisiting this if we ever do more complicated
  // things and don't want different states across tabs
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  // console.log("🚀 Service Worker: Activated");
  event.waitUntil(
    caches
      .keys()
      .then((cacheNames) => {
        return Promise.all(
          cacheNames.map((cache) => {
            if (cache !== CACHE_NAME) {
              console.log("🗑️ Deleting old cache:", cache);
              return caches.delete(cache);
            }
          })
        );
      })
      .then(() => {
        return self.clients.claim(); // 🚀 Take control of all clients immediately
      })
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;

  // Handle static assets (images, css, js)
  if (
    request.destination === "image" ||
    request.destination === "style" ||
    request.destination === "script"
  ) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((networkResponse) => {
          if (!networkResponse || networkResponse.status !== 200) {
            return networkResponse;
          }

          const responseClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => {
            cache.put(request, responseClone);
          });

          return networkResponse;
        });
      })
    );
  }
});
