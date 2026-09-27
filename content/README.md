# content/ — the Markdown source of truth

House of Aspirants has no CMS. Every note, current affairs article, magazine
issue, strategy guide, live session, recruitment record, blog post, news item,
announcement and PDF listing on this site is a Markdown file in this folder,
reviewed in Git and rendered to static HTML by `scripts/build_content.py`.

```
content/<collection>/<slug>.md     ──►  <prefix>-<slug>.html        (English, site root)
content/<collection>/<slug>.pa.md  ──►  pa/<prefix>-<slug>.html     (Punjabi edition)
                                     ──►  data/content-manifest.json  (Content Index)
                                     ──►  data/search-index.json      (full-site search)
                                     ──►  feed.xml                    (RSS 2.0)
                                     ──►  archives.html               (subject/exam/month)
                                     ──►  sitemap.xml + homepage feed blocks
                                     ──►  the generated nav blocks in assets/js/core.js
```

## Commands

```bash
python3 scripts/build_content.py            # build pages + manifest + homepage
python3 scripts/build_content.py --strict   # warnings fail the build
bash scripts/ci.sh                          # full gate (build + checks + drift)
```

Nothing is written to disk until every file validates, so a broken document
fails the build without leaving half-built pages behind.

## Front matter

Every file starts with a `---` fenced block. The parser understands a small,
deliberate YAML subset (no dependencies):

| syntax | meaning |
| --- | --- |
| `key: value` | string (`true`/`false` → boolean, digits → int) |
| `key: "a, b"` | quoted string (commas allowed) |
| `key: [a, b]` | inline list |
| `key:` + `- item` lines | block list |
| `key:` + `- k: v` lines | list of one-level mappings |
| `key: \|` + indented lines | single-paragraph literal block |

Raw HTML inside Markdown is escaped, never passed through — a document cannot
break the page or inject markup.

### Fields every collection shares

| field | required | rules |
| --- | --- | --- |
| `title` | yes | **max 60 characters** (page `<title>`, H1, schema headline) |
| `description` | yes | **140–160 characters** (meta description, OG, quick-answer box) |
| `published` | yes* | `YYYY-MM-DD` — drives sort order, RSS `pubDate` and `datePublished` |
| `updated` | no | `YYYY-MM-DD` — falls back to `published` for `dateModified` |
| `language` | no | `en` or `pa`; must match the file variant (`.md` = en, `.pa.md` = pa) |
| `author` | no | defaults to *House of Aspirants Editorial Team* (brand only) |
| `reviewedBy` | no | shown in the byline row (max 60 chars) |
| `category` | no | editorial section label; also searched |
| `subject` / `subjects` | no | subject id(s) from `data/subjects.json` |
| `exam` / `exams` | no | exam name(s) shown as badges and indexed for search |
| `tags` | no | free-form topic tags (also drive Related Notes) |
| `difficulty` | no | shown as a badge |
| `readingTime` | no | whole minutes — overrides the computed 200-wpm estimate |
| `coverImage` | no | alias of `cover`; the Download/cover button only appears if the file exists |
| `quiz` | no | linked quiz JSON — powers the "Related quiz" chain step |
| `pdf` | no | `assets/pdfs/…` path; the Download button appears only if the file exists |
| `slug` | no | override the filename-derived slug (lowercase, digits, hyphens) |
| `featured` | no | `true` renders an honest Featured badge; it never invents popularity |
| `draft` | no | `true` → validated but published **nowhere** (pages, sitemap, feed, search, archives) |

\* `pdfs/` records only need `title`, `description` and `file`.

Unknown keys raise a warning (catches typos); missing required keys fail the
build.

## Collections

| folder | page prefix | hub | extra required fields |
| --- | --- | --- | --- |
| `notes/` | `note-` | `study-notes.html` | `subject` |
| `current-affairs/` | `ca-` | `current-affairs.html` | — |
| `monthly-magazine/` | `magazine-` | `magazine.html` | `month` (`YYYY-MM`) |
| `strategy/` | `strategy-` | `strategy.html` | `category` |
| `live-sessions/` | `session-` | `live-sessions.html` | `date` |
| `recruitment/` | `recruit-` | `recruitment.html` | `post`, `official_url` |
| `blogs/` | `blog-` | `blogs.html` | — |
| `news/` | `news-` | `news.html` | — |
| `announcements/` | `announce-` | `announcements.html` | — |
| `pdfs/` | — (registry) | `pdfs.html` | `file` |

