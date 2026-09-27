# Implementation Report — Complete Competitive Exam Learning Platform (Architecture)

**Scope:** architecture and production plumbing only. No fake content, no CMS,
no invented facts. Every page in this delivery ships with honest empty states
until real Markdown is written into `content/`.

**Stack:** unchanged — vanilla HTML/CSS/JS, static output at the repo root,
Python standard library for the build (no new dependencies).

---

## 1. Created folders

| Folder | Purpose |
|---|---|
| `content/` | The single content source. Markdown in, HTML out. |
| `content/README.md` | Hard rules: schemas, official-source policy, reserved sections. |
| `content/notes/` | Study notes (`note-*.html` + Punjabi `<slug>.pa.md` editions) |
| `content/magazine/` | Monthly current affairs issues (`magazine-*.html`) |
| `content/strategy/` | Preparation strategy (`strategy-*.html`) |
| `content/sessions/` | Live sessions (`session-*.html`) |
| `content/recruitment/` | Recruitment records (`recruit-*.html`) |
| `content/pdfs/` | PDF records (registry entry on `pdfs.html`, no page) |

Each collection folder contains its own `README.md` with the exact front-matter
schema for that collection (7 READMEs in total).

Generated artefacts: `data/content-manifest.json` (feeds the sitemap and the
SEO gate) and the hub/item HTML files listed below.

---

## 2. Created pages

### Six hubs (live now, empty and honest)

| Page | URL | What it shows today |
|---|---|---|
| `study-notes.html` | `/study-notes` | Hub + the 4 existing study guides cross-linked + "no notes yet" state |
| `magazine.html` | `/magazine` | Archive shell; empty state until the first issue |
| `strategy.html` | `/strategy` | Strategy hub; empty state |
| `live-sessions.html` | `/live-sessions` | Upcoming/previous sessions; empty state |
| `recruitment.html` | `/recruitment` | Official-sources-only statement + 21 real exam pages we already cover |
| `pdfs.html` | `/pdfs` | PDF registry; empty state |

Every hub carries full metadata (title, 140–160 char description, canonical,
OG/Twitter, `CollectionPage`/`WebPage` + `BreadcrumbList` JSON-LD),
`robots: index, follow`, breadcrumb, back-link to Home, and a hub entry in the
sitemap at 0.8 priority. Empty hubs are **not** noindexed — the structure is
real and will fill.

### Item pages (generated only when Markdown exists)

`note-*.html`, `magazine-*.html`, `strategy-*.html`, `session-*.html`,
`recruit-*.html` — built, validated and cleaned up by `scripts/build_content.py`.
None ship in this commit: there is no real content to publish yet.

**Per-note features (all implemented):** title · description · byline
(brand, no invented person) · published + updated dates · reading time ·
difficulty · exam tags · subject · breadcrumb · table of contents with
scrollspy · related notes · related quizzes · Download PDF button ·
share row (copy link / WhatsApp / Telegram / X, works without JS) ·
language switch to the Punjabi edition · previous / next note.

**Magazine features (all implemented, render only from real fields):**
cover image (declared `aspect-ratio`, `width`/`height`, `decoding=async`) ·
Download PDF · "Read online" anchor · "Attempt the issue MCQs" · "All issues"
archive link · Important highlights · Most expected MCQs · Related current
affairs · archive on the hub.

**Session features (all implemented, render only from real fields):**
date · time · platform · status · Join button (https only) · "All sessions"
link · session summary · important questions · student doubts · `Event`
JSON-LD emitted **only** when `date` + `start_time` exist.

**Recruitment features (all implemented, block-per-field):** official
notification (allow-listed `.gov.in` / `.nic.in` / `pspcl.co.in` URL, required
before the file builds) · eligibility · syllabus · selection process ·
important dates · preparation strategy · expected questions · previous papers.
Each block appears only when the Markdown supplies it — empty means silence,
never filler. Recruitment never touches the existing `exam-*.html` pages.

---

## 3. Created files

