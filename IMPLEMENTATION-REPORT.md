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
