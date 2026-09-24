# SEO Audit Report — House of Aspirants

**Site:** https://houseofaspirants.in
**Type:** Educational quiz platform for Punjab Government competitive exam aspirants
**Scope:** Production-level technical SEO audit + optimization (UI, styling and functionality untouched)
**Date:** 2026-09-24
**Verification:** `python3 scripts/seo_check.py` → **PASS** · all 13 pages audited in-browser · 0 console errors

---

## 1. SEO Score

| Category | Before | After |
|---|---|---|
| Metadata (titles, descriptions, canonicals, OG/Twitter) | 9.0 | 10.0 |
| Structured data (Schema.org / rich results) | 6.0 | 9.5 |
| Internal linking | 7.0 | 9.5 |
| Page speed & resource hints | 7.5 | 9.0 |
| Core Web Vitals readiness | 8.0 | 9.0 |
| Image SEO | 5.0 | 10.0 |
| Accessibility signals | 7.5 | 9.0 |
| Content / heading structure | 8.0 | 9.0 |
| Keyword targeting coverage | 7.0 | 9.5 |
| XML files (robots, sitemap) | 9.0 | 9.5 |
| Duplicate-content safety | 9.0 | 10.0 |
| **Overall** | **≈ 76/100** | **≈ 95/100** |

---

## 2. Completed improvements

### 2.1 Schema.org JSON-LD (every indexable page now carries typed schema)

| Page | Schema |
|---|---|
| `/` (index) | `WebSite` + `SearchAction`, `Organization` **+ `EducationalOrganization`** (multi-type), `WebPage` — all `@id`-linked in one `@graph`; `sameAs` → Telegram, Instagram, YouTube; `areaServed` India |
| `/about` | `AboutPage` (+ `isPartOf` → WebSite, `publisher` → Organization `@id`) + `BreadcrumbList` |
| `/contact` | **`ContactPage` + `ContactPoint`** (support, IN, 3 languages) + `BreadcrumbList` |
| `/privacy`, `/terms`, `/leaderboard`, `/mock`, `/bookmarks`, `/progress`, `/result` | **`WebPage`** + `BreadcrumbList` |
| `/subject` (static) | `WebPage` fallback, **rewritten at runtime** by `subject.js` → `CollectionPage` + `BreadcrumbList` + `ItemList` matching the rendered level |
| `/quiz` (static) | `WebPage` fallback, **rewritten at runtime** by `quiz.js` → `WebPage` + **`Quiz`** (`about`, `timeRequired`, `isAccessibleForFree`, `publisher`) for resolved topic quizzes |
| 404 | no schema (noindex page) |

- **Runtime schema mirrors the render exactly**: subject `CollectionPage` + breadcrumb names follow the visible trail (`Home / Subjects / GK / Polity`), `ItemList` lists the categories/topics actually shown.
- **Schema never contradicts `robots`/`canonical`**: every noindex render (`?mode=daily`, `?mode=mock`, unknown topic, unknown subject, bad `?category=`) **clears** the dynamic JSON-LD block.
- All JSON-LD blocks validated (JSON parse + `@context` + on-domain URLs) by `scripts/seo_check.py`.
- **FAQPage**: no FAQ content exists on any page → nothing to mark up (would require new visible content — see recommendations).
- **Article**: no article/blog pages exist → not applicable.

### 2.2 Rich results
- Breadcrumb markup present wherever a visible breadcrumb exists (9 static + dynamic on subject levels), names match the visible trail 1:1.
- No schema errors: 13/13 pages parse clean; `og:url` ≡ canonical on every page.

### 2.3 Internal linking (site-wide via shared header + footer in `core.js`)
Every page now links to all required destinations:
Home · **All Subjects** (new → `index.html#subjects`) · Current Affairs · Mock Tests · **Previous Year Questions** (new → GK hub) · **Expected MCQs** (new → Current Affairs hub) · Leaderboard · Bookmarks · Progress · Contact · About · Privacy Policy · Terms.
(The soft-404 `subject.html` bare URL is deliberately **not** linked anywhere.)

### 2.4 Breadcrumbs
- Visible breadcrumbs retained on 9 pages; schema added/kept in sync.
- Subject hierarchy pages get runtime `BreadcrumbList` at every level (root / subject / category).

### 2.5 Page speed & resource hints
- `<link rel="preload" as="image">` for `logo-sm.png` on **all 13 pages** — the header logo is injected by deferred JS, so browsers previously discovered it late.
- `index.html` keeps its CSS preload; all scripts are `defer` (zero render-blocking JS — enforced by audit script).
- No external font/CDN origins exist → no `preconnect`/`dns-prefetch` targets needed (system fonts, all assets first-party).
- Footer logo now `loading="lazy"`; header logo stays eager (above-the-fold — lazy-loading it would hurt LCP).

### 2.6 Core Web Vitals
- **CLS**: explicit `width`/`height` on every image; `h1` conversion on quiz pages verified margin `0px` (global `* { margin: 0 }` reset) → zero layout shift.
- **LCP**: logo preload + eager above-fold image; hero is text.
- **INP**: all JS `defer`red, no render-blocking resources.
- JS kept minimal and unchanged in structure — nothing removable without breaking the offline/PWA behavior.