| File | Lines | Role |
|---|---|---|
| `scripts/build_content.py` | 1936 | Markdown → HTML: front-matter parser (incl. inline lists), Markdown renderer, validation, reading time, TOC, related notes/quizzes, prev/next, share, byline, schema, 6 hubs, homepage feeds, manifest, stale-page cleanup, `--strict` mode |
| `assets/js/content.js` | 96 | Copy-link (clipboard + `execCommand` fallback + toast) and TOC scrollspy |
| `data/content-manifest.json` | generated | Deterministic manifest (no timestamps) feeding sitemap + SEO gate |

---

## 4. Modified files

| File | Change |
|---|---|
| `assets/js/core.js` | Desktop **Study** dropdown (7 links), mobile drawer **Study** group, footer **Study** column (Study Guides moved into it), 8 new i18n keys, dropdown wiring generalised to `querySelectorAll("[data-nav-drop]")` with sibling-close + Escape |
| `assets/css/style.css` | Header fits 8 nav items on one 66px row (tightened links ≥900, wordmark hidden 900–1199 so the logo carries the brand), footer grid → 5 columns ≥900, content-page block (`.doc-layout`, `.doc-toc`, `.prose`, badges, actions, share, prev/next, `.doc-issue`, `.doc-cover`, `.doc-facts`) |
| `index.html` | 5 `<!-- HOA-FEED:… -->` markers (notes, current-affairs, magazine, sessions, recruitment); the current-affairs block renders the real CA sets today |
| `scripts/seo_check.py` | Manifest-driven `PAGES`/`BC_PAGES`, `Event` type + required fields, and a **content gate**: generated markers, hub links in `core.js`, sitemap URLs, manifest count vs rendered, hub back-links, homepage feed sync |
| `scripts/build_index.py` | Content block in the sitemap (hubs 0.8, items 0.6) |
| `scripts/build-index.mjs` | Same block, byte-identical for the CI parity step |
| `scripts/ci.sh` | New **step 1/6** runs `build_content.py` before the manifest; steps renumbered |
| `sw.js` | `VERSION = "hoa-v35"`; 6 hubs + `assets/js/content.js` added to `SHELL_FILES` |
| `sitemap.xml` | 6 hub URLs (106 total) |
| `README.md` | §24 *Content system — Markdown to live pages* |

Not modified (intentionally): the quiz engine, daily quiz, leaderboard,
progress, bookmarks, subject pages, `data/exams.json`, the landing builder's
page set, `index.html` markers required by `seo_check`, and `404.html`.

---

## 5. Navigation updates

**Desktop header (one row, 8 items):** Home · Subjects ▾ · **Study ▾ (new)** ·
Daily Quiz · Mock Tests · Bookmarks · About · Contact.

The new **Study ▾** dropdown holds: Study Notes · Current Affairs ·
Monthly Magazine · Preparation Strategy · Live Sessions · Recruitment ·
Free PDFs.

**Mobile drawer:** new **Study** group with the same 7 links, placed before
Practice.

**Footer:** new **Study** column (Study Notes, Study Guides, Current Affairs,
Monthly Magazine, Preparation Strategy, Live Sessions, Recruitment, Free PDFs).
Footer is now 5 columns ≥900px (brand + 4 link columns).

**Fit safety:** at 900–1199px the wordmark is hidden (logo + `aria-label`
carry the brand) so brand + 8 links + actions never wrap the row; measured
natural widths were nav 557px / brand 196px / actions 238–384px.

**Homepage:** the existing "free guides" section gained a note-feed marker;
a new current-affairs block renders the latest real sets; magazine, sessions
and recruitment blocks are present but empty until their first file exists.
Top Scorers was **not** added — the leaderboard is sign-in gated, so a public
score block would either expose data we do not have or fake it.

---

## 6. Content system behaviour

```
content/<collection>/<file>.md        (+ <file>.pa.md for the Punjabi edition)
        │  python3 scripts/build_content.py
        ▼
<prefix>-<slug>.html   ← title, description, canonical, OG, JSON-LD,
hub page (cards)          breadcrumb, TOC, related, prev/next, share,
data/content-manifest.json  badges, language switch — all derived
sitemap.xml (via build_index)  homepage feed block
```