Optional, collection-specific fields (see `REQUIRED_FIELDS` /
`OPTIONAL_FIELDS` in `scripts/build_content.py`):

* **monthly-magazine** — `pdf`, `quiz`, `highlights` (bullet list rendered as
  its own section), `cover`
* **strategy** — `category`, `difficulty`
* **live-sessions** — `time`, `start_time` (24h `HH:MM`, enables Event schema),
  `platform`, `join`, `status` (`upcoming` | `past`), `questions`, `doubts`
* **recruitment** — `exam` (links the matching `exam-*.html` guide),
  `official_source`, `eligibility`, `syllabus`, `selection`, `dates`,
  `expected_questions`, `previous_papers`
* **news** — `official_url` (same official-source rule as recruitment)
* **announcements** — `join` (Telegram/live link, https only)
* **pdfs** — `subject`, `exams`, `tags`, `note`

## Language URLs — English at the root, Punjabi under `/pa/`

Add `<slug>.pa.md` next to `<slug>.md`. It carries **its own** front matter —
Gurmukhi `title` and `description` (same length rules) — and its own body.

| edition | URL |
| --- | --- |
| English | `https://houseofaspirants.in/<prefix>-<slug>` |
| Punjabi | `https://houseofaspirants.in/pa/<prefix>-<slug>` |

Both pages ship a reciprocal `hreflang` pair, a language badge, and the Punjabi
page sets `<base href="/">` so the shared header, drawer and footer keep
resolving from the site root. `seo_check.py` fails the build if the pair stops
cross-linking or a Punjabi page publishes outside `/pa/`.

## What every build regenerates

* **Navigation** — the Study menu, the drawer Study group and the footer Study
  column are written between `<!-- HOA-NAV:* -->` markers in
  `assets/js/core.js` from the `HUBS` table. Adding a folder here adds it to
  the header, drawer, footer, sitemap and search index in the same run; nobody
  edits HTML or JS by hand.
* **Content Index** — `data/content-manifest.json` (hubs, index pages, every
  document with its language pair, category, author and reading time). It feeds
  the sitemap, the archive page and the SEO gates.
* **Full-site search** — `data/search-index.json`: title, description, body,
  tags, subjects, exams and category for every document, study guide and exam
  page. The search overlay fetches it lazily on first open, so page load never
  waits for it.
* **RSS** — `feed.xml`, RSS 2.0, newest 20 documents, dates derived from
  `published` only (rebuilding emits byte-identical XML).
* **Archive** — `archives.html`: latest posts, popular posts (only when
  `data/popularity.json` carries real counts), and every document grouped by
  subject, exam and month.
* **Homepage** feed blocks, sitemap entry, stale-page cleanup (including the
  `pa/` folder).

## Hard rules (enforced by the build)

1. **No invented content.** Fields you do not fill in are not rendered. Empty
   collections publish an honest empty state, never placeholder articles.
2. **Recruitment = official sources only.** `official_url` must be a
   `.gov.in` / `.nic.in` domain (or pspcl.co.in). Anything else fails the build.
   Dates, vacancies and admit cards are only restated from that notification.
3. **Expected Questions / Previous Papers stay off** until verifiable data
   exists. They appear as dimmed *reserved* steps in the learning path and are
   never linked; nothing renders and nothing is promised.
4. **Bylines are brand-only** — no invented person names.
5. **Titles ≤ 60, descriptions 140–160 characters.**
6. **Popularity is measured, not guessed.** `data/popularity.json` ships empty;
   "Popular posts" stays off the archive page until analytics fill it in.
7. **Drafts are validated but never published** — they cannot reach the
   sitemap, feed, search index or archive by accident.

## Templates — eleven page types, one contract (Phase 3)

`scripts/content_engine.py` holds the templates. A template owns four things:
the front matter it requires from its collection, the JSON-LD type it emits,
its table-of-contents rules and its **recommendation plan** — the ordered list
of slots each page renders after the body.

