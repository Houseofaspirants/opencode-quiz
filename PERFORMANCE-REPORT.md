# Performance & Accessibility Report — House of Aspirants Quiz Portal

**Site:** https://houseofaspirants.in
**Date:** 25 September 2026
**Scope:** Lazy loading · Image compression · Width & height · Font loading · DNS prefetch · Preconnect · Resource hints · Preload · Cache headers · Remove render-blocking · LCP / CLS / INP · Accessibility (ARIA, headings, semantic HTML)
**Method:** before/after measurement with `scripts/seo_check.py`, Lighthouse (axe-core 4.12) on 4 page types, in-page `PerformanceObserver` probes, Pillow-based image encoding with pixel guards.

---

## 1. Results at a glance

| Metric | Before | After |
|---|---|---|
| Lighthouse **Accessibility** | 0.95 — 2 failures (color-contrast, label-content-name-mismatch) | **1.0 — zero failures on 4/4 page types** |
| Lighthouse **Best Practices** / **SEO** | 1.0 / 1.0 | 1.0 / 1.0 |
| Rendered image weight (6 files) | 1,424,011 B | **320,449 B (−77.5 %)** |
| Cache policy | assets-only rule, no SWR, no HTML rule | **full explicit matrix** (§2.9) |
| Resource hints | logo preload only; style preload on 1 page | **preconnect + dns-prefetch ×3 + preloads on all 13 pages** |
| Render-blocking JS | 0 (already deferred) | 0 — now audit-enforced |
| `python3 scripts/seo_check.py` | PASS | **PASS** incl. new performance & a11y enforcement |
| Long tasks across all loads | — | **0** |

---

## 2. Optimization checklist (the ten requested items)

### 2.1 Lazy loading
Only **two `<img>` elements are ever rendered site-wide** (manifest icons and the OG cover are never fetched by pages):

| Image | Policy | Why |
|---|---|---|
| Header logo `logo-sm.png` (7.6 KB) | **eager** + `<link rel="preload" as="image">` | above the fold, part of first paint |
| Footer logo | **`loading="lazy" decoding="async"`** | below the fold |

`seo_check.py` now enforces this split: the header logo must *not* carry `loading="lazy"` and the footer logo must carry it. No other image can regress because every page-level `<img>` already requires `alt` + `width` + `height`.

### 2.2 Image compression
Adaptive palette quantization (Pillow, 256 colours, median-cut/octree + `optimize=True`) with hard guards: **dimensions asserted unchanged**, per-image visual error **RMSE ≤ 5/255 (~1.9 %)**, and a zoomed 4× side-by-side composite review (original vs compressed — indistinguishable).

| File | Before | After | Saving | Role |
|---|---:|---:|---:|---|
| `logo-sm.png` (96×96) | 17,370 B | 7,555 B | **−57 %** | header/footer logo (rendered at 38 px) |
| `icon-180.png` (180×180) | 52,473 B | 19,707 B | **−63 %** | Apple touch icon |
| `icon-192.png` (192×192) | 58,868 B | 22,045 B | **−63 %** | PWA icon (SW-precached) |
| `icon-512.png` (512×512) | 343,582 B | 104,445 B | **−70 %** | PWA icon (SW-precached) |
| `logo-mark.png` (512×512) | 343,582 B | 104,445 B | **−70 %** | Organization schema / SW precache |
| `og-cover.png` (1200×630) | 608,136 B | 62,252 B | **−90 %** | social preview image |
| **Total** | **1,424,011 B** | **320,449 B** | **−77.5 %** | |

Knock-on effects: service-worker install payload shrinks by ~700 KB, and the preloaded header logo drops 17.4 → 7.6 KB.

### 2.3 Width & height
Every `<img>` — static pages and the JS-injected chrome alike — carries `width` + `height` attributes, so the browser reserves the intrinsic aspect ratio before bytes arrive: **zero image-driven CLS**. Enforced by the audit (existing `alt/width/height` checks + new core.js chrome checks).