Automatic per file: SEO title/description validation (≤60 / 140–160),
Open Graph + Twitter cards, BreadcrumbList, `Article`/`Event`/`CollectionPage`
JSON-LD, reading time, internal links, related-article cards, related-quiz
cards, stale-page cleanup when a file is deleted.

**Rules the builder enforces:** official-domain allowlist for recruitment,
files must exist (`pdf`, `cover`, `quiz`, `file`), https-only join links,
valid subject ids, ISO dates, inline-list parsing, brand-only byline, fail-fast
(nothing is written when validation fails).

**Punjabi-first:** pages default to Gurmukhi content when the `.pa.md` exists;
the English page links to it and vice versa (`hreflang` + language badge).
`<html lang>` stays `en` on English pages; Punjabi editions use `lang="pa"`.

---

## 7. Reserved — schema-ready, deliberately inactive

| Section | State | Why |
|---|---|---|
| Previous Year Questions | Types + templates ready, nothing rendered or linked | Real papers are third-party copyright; waits for verified sources |
| Expected Questions | Rendered only when Markdown supplies them (recruitment block exists) | Never auto-generated |
| Mock paper pages | Reserved prefix + hub slot, inactive | Needs real data |

Same discipline for vacancies: no date, count or deadline is ever written by
the builder — only restated from an official notification the editor pastes in.

---

## 8. Future content workflow

1. Write `content/notes/my-topic.md` (schema in `content/notes/README.md`).
2. Optional Punjabi edition: `content/notes/my-topic.pa.md`.
3. `python3 scripts/build_content.py` — it validates and prints what it wrote.
4. `bash scripts/ci.sh` — content → manifest → landing → SEO → rich results →
   tree-parity. All must be green.
5. Commit the Markdown **and** the generated HTML together; push.

Deleting a file removes its page, its manifest entry, its sitemap URL and its
homepage feed card on the next build.

---

## 9. Verification

| Gate | Result |
|---|---|
| `python3 scripts/build_content.py` | ✅ 6 hubs, 0 items, 0 PDFs, no warnings |
| `python3 scripts/build_landing_pages.py` | ✅ 82 generated pages unchanged |
| `python3 scripts/seo_check.py` | ✅ `RESULT: PASS — no hard failures` (sitemap 106 URLs; "6 hubs + 0 document pages in sync") |
| `python3 scripts/rich_results_check.py` | ✅ `PASS - every feature present meets Google's published requirement list` |
| Temporary-content stress test | ✅ notes (EN + PA), magazine (cover/PDF/quiz/highlights), 2 sessions (upcoming + past), recruitment, PDF — all gates passed with items present; then removed and rebuilt clean |

Manual checks (browser): note page — badges, TOC (5 links), share row (4),
1 × `h1`, no horizontal overflow; magazine page — cover box reserved at
240×320, fact chips, 3 action buttons; session page — facts, badges,
summary/questions/doubts sections, prev/next pair; homepage — feed markers
empty when there is no content, real CA links when there is; footer has all
6 hub links; drawer has the Study group; no console errors.

**Measured header fit (natural widths):** nav 557px, brand 196px,
actions 238–384px → at 900–1199px with the wordmark hidden the row needs
≈700px of the available ≈850px.

---

## 10. Known limitations / next steps

1. **Lighthouse performance** cannot be measured locally (no Node CLI, no
   visible tab long enough for the trace). Proxy evidence from this build:
   no new render-blocking assets, no third-party requests, `content.js` is
   deferred and only loaded on content pages, images carry explicit
   dimensions. Run the Lighthouse CI step on the first deploy.
2. **CI Node parity step** runs for the first time on the next push (no local
   Node) — `build_index.py` and `build-index.mjs` must emit identical
   content-sitemap bytes.
3. **Translation parity** (`verify_translation_parity.py`) is a future gate;
   known defect: `current-affairs-july-2026-part3` EN/PA question 16 answers
   disagree.
