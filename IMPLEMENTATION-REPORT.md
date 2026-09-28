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
the promise `scripts/ci.sh` step 7 depends on. A dropped PDF without a date
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

## 40. Subfolder drops, and the two parity gaps `npm run build` exposed

Running the Node twin of the index builder (`npm run build`, now that Node is
installed locally) turned up two gaps that only appear once a second builder —
or a second drop shape — enters the picture.

**1. Subfolders never published.** PDF discovery was `cdir.iterdir()`: a file
in `content/monthly-magazine/english/` simply did not exist as far as the site
was concerned, which is exactly the "dropped it and nothing happened" failure
the PDF work exists to prevent (and the shape the library on disk already has:
`history/chapter 1/part 1 (english).pdf`). The collection folder is now walked
(`rglob`, skipping hidden folders and `_drafts`), and the subfolder that
carried the file is kept on the record so two identically named files in
sibling folders say which one they are:

```
english/current affairs sheet.pdf  ->  Current Affairs Sheet
punjabi/current affairs sheet.pdf  ->  Current Affairs Sheet (Punjabi)
```

The folder name is path data, not a guess, so no subject or language is
invented; slugs stay deterministic (`…-2` on a clash).

**2. The homepage-feed gate could not agree with the homepage.**
`data/content-manifest.json` is written **alphabetically by file name** while
records are ordered **newest first by `(published, title)`**. On a date tie —
two August PDFs both first seen on the same day — `seo_check.py`'s
`max(published)` resolved to a different file than the block the build
rendered, failing the gate over a page that was correct. The check now
resolves ties exactly as the build does: English pool first, Punjabi after it,
`(published, title)` descending, and the current-affairs block still expects a
current-affairs document before a study note.

**3. `updatedAt` never round-tripped (step 3 of `scripts/ci.sh`).** Both
builders stamp a quiz's `updatedAt` from its file mtime, but Python computed
`st_mtime * 1000` and Node `statSync().mtimeMs` — two different doubles from
the same nanosecond timestamp, serialised as `1790441705167.7627` and
`1790441705167.763`. Any machine with Node installed failed the parity gate on
a field unrelated to any change. Both now emit **whole milliseconds from
nanoseconds** (`st_mtime_ns // 1_000_000` and `mtimeNs / 1000000n`), so the
two writers emit identical bytes.

**Verification (local)**

* 3 real issues dropped into `content/monthly-magazine/` — one top level, one
  in `english/`, one in `punjabi/` — all three publish (124 sitemap URLs,
  3 document pages, hub cards, archives, search, RSS).
* Deliberate collision (same file name in `english/` and `punjabi/`): titles
  disambiguated, slugs `-2`, download hrefs nested and percent-encoded;
  removed afterwards.
* Full chain `build_content` → `build_index` → `build_landing_pages` →
  `seo_check` **PASS** → `rich_results_check` **PASS**.
* `node scripts/build-index.mjs` vs `python3 scripts/build_index.py`:
  `data/index.json` and `sitemap.xml` byte-identical apart from the two
  volatile fields the gate already normalises (`generatedAt`, `<lastmod>`).

---

## 41. Multilingual topic architecture — language is UI state

**The bug it fixes.** Punjabi and English copies of a quiz were two unrelated
records: `sikhism-part1-20-mcqs.json` and `sikhism-part1-20-mcqs-punjabi.json`
never met the pairing logic (which only looked inside `English/` and `Punjabi/`
folders), so General Knowledge showed **eight cards for four quizzes**, two
sitemap entries per set, and a reader's language preference was ignored by
anything that had no folder of its own.

**The rule.** One topic, never language-bearing: `topicId` is the file stem with
its language marker stripped. Language lives on the record (`variants`,
`availableLanguages`, `titles`, `counts`) and in the browser as UI state — the
URL stays `quiz?subject=…&topic=…`, so search, bookmarks, XP, progress,
leaderboard and analytics can all key on `topicId` alone.

*Discovery.* A marker is either a folder name (`English/`, `Punjabi/`, …) or a
file-name suffix: the word form from the curated `LANG_WORDS` table
(`-punjabi`, `-english`, `-gurmukhi`, `-hindi`, …) or the generic dotted form —
any 2–3 letter code that is not `pdf`/`txt`/`md`/…, so `topic.ta.json` needs no
table edit. Markers may stack; the dotted code wins.

*Pairing.* Union-find over two keys inside one subject + category: the
marker-stripped stem, and the JSON `topic` + `part` key (which is what links
`…-part1-geography-environment` to `…-part1-punjabi`). A group can never hold
two files of the same language — that guard is what stops grouping from
swallowing a topic instead of pairing it. English is the primary record when it
exists, otherwise the first by `(language, file)`; members are emitted in that
same order so both builders write identical bytes.

