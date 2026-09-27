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

# Phase 4 — Data-Driven Content Platform

Phase 4 turned "pages we wrote" into "pages the content produces". The design
did not change, the quiz engine did not change: every route below is generated
from a Markdown file, a JSON registry or a table inside the builder, and a
collection with nothing in it still publishes an honest empty state rather
than a placeholder.

## 28. Collections, folders and routes

All 17 collections from the brief have a folder, a hub, a navigation entry, a
sitemap entry, a search record and a filter bar. `news/` is the 18th hub (it
predates Phase 4); *Important Notifications* maps to `announcements/`.

| collection | folder | page prefix | hub | required beyond the shared fields |
| --- | --- | --- | --- | --- |
| Study Notes | `notes/` | `note-` | `study-notes.html` | `subject` |
| Personal Notes | `personal-notes/` | `pnote-` | `personal-notes.html` | `subject` |
| Punjab Current Affairs | `current-affairs/` | `ca-` | `current-affairs.html` | — |
| Monthly CA Magazine | `monthly-magazine/` | `magazine-` | `magazine.html` | `month` |
| Weekly Live Sessions | `live-sessions/` | `session-` | `live-sessions.html` | `date` |
| Exam Strategies | `strategy/` | `strategy-` | `strategy.html` | `category` |
| Preparation Blogs | `blogs/` | `blog-` | `blogs.html` | — |
| Recruitment Updates | `recruitment/` | `recruit-` | `recruitment.html` | `post`, `official_url` |
| Important PDFs | `pdfs/` | — (registry) | `pdfs.html` | `file` |
| Expected MCQs | `expected-mcqs/` | `expected-` | `expected-mcqs.html` | `subject` |
| Previous Year Questions | `previous-year-questions/` | `pyq-` | `previous-year-questions.html` | `exams` |
| Subject Guides | `subject-guides/` | `sguide-` | `subject-guides.html` | `subject` |
| Topic Guides | `topic-guides/` | `tguide-` | `topic-guides.html` | `subject` |
| Daily Practice | `daily-practice/` | `practice-` | `daily-practice.html` | `subject` |
| Success Stories | `success-stories/` | `story-` | `success-stories.html` | `exam` |
| Book Recommendations | `book-recommendations/` | `book-` | `book-recommendations.html` | `subject` |
| Important Notifications | `announcements/` | `announce-` | `announcements.html` | — |
| News (extra) | `news/` | `news-` | `news.html` | — |

**Generated routes** (extensionless URLs, English at the root, Punjabi under
`/pa/`):

* 18 collection hubs;
* one page per document: `<prefix>-<slug>`, plus `pa/<prefix>-<slug>` when a
  `.pa.md` edition exists;
* `archives.html` (the index everything hangs off), `search.html`,
  `author-<id>.html`, `archive-tag-<slug>.html`, `archive-category-<slug>.html`;
* the landing set that already existed: subject / topic / category / cluster /
  exam / quiz pages.

`sitemap.xml` carries **121 URLs with no documents published**; every document,
tag, category and author adds its own URL in the same build, registered through
`data/content-manifest.json` so the sitemap, the canonical tag and the chrome
check can never disagree.

## 29. The document contract

Every document carries the full platform model — `id`, `subtitle`, `language`,
`category`, `subject`, `examTags`, `difficulty`, `publishDate`, `updatedDate`,
`author`, `reviewedBy`, `readingTime`, `coverImage`, `thumbnail`, `seoTitle`,
`seoDescription`, `keywords`, `summary`, `tableOfContents`, `body`,
`relatedContent`, `relatedQuiz`, `downloadPDF`, `telegramLink`, `youtubeLink`,
`references`, `faq`, `schemaType`, `featured`, `status` — validated before a
single byte is written:

* the brief's spellings are **aliases** (`publishDate → published`,
  `updatedDate → updated`, `examTags → exams`, `relatedQuiz → quiz`,
  `downloadPDF → pdf`, `tableOfContents → toc`), applied *before* validation,
  so one canonical key per value;
* titles ≤ 60, descriptions 140–160, `seoTitle` ≤ 60, `seoDescription`
  140–160, ≤ 12 keywords × 48 chars, `summary` ≤ 320, dates `YYYY-MM-DD`;
* `schemaType` ∈ `Article | BlogPosting | NewsArticle | WebPage`;
  `status` ∈ `published | draft | archived` (sessions also `upcoming | past |
  held`) — `draft`/`archived` render nowhere: no page, sitemap, feed, search
  index or archive;
* `faq` becomes a section **and** a real `FAQPage` node; `references` become a
  *Sources* list; `relatedContent` only ever links a target that exists
  (missing ones are reported, never shipped);
