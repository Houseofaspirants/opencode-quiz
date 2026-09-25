# SEO Report — House of Aspirants

**Site:** https://houseofaspirants.in
**Date:** 2026-09-25
**Scope:** Complete Technical SEO audit & implementation (functionality untouched)
**Verification:** `python3 scripts/seo_check.py` → **PASS** · in-browser pixel checks · **0 console errors**

---

## Task status (10/10)

| # | Task | Status | Evidence |
|---|---|---|---|
| 1 | Replace every old Vercel-domain reference | ✅ Already clean — re-verified | Repo-wide scan (all files, incl. hidden): **0** legacy Vercel-host URLs (neither the project-prefixed nor the bare host form). Remaining "Vercel" mentions are the *platform* (deploy docs, `vercel.json`, package keywords) — not the old domain. |
| 2 | Canonicals, OG, Twitter, manifest, robots.txt, sitemap, JSON-LD, hardcoded links | ✅ Verified all | Canonical = `https://houseofaspirants.in/<path>` (extensionless) on 12 indexable pages, absent on 404; `og:url` ≡ canonical; Twitter cards on all; `manifest.webmanifest` uses relative (on-domain) URLs; `robots.txt` points to the domain sitemap; `sitemap.xml` = 23 domain URLs; JSON-LD on all indexable pages; zero off-domain internal links. |
| 3 | Unique titles < 60 chars | ✅ 13/13 | See inventory below — 31–59 chars, all unique. |
| 4 | Unique descriptions 140–160 chars | ✅ 13/13 | 146–155 chars, all unique. |
| 5 | robots meta tag | ✅ 13/13 | `index, follow` ×12; `noindex` on 404 (runtime `noindex` also on daily/mock/unknown-topic/soft-404 URLs). |
| 6 | Optimize headings H1/H2/H3 | ✅ Done this pass | 33 heading conversions + 5 CSS selector extensions — see §3. Now enforced by the audit script. |
| 7 | Remove duplicate titles | ✅ 0 duplicates | Script-enforced (case-insensitive compare). |
| 8 | Remove duplicate descriptions | ✅ 0 duplicates | Script-enforced. |
| 9 | Favicon references | ✅ 13/13 | `rel=icon` (32px) + `apple-touch-icon` (180px) on **every** page (apple-touch added to 12 pages this pass); manifest supplies 192/512 icons. |
| 10 | SEO report of modified files | ✅ This document | §2 lists every file changed. |

---

## 1. Metadata inventory (tasks 3/4/5/7/8)

| Page | Title (ch) | Desc (ch) | Robots |
|---|---|---|---|
| index | Punjab Police Free MCQ Quiz \| House of Aspirants (48) | 153 | index, follow |
| subject | Topic Wise Quiz & Free MCQ Practice \| House of Aspirants (56) | 154 | index, follow |
| quiz | Punjab Police MCQ Quiz \| House of Aspirants (43) | 150 | index, follow |
| mock | Free Mock Test \| Punjab Police & PSSSB \| House of Aspirants (59) | 155 | index, follow |
| leaderboard | Quiz Leaderboard - Top Rankings \| House of Aspirants (52) | 148 | index, follow |
| bookmarks | My Bookmarked Questions \| House of Aspirants (44) | 149 | index, follow |
| progress | Quiz Progress & Achievements \| House of Aspirants (49) | 148 | index, follow |
| result | Quiz Result & Answer Review \| House of Aspirants (48) | 147 | index, follow |
| about | About House of Aspirants \| Free MCQ Practice Portal (51) | 151 | index, follow |
| contact | Contact Us \| House of Aspirants (31) | 148 | index, follow |
| privacy | Privacy Policy \| House of Aspirants (35) | 146 | index, follow |
| terms | Terms of Use \| House of Aspirants (33) | 154 | index, follow |
| 404 | Page Not Found \| House of Aspirants (35) | 147 | noindex |

## 2. Files modified this pass (21)