*Contract.* `data/quiz-manifest.json` is new: flat, timestamp-free, and
byte-identical from `build_index.py` and `build-index.mjs` (`ci.sh` step 3
diffs it alongside `index.json` and `sitemap.xml`).

*Validation — warnings, never crashes.* Question count, ids, option count and
the resolved answer index are compared per pair; the first disagreement per pair
prints `Translation mismatch: …` and the build still succeeds. It immediately
found a real one: Punjabi Current Affairs part 3 Q16 ordered options 1 and 2 the
other way round — both files content-correct, but `answer: 2` against `answer:
1`, which would flip that question's score the moment a reader switched
language mid-quiz. Fixed in the data (options reordered to match the English
source, wording untouched).

*Front end.* `pickVariantFile()` resolves preferred language → English → first
available → primary file for topic, Daily Challenge and Mock Test alike;
`swapQuizLang()` refuses any translation that would re-point saved answers and
names the reason in the console (`translationMismatch()`); bookmark keys are now
`${topicKey}:${index}` — language-neutral — with prefix tolerance for legacy
keys that carried a snippet of question text; legacy `?topic=…-punjabi` URLs
resolve through a marker-stripping alias; `langBadge()` gained generic labels
plus `{single: true}`, used only by subject cards so home/related markup is
byte-for-byte unchanged.

**The double-count this exposed.** A subject's `topics` list already holds its
categorized topics (they are *also* listed under `categories[].topics`). With
General Knowledge empty that shape had never been exercised, so four consumers
walked **both** lists and counted every categorized quiz twice:

| Where | Symptom |
| --- | --- |
| `build_landing_pages.py::all_topics` | two landing pages per quiz → "landing pages share title" |
| `seo_check.py` exam → topic derivation | wrong candidate set |
| `build_content.py::subject_strip` | "8 sets" where 4 exist |
| `related.js` related-quizzes rail | every card listed twice |

All four now walk the flat list once and attach the category each record
declares. The silo gate was then realigned with the real hierarchy: a subject
page links its *direct* children (categories + top-level topics) and a new
**Category → Topic** rule proves each categorized topic page is linked from its
category — so `topic-gk-sikhism-*` pages are verified reachable rather than
demanded twice.

**Type checking.** `jsconfig.json` + `// @ts-check` on `core.js`, `quiz.js` and
`subject.js`, with `assets/js/hoa-types.d.ts` describing the `window.HOA` /
`gtag` / `dataLayer` globals. Annotations only — no bundler, no transpile, no
deploy change — and `npm run typecheck` / `ci.sh` step 4 enforce it. 56 errors
resolved down to zero; it also caught two duplicate keys in the Punjabi
dictionary (`Expected MCQs`, `Personal Notes`) where the later entry silently
won.

**Verification (local)**

* `bash scripts/ci.sh` **green (7/7)**: content, manifest, Python↔Node parity
  (index + quiz-manifest + sitemap), type check, landing pages, `seo_check`
  **PASS**, `rich_results_check` **PASS**, committed tree matches builders.
* Manifest: 9 topics, 17 translations — GK now 4 topics (`en` + `pa` each),
  current affairs 4, computer 1; search returns 4 Sikhism quizzes, not 8.
* Sitemap 124 → 132 URLs: eight new clean canonicals
  (`quiz-gk-sikhism-part1…4`, `topic-gk-sikhism-part1…4`), no query strings.

## 42. PDF inventory on the manifest — the scanner reads, the publisher writes

**Problem.** §39 made a PDF publishable, but *discovery* still lived inside
`build_content.py`: the publisher opened every collection folder itself
(`cdir.rglob`) and decided what was there as a side effect of rendering. The
requirement moved one step further — the site must read **only** a generated
inventory: drop a file into a supported `content/` folder and its metadata
(filename, title, slug, category, size, modified date) is derived and
published; delete or rename it and the pages follow — with no HTML, no JS and
no hand-edited manifest anywhere.

**Design.** Discovery became its own dependency-free TypeScript builder
(`type: module`, plain `node`, type-stripped — no bundler, no transpile, no
install), and the publisher became a pure reader:

| step | command | reads | writes |
|---|---|---|---|
| 1. scan | `node scripts/build_content_manifest.ts` | `content/**` (every `.pdf`; hidden folders, `_drafts`, `README*` skipped) + `data/pdf-meta.json` | `drops[]` in `data/content-manifest.json`, stamped `data/pdf-meta.json` |
| 2. publish | `python3 scripts/build_content.py` | `drops[]` + the Markdown | every page, sitemap, search, feed, and the same manifest (now `version: 3`, `drops` carried through verbatim) |
| 3. verify | `… --check` and `scripts/seo_check.py` | manifest vs disk | — |