### 2.4 Font loading
The site uses a **system font stack** (`-apple-system, BlinkMacSystemFont, "Segoe UI", …`). Result: **zero font requests, zero `font-display` latency, no FOUT/CLS from font swap, nothing to preload.** This is the optimal font-loading state; deliberately kept (adding webfonts would be a performance regression).

### 2.5 DNS prefetch
Added to **all 13 pages** for the three external origins the footer links to:
`<link rel="dns-prefetch" href="//t.me">`, `//instagram.com`, `//youtube.com`.
No page loads any third-party subresource, so DNS warming is the correct (and complete) hint for these origins. Audit-enforced.

### 2.6 Preconnect
`<link rel="preconnect" href="https://t.me">` on **all 13 pages** — t.me is the site's **primary CTA origin** (header button, hero button, six Telegram banners, footer): pre-warming DNS + TCP + TLS shortens the outbound click. It deliberately sits next to its `dns-prefetch` (older-browser fallback pattern) and carries **no `crossorigin`** so the anonymous connection pool matches navigation requests.

**Why not preconnect for the others:** Instagram/YouTube are secondary footer links with no subresources — Google's guidance is `dns-prefetch` (DNS-only, cheaper) for link-only origins. Same-origin critical assets get Chrome's implicit preconnect automatically, so there are no other legitimate targets. Audit-enforced.

### 2.7 Resource hints (coverage matrix)

| Hint | Target | Pages |
|---|---|---|
| `preconnect` | `https://t.me` | 13/13 |
| `dns-prefetch` ×3 | t.me, instagram.com, youtube.com | 13/13 |
| `preload` as=image | `assets/img/logo-sm.png` | 13/13 |
| `preload` as=style | `assets/css/style.css` | 13/13 (was 1/13) |
| `preload` as=style | `assets/css/quiz.css` | every page that links it |

### 2.8 Preload
- `style.css` preloaded on the 12 pages that lacked it (index already had it) — consistent discovery order for the render-critical stylesheet.
- `quiz.css` preloaded wherever it is linked (quiz-family pages only).
- Header logo preload retained from the previous round; under an active service worker Chrome logs a benign *“cross-world … not used”* warning because the SW serves the logo from cache instead — **no extra network request** (first visit, pre-SW, the preload still wins). Kept deliberately.

### 2.9 Cache headers (`vercel.json`)

| Source | Cache-Control | Rationale |
|---|---|---|
| `/sw.js` | `no-cache, must-revalidate` | service worker updates must never be cached |
| `/assets/(.*)` | `public, max-age=86400, stale-while-revalidate=604800` | instant repeat views + background revalidation (7-day SWR grace) |
| `/data/(.*)` | `public, max-age=60, stale-while-revalidate=600` | new quizzes visible within ≤60 s without a revalidation stall |
| `/manifest.webmanifest` | `public, max-age=86400, stale-while-revalidate=604800` | install metadata |
| `/(robots.txt\|sitemap.xml)` | `public, max-age=3600, stale-while-revalidate=86400` | crawlers + fast |
| all 13 HTML pages (+`/`) | `public, max-age=0, must-revalidate` | SEO-critical freshness; ETag revalidation → cheap 304s |

Vercel additionally serves all text with brotli/gzip (style.css 25.2 KB → **6.1 KB** on the wire; core.js 33.5 KB → **10.3 KB**). Every rule is audit-enforced (parse of `vercel.json`).