| File | Change |
|---|---|
| `terms.html` | 8× section `h3` → `h2` (font-size pinned to the exact h3 clamp) |
| `privacy.html` | 7× section `h3` → `h2` (pinned) + apple-touch-icon |
| `about.html` | 4× `h3` → `h2` (pinned, margins preserved) + apple-touch-icon |
| `contact.html` | 4× `h3` → `h2` (pinned) + apple-touch-icon |
| `mock.html` | 2× `h3` → `h2` (pinned) + apple-touch-icon |
| `result.html` | 2× `h3` → `h2` (pinned; also fixes h3-before-h2 order) + apple-touch-icon |
| `leaderboard.html` | empty-state `h3` → `h2` (pinned size + 8px margin) + apple-touch-icon |
| `bookmarks.html` | empty-state `h3` → `h2` (pinned) + apple-touch-icon |
| `quiz.html` | sidebar `h4` ×2 → `h3` (Question Palette, Telegram) + apple-touch-icon |
| `subject.html`, `progress.html`, `404.html` | apple-touch-icon added |
| `assets/css/style.css` | selectors extended: `.quiz-card h4, .quiz-card h3` · `.footer-col h4, .footer-col h2` |
| `assets/css/quiz.css` | selectors extended: `.palette-card h4, .palette-card h3` · `.side-telegram h4, .side-telegram h3` |
| `assets/js/core.js` | footer column heads `h4` → `h2`; search-result titles `h4` → `h3` |
| `assets/js/subject.js` | card titles `h4` → `h3` (×2) |
| `assets/js/home.js` | fresh-practice card titles `h4` → `h3` |
| `assets/js/result.js` | empty-state `h3` → `h2` (pinned) |
| `sw.js` | cache version `hoa-v11` → `hoa-v12` (JS + CSS changed) |
| `scripts/seo_check.py` | **new checks**: no heading-level skips; favicon + apple-touch on every page |

*(Not modified — already compliant: `index.html` (headings h1→h2, both icons), `manifest.webmanifest`, `robots.txt`, `sitemap.xml`, all JSON-LD.)*

## 3. Heading optimization detail (task 6)

**Before:** 8 pages had `h1 → h3` skips (no `h2`), `result.html` mixed `h3` before `h2`, quiz/subject/home/footer/search used `h4` directly under `h1`/`h2`.

**After (verified in-browser, zero pixel change):**

| What | Was | Now | Pixel guard |
|---|---|---|---|
| Section heads (terms, privacy, about, contact, mock, result) | `h3` | `h2` | inline `font-size:clamp(1.1rem,2.2vw,1.35rem)` = exact h3 rule; measured **17.95px ≡ expected clamp** |
| Empty-state heads (leaderboard, bookmarks, result.js) | `h3` | `h2` | size pinned + `margin-bottom:8px` (replicates `.empty-state h3`) |
| Footer columns | `h4` | `h2` | `.footer-col h2` added to selector → measured 12.48px / uppercase / 0.14em / 14px ≡ old h4 |
| Quiz palette + telegram, search results, subject/home cards | `h4` | `h3` | extended `.quiz-card/.palette-card/.side-telegram` selectors → measured 12.48px & 16px, margins 14/6/3px ≡ old h4 |

**Result:** every page now walks `h1 → h2 → h3 → h2(footer)` with **no skipped levels** — enforced by `seo_check.py` from now on. Accepted exceptions: modal/dialog headings (`Answers locked`, `Submit quiz?`) stay scoped to their overlay context.

## 4. Verification performed

1. `python3 scripts/seo_check.py` → **PASS** (titles, descriptions, dedup, robots, canonicals, OG/Twitter, JSON-LD parse, heading order, favicon+apple-touch, image attrs, resource hints, internal links, robots.txt, sitemap, repo-wide domain scan).
2. In-browser, with HTTP-cache-busted assets: terms (H1→H2×8→H2 footer, 17.95px ≡ clamp), subject (H1→H2→H3×6 cards at 16px/3px), quiz (palette/telegram pixel-identical; daily mode still `noindex` + schema cleared).
3. **0 console errors**; service worker bumped to `hoa-v12`.

## 5. Notes

- Internal links intentionally keep `.html` form (local preview works; Vercel `cleanUrls` 301s them to the extensionless canonical — no duplicate-content impact).
- `manifest.webmanifest` uses relative URLs (resolves to the domain, survives path moves).
- Run `python3 scripts/seo_check.py` after any head/heading edit — it now fails the build on skipped heading levels or missing favicons.

---

## 6. Schema.org implementation & validation (round 4)

**Status:** `python3 scripts/seo_check.py` deep-validates every JSON-LD document → **PASS, 0 errors** · runtime states verified in-browser · **0 console errors** · service worker = `hoa-v13`.