One record per PDF — `path, filename, folder, category, title, slug,
language, scripts, size, sizeLabel, published, modified` — and:

* **The publisher never walks a folder.** `drops` is the only list, so a file
  the scanner has not seen cannot half-publish, and a `drops` entry pointing at
  nothing stops the build with the command that fixes it.
* **Derivation parity is a gate, not a hope.** The same helpers exist in both
  languages; `ci.sh` step 1 feeds a 20-name fixture list (English, Punjabi,
  mixed, dated, acronym, punctuation-only, malformed dates) to `--derive` in
  TypeScript and to Python, and diffs the JSON — before any page renders.
* **Gurmukhi, in both implementations.** The word-split class gained
  `\u0A00-\u0A7F` (byte-identical for Latin names), a Gurmukhi word keeps its
  own shape in a title, and a transliteration table — plus the rule that a
  nasal carries its syllable's inherent vowel (`ਪੰ` = p + a + n) — turns
  `ਪੰਜਾਬੀ ਨੋਟ.pdf` into the slug `panjabi-not`, where Python used to return an
  empty slug and fall back to a numbered placeholder. `asciiFold()` runs before
  every `\b` regex so Python's Unicode-aware and JavaScript's ASCII boundary
  semantics mean the same thing.
* **Language is inventory data, not a route.** `language` (`en`/`pa`) and
  `scripts` (`latin`/`gurmukhi`/`mixed`/`none`) describe the file for the
  inventory and its gates; the page still publishes at the root as §39 designed
  it, so no design, routing or language-switch change entered the site —
  backend architecture only.
* **Dates stay stamped, never measured.** `published`/`modified` are written
  once per content hash; an mtime in a committed file would fail the tree gate
  on every fresh checkout.
* **Unsupported folders fail loudly.** A drop outside the `HUBS` table produces
  an actionable error and nothing is written; `seo_check.py` re-checks the
  inventory (field shape, slug and date patterns, size label, file on disk,
  every drop published), so a hand-edited manifest cannot pass either.

**Verification (local)**

* Stale inventory: drop a file, run `--check` → exit 1 with
  `+ content/notes/… (new on disk, not in the manifest)` and the command to fix.
* Punjabi drop → `note-panjabi-taist-2026-09-15.html`,
  `<title>ਪੰਜਾਬੀ ਟੈਸਟ 2026-09-15</title>`, slug `panjabi-taist-2026-09-15`,
  `language: pa`, `scripts: gurmukhi`, `published` `2026-09-15` taken from the
  name, and listed in the sitemap (133 URLs while the drop existed).
* Rename (the transliteration fix changed the slug) → the orphan sweep removed
  the old page: `⚠ stale content pages removed: note-pnjabi-taist-….html`.
* Delete → `2 file(s) described`, the page and the manifest drop both gone.
* Unsupported folder → `❌ content/random-folder/stray.pdf: … is not a
  registered collection - add it to HUBS …` and `content build FAILED - no
  files were written`.
* Gates: `node scripts/build_content_manifest.ts` → `build_content.py` →
  `--check` → derivation parity (20 names) → `build_index.py` → Python↔Node
  manifest parity → type check → `build_landing_pages.py` → `seo_check`
  **PASS** (note: *content: 2 PDF drop(s) described by the scanner's inventory
  and published*) → `rich_results_check` **PASS** → committed tree matches the
  builders.

## 43. Reading the PDF itself — summary, preview, LearningResource, related

**Problem.** §42 made the *name* authoritative, and a name can only say so
much. A page built from `five year plan (english).pdf` could not say how long
the file is, what is inside it, or what page one even looks like: the reader
landed on a Download button and a description assembled from the title and
the folder label.

**Design.** The scanner opened each file a second time — while it was already
reading it — and the publisher consumed what it found:

| field | read out of the PDF | used by |
|---|---|---|
| `pages` | the page count the file declares (`/Count`, with a raw `/Type /Page` count as fallback) | the *Pages* bullet, `2.0 MB, 11 pages` on the Download line |
| `summary` | the first of the first three pages that reads like prose, clipped to 300 chars | `## Summary`, the search row `m`, the JSON-LD `abstract` |
| `thumbnail` + `thumbW` / `thumbH` | a JPEG of page one at `assets/img/pdf/<sha256[:12]>.jpg` (`/usr/bin/sips`, `qlmanage` fallback), dimensions read back out of the bytes | the `<img>` at the top of the body |

* **Text extraction is a decoder, not a guess.** Each text object is looked
  up inside its own `endobj` bound; per-font `/ToUnicode` CMaps are parsed for
  both `bfchar` and `bfrange` against the codespace width; ligatures are
  spelled out; and the Gurmukhi pre-base matra is put back where the script
  writes it, because the file stores glyphs in visual order.