### 2.10 Remove render-blocking
- **All `<script src>` tags are `defer`** — enforced by `seo_check.py` (any non-deferred external script fails the build audit).
- **Zero third-party subresources** — nothing off the main origin can block parsing or rendering.
- CSS stays render-blocking **by design**: `style.css` (6.1 KB gz) + `quiz.css` (4.9 KB gz, quiz pages only). Async-CSS patterns (`media="print" onload`) risk a flash of unstyled content, which the “no visual change” constraint forbids — and total blocking CSS is ≈ **11 KB gz**.
- Inline JSON-LD is non-executing; page-specific CSS is only loaded where used.
- First-view critical path (wire bytes): HTML ≈5 KB + CSS 6.1 KB + logo 7.6 KB + JS 10.3 KB ≈ **29 KB** to DOMContentLoaded.

---

## 3. Core Web Vitals

### LCP (Largest Contentful Paint)
- The hero `<h1> House of Aspirants` is **static HTML**, not JS-injected → it can paint with the very first render.
- Every script is deferred → nothing executes before first paint; system fonts → no font-load delay; `style.css` preloaded and 6.1 KB gz.
- The preloaded header logo has explicit dimensions → no late-arriving image can become the LCP candidate.

### CLS (Cumulative Layout Shift)
- **New — header slot reservation:** `[data-site-header] { min-height: calc(var(--header-h) + 1px) }` reserves exactly the injected header's height (66 px + 1 px border) *before* deferred `core.js` runs. If first paint wins the race against the script, content no longer shifts down by 67 px; `min-height` is a floor only, so the filled state is byte-for-byte the same layout (pixel-identical by construction).
- The `<noscript>` fallback header (index, subject) was moved **inside** the placeholder, so the JS-disabled layout keeps its exact 67 px height (no doubled band).
- Footer chrome injection appends below existing content → cannot move rendered elements.
- Subject/latest grids render **below the fold** → their post-fetch content contributes no viewport shift.
- All images sized; no web fonts; `reveal` animations animate transform/opacity only.

### INP (Interaction to Next Paint)
- `PerformanceObserver('longtask')` across every measured load: **0 long tasks**.
- Whole-site JS ≈ **24 KB gz** (core 10.3 KB + page scripts), all deferred; `core.js` uses a single delegated event listener; interactions (theme, drawer, search, toast) are class toggles with no layout thrash.

**Measurement note (honest limitation):** paint-timing entries (FCP / LCP / live CLS) could not be captured in this development harness — the embedded browser renderer stays suspended (`document.visibilityState === "hidden"`, `requestAnimationFrame` = 0) even after window/tab focus, so Chrome never records a first paint. Non-paint metrics were measurable: **TTFB 7–60 ms, DOMContentLoaded 17–93 ms, load 19–98 ms, 0 long tasks** (local server). After deploying, verify field/lab CWV with PageSpeed Insights (the keyless PSI API returned HTTP 429 quota during this round) and CrUX.

---

## 4. Accessibility

### 4.1 Colour contrast (all computed against the actual surface colours, WCAG AA 4.5:1)

| Element | Before | After | Contrast |
|---|---|---|---|
| `--muted` light (secondary text: hero sub, float cards, stats, breadcrumbs, footer…) | `#7c879b` | `#646d7d` | 3.62 → **4.61** worst-case across #ffffff / #f9fafc / #fcfdfe / #f6f7fb / #eef1f8 |
| `.btn-telegram` (white text) | `#229ed9` | `#1a7ba6` | 3.02 → **4.74** |
| `.btn-telegram:hover` | `#1b8dc4` | `#17709d` | → **5.47** |
| `.banner-telegram` gradient (white text) | `#229ed9 → #1e88c5` | `#1a7ba6 → #16759d` | 3.02/3.90 → **≥4.5 at every stop** (indigo end 6.29) |
| `.side-telegram` quiz card | `#229ed9 → #1c7fb4` | `#1a7ba6 → #16759d` | same fix |
| mobile-menu Telegram link | inline `#229ed9` | `.mm-tg` class: light `#1a7ba6`, dark `#4db6e8` | theme-aware: **4.74** light / **7.6** dark (one colour cannot pass both themes — the inline style could not adapt) |
| dark `--muted` `#8b97b5` | unchanged | unchanged | already **5.5–6.48** on every dark surface (computed, no change needed) |