* unknown keys warn, missing required keys fail the build.

## 30. Generated page types (19)

Home, Subjects, Subject, Topic, Notes, Magazine, Blogs, Strategies, Live
Sessions, Recruitment, Current Affairs, PDF Library, Expected MCQs, PYQs, Daily
Quiz, Search Results, Author Profile, Tag Archive, Category Archive — plus the
archives index. Each is built from the manifest rather than edited:

* **Search Results** — `search.html`: a GET form that works with JavaScript
  off, filled by `content.js` from `data/search-index.json` after paint.
* **Author Profile** — `author-<id>.html`, `@type: ProfilePage` with
  `mainEntity` → the Person node.
* **Tag / Category Archive** — created only when an English document really
  carries the value, removed again when the last one goes.
* **Subject / Topic / Category** landings keep the pre-existing
  `build_landing_pages.py` set; its stale-deletion now skips anything the
  content manifest registers (that is how `subject-guides.html` /
  `topic-guides.html` survive it).

## 31. Navigation, search and related content (all automatic)

* **Navigation** — the header Study menu, drawer and footer are rewritten from
  the `HUBS` table between the `<!-- HOA-NAV:* -->` markers in
  `assets/js/core.js`; the footer also gains a *Search* link and every profiled
  author. Adding a collection adds its menu entry, sitemap URL, search record
  and chrome link in one run — no hand-edited HTML or JS.
* **Search** — `data/search-index.json` now carries `m` (summary), `w`
  (keywords), `a` (author) and `f` (difficulty) on each document row, next to
  title, description, body, tags, subjects, exams and category. Both the Ctrl+K
  overlay and `search.html` fold the same fields into one haystack.
* **Filters** — a listing with >1 document and >1 value in any facet renders a
  chip bar (Exam, Subject, Language, Difficulty, Date, Category); cards carry
  `data-f-*`, and `assets/js/content.js` filters the DOM that already shipped
  (OR inside a facet, AND across facets, one `Clear filters` button, a live
  count). No request, no re-render, no control that cannot do anything.
* **Related** — each of the 17 templates owns a recommendation plan (practice
  quiz, subject hub, same-collection siblings, strategy, notes, reserved slots
  for expected MCQs/PYQs with an honest "why this is empty" line), scored on
  shared subject/exam/tag/category. `relatedContent` adds an editorial override,
  and the **link floor** guarantees ≥ 5 contextual internal links in `<main>`
  by appending an *Explore the library* module — topped up from the hubs when a
  page's own collection cannot fill it, and deduplicated so the same card never
  appears twice.

## 32. Author system (E-E-A-T)

`data/authors.json` is the registry: name, id, role, bio, credentials, topics
and `profile: true|false`.

* an `author:` value that is not in the registry **fails the build** — bylines
  stay a known list, never free-running text;
* a profiled author gets `author-<id>.html`, is linked from every document
  carrying the byline and appears in the footer; the JSON-LD `author` becomes a
  `Person` (`name`, `url`, `jobTitle`) pointing at that page;
* a non-profiled entry (e.g. *House of Aspirants Editorial Team*) stays an
  `Organization` node behind `/about` and gets no page, because nothing should
  link to a person the site cannot introduce;
* the example entry is *Gurpreet Singh — Punjab Police Sub Inspector, Founder of
  House of Aspirants, Competitive Exam Mentor, Monthly Current Affairs Author,
  Weekly Live Session Mentor*.

## 33. Magazine, session and blog contracts

* **Magazine** — cover (dimensions + file), PDF download, online reading,
  highlights, `expected_mcqs`, `important_questions`, `revision_notes`, related
  quiz. Each block renders only when written.
* **Live sessions** — title, topic, date, time (`start_time` for the Event
  slot), platform, join link, poster (640×360), recording link, resources
  (https URL or a site path), questions covered, doubts, summary, and `status`
  shown only for `upcoming`/`past`/`held`. No Event schema is published for a
  slot that has no real start time.
* **Blogs** — the seven subtypes (Preparation Experience, Study Plans, Time
  Management, Motivation, Book Reviews, Mistakes, Strategy Articles) are
  validated against the collection, normalised for the archive page.

## 34. The CMS: no database

```
Markdown + JSON + static assets
   │
   ├─ scripts/build_content.py   validate → render → manifest → search index
   │                             → RSS → archives → index pages → nav →
   │                             homepage feed → stale-page cleanup
   ├─ scripts/build_index.py     data/index.json + sitemap.xml
   ├─ scripts/build_landing_pages.py  subject/topic/category/exam/quiz landings
   └─ scripts/ci.sh              both index builders (+ Node parity), landing
                                 set, seo_check, rich_results, drift check
```