4. **Top Scorers homepage block** deferred until the leaderboard can be read
   without breaking the sign-in gate.
5. **Cover images**: `cover_width`/`cover_height` are optional but
   recommended — the builder reserves the declared box either way.

---

# Phase 2 — Content Automation Engine

Markdown stays the single source of truth; everything below is generated from
it by the same `scripts/build_content.py` run. Nothing is hand-edited: the
navigation, the content index, the search corpus, the feed and the archive are
all outputs of one command.

## 11. Content model

| Folder | Prefix | Hub | State |
|---|---|---|---|
| `content/notes/` | `note-` | `study-notes.html` | unchanged |
| `content/current-affairs/` | `ca-` | `current-affairs.html` | **new** |
| `content/monthly-magazine/` | `magazine-` | `magazine.html` | renamed from `content/magazine/` ( URL unchanged ) |
| `content/strategy/` | `strategy-` | `strategy.html` | unchanged |
| `content/live-sessions/` | `session-` | `live-sessions.html` | renamed from `content/sessions/` ( URL unchanged ) |
| `content/recruitment/` | `recruit-` | `recruitment.html` | unchanged |
| `content/blogs/` | `blog-` | `blogs.html` | **new** |
| `content/news/` | `news-` | `news.html` | **new** |
| `content/announcements/` | `announce-` | `announcements.html` | **new** |
| `content/pdfs/` | — | `pdfs.html` | unchanged (registry, no page) |

**Front matter (all article collections):** `slug`, `language`, `author`,
`reviewedBy`, `category`, `subject`/`subjects`, `exam`/`exams`, `tags`,
`difficulty`, `readingTime` (editorial override of the 200-wpm estimate),
`coverImage` (alias of `cover`), `pdf`, `quiz`, `featured`, `draft`.

* `draft: true` → validated, but published **nowhere** (page, manifest, sitemap,
  feed, search index, archive, homepage).
* `language` must match the file variant (`en` for `.md`, `pa` for `.pa.md`).
* `featured: true` renders a badge; popularity stays measured, never assumed.

## 12. Language URLs — English at the root, Punjabi under `/pa/`

| Edition | URL | Page |
|---|---|---|
| English | `houseofaspirants.in/<prefix>-<slug>` | `<prefix>-<slug>.html` |
| Punjabi | `houseofaspirants.in/pa/<prefix>-<slug>` | `pa/<prefix>-<slug>.html` |

* Punjabi pages carry `<base href="/">`, so the shared header, drawer and
  footer (which link relatively) keep resolving from the site root — no chrome
  markup was rewritten for this.
* In-page anchors on `/pa/` pages are emitted as `/pa/<file>#section`; the
  skip-to-content link is corrected at runtime when a `<base>` is present.
* Reciprocal `hreflang` pair in `<head>` **and** a language badge on the body;
  `seo_check.py` fails if either side stops cross-linking.
* Canonical stays extensionless on `https://houseofaspirants.in` in both
  editions, so English URLs are untouched (zero SEO churn).

## 13. Generated outputs (one build, no manual HTML)

| Output | Source of truth | Notes |
|---|---|---|
| `data/content-manifest.json` (Content Index) | `HUBS` + front matter | hubs, index pages (`pages`), every document with language pair, category, author, reading time |
| `data/search-index.json` | documents + study guides + exam pages | title, description, body (1200 chars), tags, subjects, exams, category |
| `feed.xml` | newest 20 documents | RSS 2.0, `pubDate` from `published` only → byte-identical on rebuild |
| `archives.html` | manifest | latest, popular (only from `data/popularity.json`), by subject, by exam, by month |
| nav blocks in `assets/js/core.js` | `HUBS` / `NAV_ENTRY` | Study menu + drawer Study group + footer Study column, between `<!-- HOA-NAV:* -->` markers |
| homepage feed blocks, sitemap, `/pa/` cleanup | manifest | existing behaviour, extended to `pa/` |

`data/popularity.json` ships **empty**: "Popular posts" renders only when real
view counts are pasted in, so the section can never claim a number that does
not exist.

## 14. Search

