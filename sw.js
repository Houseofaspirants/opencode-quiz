/* ============================================================================
 * sw.js | Service Worker - offline support (PWA)
 * ----------------------------------------------------------------------------
 * Strategy: the network is always the truth, the cache is only for offline.
 *   • HTML pages                     → network-first, cached copy offline
 *   • data/, questions/, JS, CSS     → network-first (ETag revalidated),
 *                                      cached copy offline; 404 evicts it
 *   • content/*.pdf downloads        → never cached here (browser HTTP cache)
 *
 * Bump VERSION whenever core assets change: scripts/clean-links.mjs stamps
 * every page's JS/CSS URLs with ?v=<that number>, so the bump alone makes a
 * returning visitor's first page view load the new files. install calls
 * skipWaiting() and activate clients.claim(), so the new worker takes over
 * that same visit; nothing reloads the page, so there is no reload loop.
 * ========================================================================== */
const VERSION = "hoa-v102";
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
  "./editorial-policy.html",
  "./articles.html",
  "./faq.html",
  "./punjab-exams.html",
  "./punjab-police-exam-preparation.html",
  "./punjab-gk-study-guide.html",
  "./current-affairs-preparation.html",
  "./reasoning-quant-preparation.html",
  /* content hubs (Markdown-built, static) */
  "./study-notes.html",
  "./current-affairs.html",
  "./magazine.html",
  "./strategy.html",
  "./live-sessions.html",
  "./recruitment.html",
  "./blogs.html",
  "./news.html",
  "./announcements.html",
  "./archives.html",
  "./pdfs.html",
  "./expected-mcqs.html",
  "./previous-year-questions.html",
  /* Phase 4 - the six new collections plus the generated search page */
  "./personal-notes.html",
  "./subject-guides.html",
  "./topic-guides.html",
  "./daily-practice.html",
  "./success-stories.html",
  "./book-recommendations.html",
  "./search.html",
  /* Practice + shelf destinations (hand-written, config-driven content) */
  "./books.html",
  "./revision.html",
  "./pyq.html",
  /* Learning-first module roots (Study, Practice, Rank 2 Blueprint) */
  "./study.html",
  "./study-material.html",
  "./practice.html",
  "./rank-2-blueprint.html",
  "./assets/css/style.css",
  "./assets/css/quiz.css",
  "./assets/css/leaderboard.css",
  "./assets/js/core.js",
  "./assets/js/auth.js",
  "./assets/js/content.js",
  "./assets/js/pdf-reader.js",
  "./assets/js/gamification.js",
  "./assets/js/leaderboard-api.js",
  "./assets/js/home.js",
  "./assets/js/subject.js",
  "./assets/js/related.js",
  "./assets/js/di-chart.js",
  "./assets/js/quiz.js",
  "./assets/js/result.js",
  "./assets/js/mock.js",
  "./assets/js/bookmarks.js",
  "./assets/js/leaderboard.js",
  "./assets/js/dashboard.js",
  "./assets/js/contact.js",
  "./assets/js/books.js",
  "./assets/js/revision.js",
  "./assets/js/pyq.js",
  "./assets/js/proof.js",
  "./assets/js/study.js",
  "./assets/js/practice.js",
  "./assets/js/rank2.js",
  "./data/books.json",
  "./data/study-manifest.json",
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
/**
 * Fetches `req` past the browser's HTTP cache (an ETag revalidation, so an
 * unchanged file costs a 304, not a download) and keeps the cache in step with
 * the server: a good answer replaces the stored copy, and a 404/410 deletes it,
 * so a removed quiz or document stops being served instead of living on here.
 */
function fresh(req, cacheName) {
  let live = req;
  try {
    live = new Request(req, { cache: "no-cache" });
  } catch (_) {
    // e.g. an only-if-cached request: send it as it came
  }
  return fetch(live).then((res) => {
    if (res.ok && res.type === "basic") {
      const copy = res.clone();
      caches.open(cacheName).then((c) => c.put(req, copy));
    } else if (res.status === 404 || res.status === 410) {
      caches.keys().then((keys) => keys.forEach((k) => caches.open(k).then((c) => c.delete(req))));
    }
    return res;
  });
}

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;
  if (req.headers.has("range")) return; // media seeking: leave to the browser

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // never touch CDNs / fonts

  /* 0. Hosted documents (the PDFs behind content/<collection>/*.pdf) are
        multi-megabyte downloads: let the browser's own HTTP cache handle
        them instead of pinning them in the shell or data cache forever. */
  if (url.pathname.toLowerCase().endsWith(".pdf")) return;

  /* 1. HTML pages: network first, cache fallback, offline shell last */
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          if (res.ok && res.type === "basic") {
            const copy = res.clone();
            caches.open(SHELL).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(async () =>
          (await caches.match(req)) ||
          (await caches.match(req, { ignoreSearch: true })) ||
          (await caches.match("./index.html")) ||
          Response.error()
        )
    );
    return;
  }

  /* 2. Everything else - data/*.json inventories, questions/*.json, JS, CSS,
        images: network first, cache only as the offline fallback. Serving the
        cached copy first is what made added MCQs, content and documents
        invisible (and deleted ones linger) until a second or third reload. */
  const bucket =
    url.pathname.includes("/data/") || url.pathname.includes("/questions/") ? DATA : SHELL;
  /* Pages ask for JS/CSS as "?v=<VERSION>" (scripts/clean-links.mjs), so a
     release changes every asset URL. Offline, the precached unversioned copy
     still answers that request (ignoreSearch). */
  event.respondWith(
    fresh(req, bucket).catch(async () =>
      (await caches.match(req)) ||
      (await caches.match(req, { ignoreSearch: true })) ||
      Response.error())
  );
});