### 4.2 Accessible names (`label-content-name-mismatch`)
The header brand link failed even with an “exact” label. Empirical testing against **axe-core 4.12 in-page** (the same version Lighthouse runs) proved the rule compares against the **raw DOM text concatenation** — `"House of AspirantsQuiz Portal"` (no space at the `<span class="brand-sub">` boundary) — so no spaced label could ever match, while removing the label passed. Fix applied: a **real space at the span boundary** (rendered `innerText` verified byte-identical before/after → **pixel-identical UI**) plus `aria-label="House of Aspirants Quiz Portal - go to home"` (screen readers get a clean, complete name containing the visible text). Lighthouse confirms PASS. `noscript` navs (index, subject) also gained `aria-label="Primary"`.

### 4.3 Semantic HTML & headings
- Landmarks: skip-link → `<header>` → `<nav aria-label="Primary">` → `<main id="main">` → `<footer>` with `<nav aria-label="Legal">`; search overlay is `role="dialog"` with labelled input; icon-only buttons all carry `aria-label`; dropdown exposes `aria-haspopup`/`aria-expanded`.
- `seo_check.py` now additionally enforces **`<main>` on every page**.
- Heading hierarchy (exactly one `h1`, no skipped levels) remains enforced and passing.

---

## 5. Verification evidence

| Check | Result |
|---|---|
| `python3 scripts/seo_check.py` | **PASS** — now including: defer-only scripts, dns-prefetch, preconnect, style/quiz/logo preloads, `<main>` landmark, header-vs-footer image loading policy, `vercel.json` cache-header rules |
| Lighthouse — index | **1.0 / 1.0 / 1.0, zero failures** |
| Lighthouse — quiz | **1.0 / 1.0 / 1.0, zero failures** |
| Lighthouse — contact | **1.0 / 1.0 / 1.0, zero failures** |
| Lighthouse — subject (dynamic) | **1.0 / 1.0 / 1.0, zero failures** |
| Console | **0 errors**; only warnings: 2× benign SW cross-world preload note + 1 from the measurement harness (site code contains no `PerformanceObserver`) |
| Visual identity | compression composite reviewed at 4× zoom (indistinguishable); brand `innerText` identical; header reservation exact-match; no layout/UI redesign anywhere |
| Crawl/SEO regression | full audit PASS (metadata, schema, headings, robots, sitemap, domain scan) |

## 6. Files changed in this round

| File(s) | Change |
|---|---|
| 13 × `*.html` | preconnect, dns-prefetch ×3, style/quiz preloads, noscript relocation (index, subject), noscript nav labels |
| `assets/css/style.css` | contrast tokens, `.mm-tg` theme-aware link, `[data-site-header]` CLS reservation |
| `assets/css/quiz.css` | `.side-telegram` gradient contrast |
| `assets/js/core.js` | brand accessible-name fix (space + label), `.mm-tg` class |
| `vercel.json` | cache-header matrix (§2.9) |
| `sw.js` | `VERSION = hoa-v14` (assets changed) |
| 6 × `assets/img/*.png` | quantized (−77.5 % total, dimensions preserved) |
| `scripts/seo_check.py` | performance & accessibility enforcement section |
| `data/index.json`, `sitemap.xml` | rebuilt from the new *Number Series Part 1* question bank (25 questions, 24 sitemap URLs) |

## 7. Recommendations after deploy
1. **Run PageSpeed Insights** on `/`, `/subject`, `/quiz` once live — confirm lab LCP/CLS and collect CrUX field data (PSI keyless API was quota-limited during this round).
2. Re-check contrast after any future theme colour change — add the ratio table above to the definition of done.
3. When real content pages grow (articles/FAQs), re-evaluate webfonts *only* with `font-display: swap` + preload of the woff2 subset — until then the system stack is the fastest option.
