/* ============================================================================
 * sw.js | Service Worker - offline support (PWA)
 * ----------------------------------------------------------------------------
 * Strategy:
 *   • App shell (HTML/CSS/JS/icons)  → cache-first, updated in background
 *   • data/index.json                → network-first (fresh stats), cached copy
 *   • question JSON files            → cache-first (quizzes work offline)
 *   • Everything else                → network with cache fallback
 *
 * Bump VERSION whenever core assets change.
 * ========================================================================== */
const VERSION = "hoa-v5";
const SHELL = `${VERSION}-shell`;
const DATA = `${VERSION}-data`;

const SHELL_FILES = [
  "./",
  "./index.html",
  "./subject.html",
  "./quiz.html",
  "./result.html",
  "./mock.html",
  "./bookmarks.html",
  "./leaderboard.html",
  "./progress.html",
  "./about.html",
  "./contact.html",
  "./privacy.html",
  "./terms.html",
  "./assets/css/style.css",
  "./assets/css/quiz.css",
  "./assets/js/core.js",
  "./assets/js/home.js",
  "./assets/js/subject.js",
  "./assets/js/quiz.js",
  "./assets/js/result.js",
  "./assets/js/mock.js",
  "./assets/js/bookmarks.js",
  "./assets/js/leaderboard.js",
  "./assets/js/dashboard.js",
  "./assets/js/contact.js",
  "./assets/img/logo-mark.png",
  "./assets/img/logo-sm.png",
  "./assets/img/favicon-32.png",
  "./assets/img/icon-180.png",
  "./assets/img/icon-192.png",
  "./assets/img/icon-512.png",
  "./manifest.webmanifest",
];

/* ------------------------------------------------------------- INSTALL ---- */
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(SHELL)
      // addAll fails atomically → use individual puts so one 404 can't break install
      .then((cache) =>
        Promise.all(
          SHELL_FILES.map((f) =>
            fetch(f, { cache: "no-cache" })
              .then((r) => (r.ok ? cache.put(f, r) : null))
              .catch(() => null)
          )
        )
      )
      .then(() => self.skipWaiting())
  );
});

/* ---------------------------------------------------------- ACTIVATE ------ */
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys.filter((k) => !k.startsWith(VERSION)).map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

/* -------------------------------------------------------------- FETCH ----- */
self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // never touch CDNs / fonts

  /* 1. HTML pages: network first, cache fallback, offline shell last */
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(SHELL).then((c) => c.put(req, copy));
          return res;
        })
        .catch(async () =>
          (await caches.match(req)) ||
          (await caches.match("./index.html")) ||
          Response.error()
        )
    );
    return;
  }

  /* 2. Manifest index: always try network so new quizzes show up fast */
  if (url.pathname.includes("/data/index.json")) {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(DATA).then((c) => c.put(req, copy));
          return res;
        })
        .catch(async () => (await caches.match(req)) || Response.error())
    );
    return;
  }

  /* 3. Everything else (incl. question JSON): cache-first + background refresh */
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches
              .open(url.pathname.includes("/questions/") ? DATA : SHELL)
              .then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});