One build updates the page, the sitemap, the search index, the navigation, the
RSS feed, the JSON-LD and the internal links together; `scripts/new_content.py`
scaffolds a valid draft (required fields included) for any of the 17 templates,
and `content/_drafts/` is never read by the builder. Review happens in Git —
the rendered HTML and `data/*` are committed alongside the Markdown because
static hosting needs the bytes.

## 35. SEO improvements

* per-page `title` / `description` / canonical / Open Graph / Twitter from
  `seoTitle`, `seoDescription`, `keywords` and `thumbnail` when present;
* JSON-LD per document: `Article`-family node (or the declared `schemaType`),
  `BreadcrumbList`, optional `FAQPage`, `Person`/`Organization` author, plus
  `ProfilePage` for author pages and `CollectionPage` + `ItemList` for tag and
  category archives;
* taxonomy pages (`archive-tag-*`, `archive-category-*`) are in the sitemap and
  reachable from `archives.html` **and** from every document that carries the
  tag — nothing exists only in the footer;
* a crawlable `search.html` with a real GET form, so the corpus is discoverable
  without JavaScript;
* `hreflang` pairs for every EN/PA document, English published at the root;
* the link floor (≥ 5 contextual links in `<main>`) plus a graph of 56 nodes /
  154 contextual edges / 28 silos, all resolving;
* RSS 2.0 (`feed.xml`) fed from the same manifest.

## 36. Files created / modified

**Created:** `data/authors.json`, `content/personal-notes/README.md`,
`content/subject-guides/README.md`, `content/topic-guides/README.md`,
`content/daily-practice/README.md`, `content/success-stories/README.md`,
`content/book-recommendations/README.md`, and (generated) `search.html`,
`author-gurpreet-singh.html` with every `archive-tag-*` / `archive-category-*`
page the moment documents exist.

**Modified:** `scripts/build_content.py` (6 new hubs, nav tables, field
contracts + aliases, author registry, byline/FAQ/references/related rendering,
filter facets and bars, `index_shell` + author/tag/category/search pages,
search-index fields, link-floor top-up, taxonomy badges, stale cleanup moved
after every writer), `scripts/content_engine.py` (17 templates and their
defaults), `scripts/seo_check.py` (`ProfilePage`/`BlogPosting`/`NewsArticle`,
landing-stale exclusion, index-page rules, byline/taxonomy/filter/search-field
gates), `scripts/build_landing_pages.py` (protects manifest-registered files),
`scripts/new_content.py` (17 templates, valid-by-default required fields,
`--pa` writes the EN/PA pair), `assets/js/core.js` (Punjabi labels, type
labels/icons, search haystack, `nav-cols`, footer extras),
`assets/js/content.js` (filter + search-page readers), `assets/css/style.css`
(Phase 4 block, linked badges), `sw.js` (`hoa-v38` + the 6 hubs and
`search.html` in the shell), `content/README.md` (content model + authoring
guide).

## 37. Verification

* Pipeline exercised end to end with **10 temporary documents** across all six
  new collections plus blogs, magazine and sessions (EN + PA), then deleted:
  10 pages + 1 PA twin, 24 index pages (author, 22 tag/category archives,
  search), 35 search rows, 10 RSS items, 101 nodes / 469 edges, sitemap 153
  URLs; stale cleanup then removed every document page and archive and returned
  to 56 nodes / 154 edges / 25 search rows / 121 URLs.
* Scaffolds round-tripped: `new_content.py --type subject-guide` and
  `--type success-story --pa` were moved into their collections and **built
  clean** (required fields, description length and the EN/PA pairing all
  satisfied by the stub itself).
* Measured in the browser: filter chips on `personal-notes.html` narrow
  `2 shown → 1 of 2 shown → Clear`, `search.html?q=polity` renders 5 results
  with collection + author labels, the author page lists all 8 of its documents,
  the hub hero/answer-box/typography are unchanged, `quiz.html?mode=daily`
  renders its options with no console errors. Lighthouse (local): accessibility
  **1.0**, best practices **1.0**, SEO **1.0**, zero failures; navigation
  timings index 132 ms / hub 49 ms / quiz 95 ms.
* Gates: `build_content.py` → `build_index.py` → `build_landing_pages.py` →
  `seo_check.py` **PASS** (`18 hubs + 0 document page(s) in sync`, `bylines`,
  `taxonomy`, `filters`, `link floor`, `content graph … all resolving`),
  `rich_results_check.py` **PASS**, `bash scripts/ci.sh` **ALL GATES GREEN
  (6/6)** with `data/index.json generatedAt` normalised back to
  `2026-09-26T17:53:50.784Z`.

## 38. Known limitations / future scalability