`Ctrl+K` / `/` / the 🔍 button opens the existing overlay. It now merges:

1. the flat index built from `data/index.json` (subjects, categories, topics),
2. the lazily fetched `data/search-index.json` (documents, guides, exams).

Scoring is token-based (every word must match) and weighted: title 6 →
tags/subjects/exams/category 4 → description 2 → body 1. The corpus is fetched
on **first open only** — page load never waits for it.

## 15. Learning path (automatic internal links)

Every document renders a `Where this page fits` chain:
current page → related quiz → *Previous Year Questions (reserved)* →
*Expected MCQs (reserved)* → current affairs → magazine → strategy. Steps link
only what exists (newest real page, else the hub); the two reserved steps are
named but never linked, so the path stays honest until verified data exists.

## 16. Files created / modified

**Created:** `content/{current-affairs,blogs,news,announcements}/` (+ READMEs),
`archives.html`, `feed.xml`, `data/search-index.json`, `data/popularity.json`,
`current-affairs.html`, `blogs.html`, `news.html`, `announcements.html`.

**Modified:** `scripts/build_content.py` (HUBS, front-matter contract, `/pa/`
URLs, nav generation, chain, search/feed/archive writers), `scripts/seo_check.py`
(pages + language pairs + search + RSS + popularity gates), `scripts/rich_results_check.py`
(now audits `pa/*.html`), `scripts/build_index.py` + `scripts/build-index.mjs`
(manifest `pages` → sitemap, parity-mirrored), `assets/js/core.js` (nav markers,
full-site search, skip-link fix, i18n), `assets/js/content.js` (anchor-aware
TOC), `assets/css/style.css` (`.doc-chain`, `.arch-*`), `sw.js` (`hoa-v36` +
new hubs), `README.md` §24, `content/README.md`.

**Renamed (URLs unchanged):** `content/magazine` → `content/monthly-magazine`,
`content/sessions` → `content/live-sessions`.

## 17. Verification

* Every pipeline stage exercised with temporary content in **all 10**
  collections (EN + PA), then deleted — stale cleanup removed all 10 pages
  including `pa/`, leaving honest empty states.
* Measured in the browser: archives lists every document once per axis; the
  `/pa/` page resolves chrome, TOC, chain and language switch correctly;
  search returns the exam page → study guide → document for
  "punjab police constable" and both language editions for "revenue act";
  Study menu, drawer and footer show all 11 hub links; header fit unchanged
  (nav 547px inside a 1000px header — no new top-level items).
* Gates: `build_content` → `build_index` → `seo_check` **PASS** (content: 10
  hubs in sync, search/RSS/archives wired), `rich_results_check` **PASS** with
  `pa/*.html` included in the audit.

## 18. Known limitations (Phase 2)

1. **Lighthouse** still unmeasurable locally; Phase 2 adds no render-blocking
   asset (search corpus is fetched on first open only, CSS additions are small).
2. **Node parity** (`build-index.mjs`) runs on push — the `pages` loop was
   written byte-for-byte in both builders, but it has never executed locally.
3. **`/pa/` clean URLs** depend on the host's extensionless rewrite, exactly
   like the existing English canonicals; internal links keep `.html`, which
   works with or without it.
4. **Popular posts** needs a real analytics export before it renders anything.
5. **Translation parity** gate still pending (known EN/PA defect noted above).

---

# Phase 3 — AI Content Engine

Everything below is **architecture, not invented content**: templates,
scoring, linking and reporting rules that only ever describe material that
really exists in `content/`. The site ships with 0 documents published; every
claim here was measured with temporary documents and then re-verified against
the empty build.

## 19. Content templates + scaffold

`scripts/content_engine.py` (new) holds `TEMPLATES`: eleven page types, each
with its label, collection, JSON-LD type, chapter behaviour, required fields
and an ordered recommendation plan.