* **Run separators come from geometry.** Every drawn string carries the
  translation of its `cm` *and* its `Tm`; a space is emitted only when the
  baseline moves more than half the font size (a new line) or when the last
  character ended a sentence (`. , ; : ! ? ) ]`). Ligature runs and Punjabi's
  explicit space glyphs therefore neither gain nor lose a word:
  `ef fi cient` → `efficient`, `for. Thank` stays two words, and
  `(Cell Phone)` no longer becomes `( Cell Phone)`.
* **The welcome page is matched on its opening only.** Every page carries
  `House of Aspirants` in its footer, so a whole-page match marked every page
  as front matter and the summary always fell back to page 1. The brand test
  now runs on the first ~90 characters, so page 1 is front matter and page 2
  is content.
* **A glyph the file itself does not know.** The Gurmukhi PDFs ship
  `/ToUnicode` entries that map a code to its own ASCII character
  (`<3d><3d><003d>`) — the producer's placeholder for "unknown glyph". The
  embedded `FontFile2` still carries a `cmap` (formats 0/4/6/12) and a
  format-2 `post`, so the scanner reads the glyph's *name*
  (`MatraIiBindi.gm`), learns each font's name→Unicode map from the codes the
  file does know, splits a compound name by longest-prefix match, and inserts
  U+0A4D (halant) between two consonants. `ਵਰਤ=` becomes `ਵਰਤੋਂ`, `RaHa.gm`
  becomes `ਰ੍ਹ`. A code with no witness is left exactly as the file says —
  the repair only ever improves an answer it can prove.
* **Previews are a cache, not an output.** They are drawn only inside
  `write()` (never under `--check`, which must stay a pure read), named by
  content hash so an unchanged file keeps its bytes, and swept when no drop
  points at them anymore. Linux CI has no `sips`/`qlmanage`, so the path is
  computed from the committed file's existence and both machines emit the
  same bytes.

**On the page.** The preview is prepended to `bodyHtml` through one helper
used by both the first build and any later re-render, reusing the existing
`.doc-cover` box — so the layout does not move — with `alt` / `width` /
`height` / `decoding` and an inline `aspect-ratio`. A **Related PDFs**
`rec-group` is prepended in `recommend_sections`, built from the same
`card_html` every other slot uses: candidates are PDF drops that publish a
page, ranked own-folder → own collection → anywhere else, three at most, with
`(href, "related-pdf")` edges recorded in the content graph. A
`LearningResource` node is inserted at `nodes.insert(1, …)` for every
`pdfDrop`, carrying `learningResourceType: "PDF"`, `encoding` typed
`["DataDownload", "MediaObject"]` (the second type is the one `contentUrl` is
actually declared on), the preview as `image` and the summary as `abstract`.
No `numberOfPages`: schema.org scopes that property to `Book`, and a property
the gates cannot verify would be worse than none.

**Verification (local)**

* `bash scripts/ci.sh` → steps 1/7 through 6/7 green; step 7 fails only
  because it diffs the working tree against `HEAD` (the regenerated files are
  not committed yet).
* Summaries, verbatim from `data/content-manifest.json`:
  * `FIVE YEAR PLANS (1951–2017) Introduction Economic Planning refers to the systematic and efficient utilization of a country's available resources …`
  * `FIVE YEAR PLANS ( ਪੰਜ ਸਾਲਾ ਯੋਜਨਾਵਾਂ) Introduction ਆਰਥਿਕ ਯੋਜਨਾ (Economic Planning) ਦਾ ਅਰਥ ਹੈ … ਦੀ ਪ੍ਰਭਾਵਸ਼ਾਲੀ ਵਰਤੋਂ ਕਰਕੇ ਲੰਬੇ ਸਮੇਂ ਲਈ …`
  * `MOBILE PHONES (CELLULAR PHONES) A Mobile Phone (Cell Phone) is an electronic communication device …`
  * page counts 18 / 11 / 11 / 18; three previews written (450×600 JPEG,
    57–67 KB) — the fourth drop is byte-identical to another, so it reuses
    the same hash.
* `seo_check` → *content: 4 PDF drop(s) described by the scanner's inventory
  and published*, schema line including `LearningResourcex7`, `DataDownloadx3`,
  `MediaObjectx3`, **RESULT: PASS — no hard failures**; `rich_results_check`
  → **RESULT: PASS**. `index.html` markers still 3× `Gurpreet Singh`, 1×
  `Prepare Smarter`, 4× `t.me/HouseOfAspirant`; `404.html` still carries zero
  `<script type="application/ld+json">`.