### Type matrix (10 requested)

| # | Schema type | Location | Notes |
|---|---|---|---|
| 1 | `Organization` | `index.html` `@graph` | name / url / logo / sameAs |
| 2 | `EducationalOrganization` | `index.html` — multi-typed with #1 (`["Organization","EducationalOrganization"]`) | one entity node, no duplication |
| 3 | `WebSite` | `index.html` | name / url / `publisher → /#organization` |
| 4 | `SearchAction` | `WebSite.potentialAction` | modern `EntryPoint.urlTemplate` form + `query-input` |
| 5 | `BreadcrumbList` | 8 static pages (one `@graph` each) + runtime `subject.js` | positions 1..n, `@id` cross-linked to the page node |
| 6 | `WebPage` (+ `AboutPage` / `ContactPage`) | every indexable page statically; rewritten at runtime on subject/quiz | required: url, name, description, isPartOf, inLanguage |
| 7 | `CollectionPage` | `subject.js` runtime (subject root + category levels) | `mainEntity: ItemList` of categories/topics |
| 8 | `Quiz` | `quiz.js` runtime when a topic resolves | name / url / description / timeRequired / publisher / isAccessibleForFree; cleared on empty & personal states |
| 9 | `FAQPage` | intentionally **not emitted** | No visible FAQ content exists; Google requires markup to mirror visible content. Decision this round: skip — add together with a real FAQ section later. |
| 10 | `Article` | intentionally **not emitted** | No article/news content exists — same policy; revisit when articles ship. |

### Structural fixes this round

