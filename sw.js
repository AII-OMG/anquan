// 离线缓存 Service Worker
// 页面(index.html)网络优先, 断网时回退缓存; 题库JSON缓存优先+后台更新
const CACHE = 'hnsafety-v1';
const CORE = ['./', './index.html', './manifest.webmanifest', './icon-192.png', './icon-512.png', './icon-180.png'];

self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return;

  // 页面: 网络优先, 保证更新及时; 断网回退缓存
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request)
        .then(res => {
          const copy = res.clone();
          e.waitUntil(caches.open(CACHE).then(c => c.put('./index.html', copy)));
          return res;
        })
        .catch(() => caches.match('./index.html'))
    );
    return;
  }

  // 题库JSON: 缓存优先立即返回, 同时后台拉新版本更新缓存
  if (url.pathname.endsWith('.json')) {
    const refresh = fetch(e.request).then(res => {
      if (!res.ok) return res;
      const copy = res.clone();
      return caches.open(CACHE).then(c => c.put(e.request, copy)).then(() => res);
    });
    e.waitUntil(refresh.then(() => {}).catch(() => {}));
    e.respondWith(
      caches.match(e.request).then(cached => cached || refresh.catch(() => cached))
    );
    return;
  }

  // 其他静态资源: 缓存优先
  e.respondWith(
    caches.match(e.request).then(cached => {
      if (cached) return cached;
      return fetch(e.request).then(res => {
        if (res.ok) {
          const copy = res.clone();
          e.waitUntil(caches.open(CACHE).then(c => c.put(e.request, copy)));
        }
        return res;
      });
    })
  );
});