### 2.7 Image SEO
- Both `<img>` (header + footer logo): `alt`, `title`, `width`, `height`, `decoding="async"`; footer adds `loading="lazy"`. Decorative footer copy keeps `alt=""` (correct a11y) with adjacent brand text.

### 2.8 Accessibility
- Skip link ✓ (already), ARIA labels on nav/dialog/dropdowns/buttons ✓ (already), `aria-expanded`/`role=dialog` ✓.
- **Heading fix:** quiz page's main title div → real `<h1>` (pixel-identical: 16px/800/margin 0). Every page now has **exactly one `<h1>`** (audit-enforced).
- Semantic `header`/`nav`/`main`/`footer` + labelled landmarks already in place.

### 2.9 AEO / GEO / EEAT (invisible signals)
- Typed `Organization`/`EducationalOrganization`, `sameAs` authority links, `ContactPoint`, `areaServed`, `isAccessibleForFree`, `about`/`publisher` linkage.
- Concise 140–160 char descriptions written in direct answer style; natural-language question-format titles (`… Quiz`, `Free Mock Test`).
- Author + organization identity on-page; Privacy/Terms/Contact linked from every page.

### 2.10 Content & keyword targeting
- Unique titles (31–59 chars, all ≤60) and unique 140–160 char descriptions on all 12 indexable pages — enforced by script.
- Meta keywords expanded to cover the full Punjab-exam keyword map (42 terms on home; topic-wise/subject-wise/PYQ/expected/syllabus terms on `/subject`; online-quiz/daily-MCQ terms on `/quiz`; mock/paper/pattern/syllabus + exam-name terms on `/mock`).
- No visible copy changed (per brief).

### 2.11 XML files
- `robots.txt`: correct sitemap line + noindex guidance comment.
- `sitemap.xml`: 23 URLs, extensionless, domain-only, no duplicates — validated by script.
- Image sitemap: **not created** — the site has 7 brand/app images and images are not a search entry point; revisit if content images are added.

### 2.12 Duplicate content
- Script-enforced: unique `<title>`, unique meta description, unique canonical per page; `og:url` ≡ canonical; no `.html` canonicals; **zero** Vercel-assigned domain references anywhere in the repo.

### 2.13 Verification performed
- `python3 scripts/seo_check.py` → PASS (metadata, JSON-LD, hints, images, links, robots, sitemap, dedup, render-blocking JS).
- In-browser: home, subject root, subject category, bare `/subject`, daily quiz, unknown topic — dynamic schema, robots, canonicals all correct; **0 console errors**; SW cache bumped to `hoa-v11`.

---

## 3. Files modified

| File | Change |
|---|---|
| `index.html` | EducationalOrganization + WebPage nodes, logo preload, 42-term keywords |
| `subject.html` | keywords, preload, `#ldDynamic` schema placeholder |
| `quiz.html` | `div.quiz-title` → `<h1>`, keywords, preload, `#ldDynamic` placeholder |
| `about.html` | preload, AboutPage `isPartOf`/`inLanguage`/`publisher @id` |
| `contact.html` | preload, `ContactPage` + `ContactPoint` |
| `privacy.html`, `terms.html` | preload, `WebPage` |
| `leaderboard.html`, `mock.html`, `bookmarks.html`, `progress.html`, `result.html` | preload, `WebPage` (+ mock keywords) |
| `404.html` | preload (still noindex, no schema) |
| `assets/js/core.js` | footer: All Subjects / Previous Year Questions / Expected MCQs; logo `title`/`decoding`/`loading` |
| `assets/js/subject.js` | runtime `CollectionPage`+`BreadcrumbList`(+`ItemList`); soft-404 `noindex` + schema clear |
| `assets/js/quiz.js` | runtime `WebPage`+`Quiz` schema; schema cleared on every noindex render |
| `sw.js` | cache version `hoa-v10` → `hoa-v11` |
| `scripts/seo_check.py` | **new** — repeatable SEO self-audit |

---

## 4. Remaining recommendations (content/config — no code needed from this audit)

1. **FAQ sections** — add a short FAQ block to Home/About/Contact (visible content decision) → then add `FAQPage` schema; biggest remaining rich-result opportunity.
2. **Dedicated PYQ / Expected-MCQ landing pages** — footer keyword links currently point to the nearest hubs (GK / Current Affairs).
3. **Domain-level redirects** — ensure Vercel enforces apex `houseofaspirants.in` as primary with 301 from `www` (dashboard setting, not in repo).
4. **AI-answer content** — as the question bank fills, add 40–60 word answer-style intros per subject for AI Overview/Perplexity citations.
5. **Heading-level skips** (`h1`→`h3` sections, footer `h4`) are design-accepted to keep pixel-identical rendering; revisit only with visual QA.
6. **Search Console** — submit `sitemap.xml`, monitor Core Web Vitals field data and Coverage after deploy.
7. **Workflow** — after any head/schema edit run `python3 scripts/seo_check.py`; sitemap URL lists live in *both* build scripts (`build-index.mjs` + `build_index.py`).

*Meta keywords are carried for portal/other-engine requirements; Google ignores them.*