| Template key | Type | Collection |
|---|---|---|
| `study-note` | Study Note | `notes/` |
| `current-affairs` | Current Affairs | `current-affairs/` |
| `monthly-magazine` | Monthly Magazine | `monthly-magazine/` |
| `expected-mcq` | Expected MCQ | `expected-mcqs/` |
| `previous-year-question` | Previous Year Question | `previous-year-questions/` |
| `preparation-strategy` | Preparation Strategy | `strategy/` |
| `motivation` | Motivation Article | `strategy/` |
| `book-review` | Book Review | `strategy/` |
| `live-session-summary` | Weekly Live Session | `live-sessions/` |
| `recruitment-notification` | Recruitment | `recruitment/` |
| `exam-analysis` | Exam Analysis | `blogs/` |

Two collections were added so those two types can publish honestly:
`expected-mcqs` (`expected-mcqs.html`) and `previous-year-questions`
(`previous-year-questions.html`). Both ship an empty state, are registered in
`HUBS`/nav/footer/sitemap, and their learning-path steps stay **reserved and
unlinked** until a real document exists — `CHAIN_TARGETS` links the step only
when there is a target to link to.

`scripts/new_content.py` (new) scaffolds from a template:

```bash
python3 scripts/new_content.py --list
python3 scripts/new_content.py --type study-note --slug punjab-history-sikh-period
python3 scripts/new_content.py --type current-affairs --slug july-week-1 --pa
```

Scaffolds go to `content/_drafts/<collection>/<slug>.md`, a path the builder
never loads, so an unfinished file cannot fail CI; titles/descriptions are
placeholders the validator rejects if someone publishes them unchanged.

The build validates `type` against both `TEMPLATES` and the collection it was
filed under, and `main()` fails the run if a template's required fields are
not enforced by its collection's contract.

## 20. The recommendation engine (facets, not filler)

`score()` weights: subject **6**, exam **4**, tag **3**, category **3**,
difficulty **2**, featured **2**, shared section **1**; `language` (**2**) is
deliberately **not** part of the score — `rank()` applies it as a tie-break
between candidates that already overlap, so shared language can prefer a
Punjabi edition but can never make two unrelated documents "related".

`rank()` sorts by score, then reading time (shorter first), then newest; a
slot only shows candidates that scored above zero unless it is explicitly
marked `any` (the "More &lt;section&gt;" slot, where being in the same section
*is* the relevance). Candidates are never their own recommendation, and the
same target never appears twice in a plan.

## 21. What each page type renders

Every document ends with one "What to do with this page" section built from
its plan, grouped by slot title, plus a TOC aside line
(`≈ N min to finish · difficulty` = estimated completion time) and — for
chaptered collections — previous/next chapter labels.

* **Study note** → practice set (the document's own `quiz:` first, otherwise
  a set that shares its subject), subject hub, current affairs, expected MCQs,
  previous papers, more notes, guides.
* **Current affairs** → practice set, latest magazine issue, related news,
  government schemes (tag filter), Punjab GK subject hub.
* **Recruitment** → eligibility, syllabus, strategy, free PDFs, previous
  papers, expected questions, live session — with on-page anchors
  (`#notification`, `#eligibility`, `#syllabus`, `#dates`) rendered only when
  the document declares those fields.
* **Reserved honesty** → a slot with no matching data renders one compact
  line, e.g. `Reserved — Expected MCQs, Previous Year Questions …`, and is
  never a link.

## 22. Content graph, silos and pillars

`data/content-graph.json` (new): **47 nodes, 102 contextual links, 28 silos
(27 pillars, 19 clusters)** in the empty build.

* Nodes are the documents, the 12 hubs and the archive; edges are re-read out
  of the HTML that actually shipped, so the graph cannot describe a link the
  site does not serve (share links on `t.me` / Twitter / WhatsApp are excluded
  by host matching, and absolute links to our own domain are normalised to
  their path).
* Silos cover every subject and every exam: pillar (the guide named after the
  silo, else the narrowest guide that shares its subjects, else `null`) → hub
  (subject/exam landing page from `data/landing-manifest.json`) → clusters
  (category + cluster + topic landing pages) → leaves (documents).

## 23. Five contextual internal links, or the build fails