- **One `@graph` document per page.** The 8 pages carrying two separate `<script>` blocks (page node + breadcrumb) were merged into a single document, so `@id` references resolve inside one JSON-LD graph — cross-script `@id` refs are not resolvable per spec (this was the validator's original 16-error finding).
- **Entity linking.** Every page node declares `breadcrumb: {"@id": "<url>#breadcrumb"}`; each `BreadcrumbList` declares the matching `@id`. `isPartOf → /#website` and `publisher → /#organization` resolve to their defining nodes on the home page.
- **SearchAction modernized:** string target → `{"@type":"EntryPoint","urlTemplate":…}` (found nested in `WebSite.potentialAction` in-browser).
- **Node hygiene:** missing `description` added to the static subject/quiz `WebPage`; `ContactPoint.areaServed` `"IN"` → `{"@type":"Country","name":"India"}`; redundant per-node `@context` stripped inside `@graph` (top-level only); preload link between the merged blocks preserved.
- **Runtime parity:** the dynamic `subject.js` graph carries the same `@id` linkage as the static pages.

### What the validator now enforces (`scripts/seo_check.py`)

- JSON parses; `@context` exactly `https://schema.org`
- every `@type` ∈ known-vocabulary whitelist (catches typos such as `Website`)
- required properties per type (`Organization`: name/url/logo · `WebPage`-family: url/name/description/isPartOf · `BreadcrumbList`: itemListElement · `SearchAction`: target + query-input · `EntryPoint`: urlTemplate · `ListItem`: position/name · `Quiz`: name/url/description · `ContactPoint`: contactType …)
- all `@id` references resolve in-document (or to the three known cross-page entities `/#website`, `/#organization`, `/#webpage`)
- `WebPage` ↔ `BreadcrumbList` cross-link equality
- breadcrumb positions contiguous from 1, every crumb named; all `url`/`item`/`urlTemplate` on-domain (template variables stripped) and extensionless
- coverage: `WebPage`-family on all 12 indexable pages · `WebSite` + `SearchAction` + `EntryPoint` + `Organization` + `EducationalOrganization` on home · `BreadcrumbList` on the 8 pages with visible breadcrumbs · 404 carries **zero** schema · `ItemList.numberOfItems` consistency · duplicate-`@id` detection

### Runtime verification (in-browser)

| State | Result |
|---|---|
| `subject?subject=gk` (root) | `CollectionPage` + `ItemList` (6 category items) + 3-crumb `BreadcrumbList`, linkage resolved, `index, follow` — **0 errors** |
| `subject?subject=gk&category=polity` | 4 crumbs (…→ Polity), dynamic title, canonical with `&category=` — **0 errors** |
| `subject?subject=zzz` (unknown) | slot cleared, `noindex, nofollow`, 0 live JSON-LD — **0 errors** |
| `quiz?mode=daily` (personal) | slot cleared, `noindex, nofollow`, 0 live JSON-LD — **0 errors** |
| `index.html` | full `@graph` parses live; `SearchAction`/`EntryPoint` found nested in `WebSite.potentialAction` — **0 errors** |
| Console | **0 errors** |

### Files modified (schema round)

| File | Change |
|---|---|
| `index.html` | `SearchAction` → `EntryPoint` target form |
| `subject.html`, `quiz.html` | static `WebPage.description` added |
| `about/bookmarks/contact/leaderboard/mock/privacy/progress/terms.html` | 2 JSON-LD blocks merged → 1 `@graph` with `@id` linkage; `contact` also `areaServed` → `Country` |
| `assets/js/subject.js` | dynamic breadcrumb `@id` + `WebPage.breadcrumb` linkage |
| `scripts/seo_check.py` | deep schema validator (types/props/@id/positions/coverage) + inventory |
| `sw.js` | `hoa-v12` → `hoa-v13` |
| `SEO-REPORT.md` | this section |

---

## 7. Intelligent internal linking & content hub (round 7)

**Scope:** every page naturally reaches all 13 destinations; new Related
Quizzes / Related Subjects / Related Articles modules; an `/articles` content
hub; improved crawl depth.

### Link graph

| Destination | Where it now links from (every page) |
|---|---|
| Home · Subjects · Current Affairs · Mock Tests · Expected MCQs · Previous Year Questions · Bookmarks · Leaderboard · About · Contact · Privacy · Terms | shared header + footer (`core.js`) — enforced by `seo_check.py` `DESTINATIONS` |
| **Punjab GK** (`subject?subject=gk&category=punjab-gk`) | **new** footer SUBJECTS column, mobile drawer, noscript navs (index/subject) |
| **Study Guides** (`/articles`) | **new** footer Company column, mobile drawer |

Footer keeps its approved targets: *Previous Year Questions* → `subject?subject=gk`,
*Expected MCQs* → `subject?subject=current-affairs` (no thin hub pages). Deeper
in-content links were added instead: mock builder → PYQ/Expected MCQs/Daily
Quiz; quiz page → "More ways to practise" strip; about chips → live subject
pages; leaderboard/progress/bookmarks/contact/privacy/terms/404 each gained a
natural contextual link (`.ilink`, brand + underline — content links have no
default styling because `a { color: inherit }`).

### Content hub — `/articles`

- `articles.html` hub (CollectionPage + ItemList + BreadcrumbList) listing 4
  evergreen guides; each guide is a root-level page with `Article` + `WebPage`
  multi-type `@graph`, visible breadcrumb and full head suite.
- `data/articles.json` — no-code registry (mirrors `subjects.json` pattern):
  title/description/subjects/categories/dates. `build_index.py` **and**
  `build-index.mjs` append every registered guide to `sitemap.xml`
  (**24 → 29 URLs**); `seo_check.py` verifies registry ↔ page metadata sync,
  hub cross-links, sitemap inclusion and valid subjects.
- Evergreen content only — no dates, vacancies or unverifiable claims.

### Related modules (subject pages)

`assets/js/related.js` renders three cards from config, no hardcoding:
**Related subjects** (affinity map — e.g. GK → Current Affairs/Punjab GK first,
then config order), **Related quizzes** (live quizzes, current subject/category
floated up, current quiz excluded), **Related study guides** (registry match by
subject, `categories` score boosted, *narrowest guide ranks first*, fallback to
all). Heading order h2 → h3 preserved.

### What the audit now enforces (`scripts/seo_check.py`)

13 chrome destinations + hub link · chrome placeholders on all 18 pages ·
articles registry integrity & page metadata sync · hub ↔ guide cross-links ·
sitemap coverage (hub + all guides) · `Article` schema on guides,
`CollectionPage` on hub · related-module placeholder + `related.js` wiring ·
`vercel.json` HTML cache rule covers articles pages.

### Verification

`seo_check.py` → **PASS** (29 URLs, Article×4, BreadcrumbList×13) · Lighthouse
1.0/1.0/1.0 on hub, guide, subject · in-browser: 14/14 destinations render,
related cards correct on `gk&category=punjab-gk` and `reasoning` · 0 console
errors.