| `--type` key | Page type | Collection | Recommends (in order) |
|---|---|---|---|
| `study-note` | Study Note | `notes/` | the practice set, subject hub, current affairs, expected MCQs, previous papers |
| `current-affairs` | Current Affairs | `current-affairs/` | the practice set, latest magazine issue, related news, government schemes, Punjab GK |
| `monthly-magazine` | Monthly Magazine | `monthly-magazine/` | the practice set, current affairs, previous papers |
| `expected-mcq` | Expected MCQ | `expected-mcqs/` | the practice set, study notes, previous papers |
| `previous-year-question` | Previous Year Question | `previous-year-questions/` | the practice set, study notes, expected MCQs |
| `preparation-strategy` | Preparation Strategy | `strategy/` | the practice set, study notes, free PDFs, latest magazine |
| `motivation` | Motivation Article | `strategy/` | strategy guides, the practice set, live sessions |
| `book-review` | Book Review | `strategy/` | free PDFs, study notes, the practice set |
| `live-session-summary` | Weekly Live Session | `live-sessions/` | study notes, the practice set, strategy guides |
| `recruitment-notification` | Recruitment | `recruitment/` | eligibility, syllabus, strategy, books (PDFs), previous papers, expected questions, live session |
| `exam-analysis` | Exam Analysis | `blogs/` | the practice set, study notes, news |

Three cross-section slots are appended to every plan so no page stops at its
own section: **More &lt;section&gt;** (same collection, shown whenever it has
another document), **Related current affairs** and **Guides worth reading
next**. Study notes additionally carry previous/next chapter links when the
subject has more than one note.

### Recommendations are facets, not filler

Candidates are scored against the page you are reading:

| Facet | Weight | Facet | Weight |
|---|---|---|---|
| shared subject | 6 | difficulty | 2 |
| shared exam | 4 | featured | 2 |
| shared tag | 3 | shared section | 1 |
| shared category | 3 | language | tie-break only |

Language never makes two documents "related" — it only breaks ties between
candidates that already overlap, so a Punjabi reader is served the Punjabi
edition when one exists rather than any random item in the same language.
A slot with no candidate above zero renders nothing; a slot whose data type
the site does not publish at all (previous papers, expected MCQs, news for a
note with no news) renders one dimmed **Reserved** line that explains why.
Nothing is ever linked to a page that does not exist.

### The link floor

Every page must carry **at least five contextual internal links inside
`<main>`**. The builder counts them with the same rule the graph uses, and
appends an "Explore the library" module when a page is short;
`scripts/seo_check.py` re-counts them across all shipped pages and fails the
run if any page (404 excepted) falls below five.

### Topic clusters, silos and the graph

`data/content-graph.json` ships three views of the same tree:

* **nodes** — every hub, document and the archive, with title, type, template,
  language and facets;
* **edges** — the contextual links actually present in the shipped HTML
  (`<main>`), each with a relation label;
* **silos** — one per subject and per exam: pillar (the guide that heads the
  silo) → hub (subject/exam landing page) → clusters (category and cluster
  landing pages) → leaves (documents). A silo with no pillar publishes
  `pillar: null` rather than an invented one.

### Scaffold instead of copying

```bash
python3 scripts/new_content.py --list                 # the 11 templates
python3 scripts/new_content.py --type study-note --slug punjab-history-sikh-period
python3 scripts/new_content.py --type current-affairs --slug july-week-1 --pa
python3 scripts/new_content.py --type study-note --slug x --stdout   # print only
```

Scaffolds land in `content/_drafts/`, which the builder never loads: an
unfinished file with placeholder text cannot reach a page, the sitemap, the
feed or the search index. Fill the placeholders (titles ≤ 60 characters,
descriptions 140–160) and `mv` the file into its collection folder when it is
real.

## Content workflow

1. Write `content/<collection>/<slug>.md` (optionally `<slug>.pa.md`).
   Set `draft: true` to keep it out of every output while you iterate.
2. `python3 scripts/build_content.py` — fixes every validation error locally.
3. `bash scripts/ci.sh` — builds both index builders, the landing set, runs
   `seo_check.py` + `rich_results_check.py` and proves the committed tree is
   exactly what the builders emit.
4. Commit the Markdown **and** the generated HTML + `data/*` (static hosting
   needs the rendered bytes in Git).
5. Push — GitHub Actions runs the same `scripts/ci.sh`.