`enforce_link_floor()` counts unique contextual links inside `<main>` and
appends an "Explore the library" module (six links) when a generated page is
short; seven hand-written pages that were below the floor — `contact`, `faq`,
`mock`, `progress`, `result`, `bookmarks`, `subject` — received the same
module as a "Where to go next" section. `seo_check.py` re-counts **all 115
shipped pages** (404 excluded) with the builder's own `link_floor()` and fails
the run if any page is below five.

## 24. Homepage engine

* `index.html` gained `#foryou` with `<!-- HOA-HOME:popular -->` (server
  rendered by `patch_index()` from `data/popularity.json` — ships empty, so
  Popular notes / Trending quiz stay hidden) and `<!-- HOA-HOME:data -->`
  (the candidate list, EN documents only, embedded — no extra request).
* `assets/js/home.js` scores that list against *this* reader: the subject
  they last practised (`HOA.progress.get().lastSubject`) and their bookmarks
  produce **Continue learning** and **Recommended for you** cards. With no
  signal the section stays `hidden` — measured in the browser: seeded progress
  → 3 cards and the section visible; cleared storage → section hidden; zero
  console errors either way.

## 25. Files created / modified

**Created:** `scripts/content_engine.py`, `scripts/new_content.py`,
`data/content-graph.json`, `expected-mcqs.html`,
`previous-year-questions.html`.

**Modified:** `scripts/build_content.py` (template-aware validation, plan
renderer, `enforce_link_floor`, graph writer, homepage engine, `patch_index`
args, chapter labels, recruitment anchors), `scripts/seo_check.py` (link
floor, content-graph validity, template parity — one `link_floor()` shared
with the builder), `assets/js/home.js` (engine cards), `assets/js/core.js`
(nav markers + Punjabi labels for the two new hubs), `assets/css/style.css`
(`.rec-title`, `.rec-reserved`, `.toc-meta`), `index.html` (`#foryou`),
`sw.js` (`hoa-v37` + both hubs in the shell), seven static pages (link
floor), `README.md` §24, `content/README.md`.

## 26. Verification

* Pipeline exercised end to end with **5 temporary documents** across notes
  (EN + PA), current affairs and recruitment, then deleted: 5 pages built,
  30 search entries, 5 RSS items, 63 nodes / 167 edges, stale cleanup removed
  every page and the `pa/` twin, returning 47 nodes / 102 edges.
* Measured in the browser on a document page: 4 recommendation groups, chain
  `current → quiz → reserved PYQ → reserved Expected → current affairs →
  magazine → strategy`, chapter labels, `≈ 1 min to finish · Easy`, heading
  order `H1 H2×4 H3×8 H2` (no skips), 10 contextual links, no console errors;
  computed styles confirm the new CSS (`.rec-title` uppercase 13.4px,
  `.rec-reserved` dashed flex, `.toc-meta` bordered).
* Recruitment anchors, eligibility/syllabus groups and the reserved
  previous-papers line verified on a temporary notice; PA page verified with
  `<base href="/">`, `/pa/…#section` anchors and 13 contextual links.
* Gates: `build_landing_pages.py` → `seo_check.py` **PASS** with the three
  new notes (`link floor`, `content graph … all resolving`,
  `content templates: 11 …`), `rich_results_check.py` **PASS**,
  `scripts/ci.sh` green with `generatedAt` restored.

## 27. Known limitations (Phase 3)

1. **Lighthouse** still unmeasurable locally; Phase 3 adds one CSS block, one
   small JS function and no request on the homepage (the candidate list is
   embedded, popularity ships empty).
2. **Node parity** (`build-index.mjs`) still runs on push only.
3. **Graph scope** — nodes/edges cover the content tree (documents, hubs,
   archive), not the whole site; chrome-only pages such as `contact` are
   counted by the link-floor gate but are not graph nodes.
4. **Popular notes / Trending quiz** stay hidden until a real
   `data/popularity.json` exists; nothing is guessed.
5. **Personalisation** is client-side and first-party only (last subject +
   bookmarks); there is no account-level profile to score against until the
   backend phase.