1. **No documents ship.** The platform is architecture only, per the brief —
   empty collections publish an honest empty state, and Expected MCQs / PYQs
   stay reserved until verifiable data exists.
2. **Adding a collection** is two edits: a folder + a `HUBS` entry (title,
   description, prefix) and a `TEMPLATES` entry in `content_engine.py`.
   Navigation, sitemap, search, filters, archive, RSS, chrome and the SEO gates
   pick it up in the same run.
3. **Adding an author** is one line in `data/authors.json`; their page,
   bylines, footer entry and JSON-LD follow.
4. **Node parity** (`build-index.mjs`) still runs on push only — no Node is
   installed locally, so step 3 of `ci.sh` reports "skipped".
5. **Lighthouse performance** is not part of the local audit run (the tool
   returns accessibility / best practices / SEO only); Phase 4 adds one small
   JS block and one CSS block, both lazy, and no new request on first paint.
6. **Graph scope** remains the content tree; chrome-only pages are counted by
   the link-floor gate but are not graph nodes.

## 39. PDF drops — a PDF alone is enough to publish

**Problem.** Uploading a PDF into a content folder never changed the site:
`build_content.py` discovered documents with `cdir.glob("*.md")` only, so a
`.pdf` file was invisible to every page, the manifest, search, the feed and
the sitemap. The site behaved as if there were no content.

**Design.** A PDF is now a document like any other, published from its file
name alone — no Markdown, no front matter, no scaffold:

| Derived | Rule |
|---|---|
| title | file name title-cased, acronyms (PPSC, SI, PYQ, CA) kept, ISO dates preserved, cut to 60 chars |
| slug | the same lowercase-hyphen rule as every document; a clash gets `-2`, `-3` — never a failed build |
| description | title + collection label, assembled inside the enforced 140–160 character window |
| date | `2026-08-12` / `July 2026` / `2026-07` in the name wins; otherwise the first-seen date stored in `data/pdf-meta.json` |
| download URL | the file itself, percent-encoded once (`…/Punjab%20GK%20Sheet.pdf`) |

The record then enters the existing pipeline unchanged: hub card, doc page
with a Download button, `data/content-manifest.json`, search corpus
(summary/keywords/author), `feed.xml`, `archives.html`, taxonomy archives,
`sitemap.xml`, content graph and the homepage feed blocks.

**Edge cases handled**

* `Quant Shortcuts.pdf` next to `quant-shortcuts.md` → the PDF becomes that
  document's download instead of a second page (one file, one URL).
* `content/pdfs/` keeps its registry semantics: the PDF is listed on
  `pdfs.html`, no page is generated (hub count stays in sync with the
  manifest).
* Collection fields a file name cannot carry (`subject`, `post`,
  `official_url`, …) are skipped under a relaxed contract; the card and hero
  lead with *PDF download* rather than inventing data. The recruitment
  "Notification" block and its plan anchor render only when `official_url`
  exists, so no empty `href=""` is ever emitted.
* Generated titles are deduplicated site-wide before rendering (a gate in
  `seo_check.py`), disambiguated with the collection label —
  `My Notes` / `My Notes (Study Notes)` — and the description and body that
  quote the title are regenerated with it.
* `sw.js` (`hoa-v39`) no longer pins multi-megabyte PDFs into the shell/data
  caches; the browser's HTTP cache handles them.

**Determinism.** `data/pdf-meta.json` remembers `{hash, published, updated}`
per file, so a rebuilt tree on another machine (or in CI) is byte-identical —
the promise `scripts/ci.sh` step 6 depends on. A dropped PDF without a date
in its name gets today's date *once*, not on every run.

**Verification (local)**

* 12 test PDFs across notes, pdfs, recruitment, live-sessions,
  subject-guides, success-stories, blogs, daily-practice, monthly-magazine:
  11 doc pages + 1 registry record + 1 Markdown twin attachment, all visible
  on their hub, in `archives.html`, in `search.html` (1 result for
  "indian polity"), in `feed.xml` (11 items) and in the sitemap (132 URLs).
* `title`/`description` fuzzed over ~4 000 synthetic file names × 17 labels:
  0 descriptions outside 140–160, 0 empty or over-long titles.
* HTTP: `content/monthly-magazine/Current%20Affairs%20July%202026.pdf` →
  `200 application/pdf`, 5 853 735 bytes; schema on the generated page is
  `Article + WebPage + BreadcrumbList`.
* Gates: `build_content.py` → `build_index.py` → `build_landing_pages.py` →
  `seo_check.py` **PASS** → `rich_results_check.py` **PASS** →
  `bash scripts/ci.sh` **ALL GATES GREEN (6/6)** with the test files removed
  and the real PDF published (1 document page).
