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
