# content/ — the Markdown source of truth

House of Aspirants has no CMS. Every note, current affairs article, magazine
issue, strategy guide, live session, recruitment record, blog post, news item,
announcement, PDF listing, personal note, subject guide, topic guide, daily
practice set, success story and book recommendation on this site is a Markdown
file in this folder, reviewed in Git and rendered to static HTML by
`scripts/build_content.py` — and a PDF dropped into the same folder publishes
from its file name alone (see **PDF drops** below).

```
content/<collection>/<slug>.md     ──►  <prefix>-<slug>.html        (English, site root)
content/<collection>/<slug>.pa.md  ──►  pa/<prefix>-<slug>.html     (Punjabi edition)
content/<collection>/<file>.pdf    ──►  <prefix>-<slug>.html        (PDF drop)
                                     ──►  data/content-manifest.json  (Content Index)
                                     ──►  data/search-index.json      (full-site search)
                                     ──►  feed.xml                    (RSS 2.0)
                                     ──►  archives.html               (subject/exam/month)
                                     ──►  archive-tag-*.html          (taxonomy, Phase 4)
                                     ──►  archive-category-*.html     (taxonomy, Phase 4)
                                     ──►  author-<id>.html            (byline profile, Phase 4)
                                     ──►  search.html                 (crawlable search, Phase 4)
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
| `author` | no | must exist in `data/authors.json` (defaults to *House of Aspirants Editorial Team*) |
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

### The full platform content model (Phase 4)

Everything the platform brief asks for is a **first-class, optional** field on
every document. It is rendered only when you fill it in — an unfilled field
never becomes placeholder text.

| field | rules | what it drives |
| --- | --- | --- |
| `subtitle` | ≤ 120 chars | hero subtitle under the H1 |
| `summary` | ≤ 320 chars | answer box, cards, the `m` search field, feed blurb |
| `seoTitle` | 40–60 chars | `<title>` + OG/Twitter title (falls back to `title`) |
| `seoDescription` | 140–160 chars | meta description + OG description |
| `keywords` | ≤ 12 entries, ≤ 48 chars each | meta keywords **and** the JSON-LD `keywords` |
| `toc` | `true` / `false` | table of contents (`true` = hide, headings are always parsed) |
| `relatedContent` | list of hub names or page files | the *Related reading* module; a target that does not exist is skipped, never linked |
| `telegramLink` / `youtubeLink` | `https://` only | the two action buttons in the hero |
| `references` | `- title:` + `url:` (or a plain line) | *Sources* list (E-E-A-T evidence) |
| `faq` | `- q:` / `a:` pairs | FAQ section **and** a real `FAQPage` JSON-LD node |
| `schemaType` | `Article` \| `BlogPosting` \| `NewsArticle` \| `WebPage` | the JSON-LD type of the document |
| `status` | `published` \| `draft` \| `archived` (+ `upcoming`/`past`/`held` for sessions) | `draft`/`archived` publish nowhere |
| `thumbnail` | existing file or `https://` | `og:image` / `twitter:image` (falls back to the site OG image) |
| `id` | stable string | identity used by the manifest and the graph |

**Aliases** are accepted and normalised before validation, so the brief's
spelling and this builder's key always mean the same thing:

| you can write | which is read as |
| --- | --- |
| `publishDate` | `published` |
| `updatedDate` | `updated` |
| `examTags` | `exams` |
| `relatedQuiz` | `quiz` |
| `downloadPDF` | `pdf` |
| `tableOfContents` | `toc` |
| `coverImage` | `cover` |

**Bylines are a registry, not free text.** `data/authors.json` lists who may
sign a document; an `author:` value that is not in it fails the build. An
entry with `"profile": true` gets a generated `author-<id>.html` page
(`@type: ProfilePage`), every document signed with it links that page, and
the JSON-LD `author` node becomes a `Person` pointing at it. Entries with
`"profile": false` stay an `Organization` node behind `/about` — they have no
page, because nothing links to a person the site cannot introduce.

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
| `personal-notes/` | `pnote-` | `personal-notes.html` | `subject` |
| `subject-guides/` | `sguide-` | `subject-guides.html` | `subject` |
| `topic-guides/` | `tguide-` | `topic-guides.html` | `subject` |
| `daily-practice/` | `practice-` | `daily-practice.html` | `subject` |
| `success-stories/` | `story-` | `success-stories.html` | `exam` |
| `book-recommendations/` | `book-` | `book-recommendations.html` | `subject` |

(Those six are the Phase 4 collections; every one of them has its own folder,
hub page, navigation entry, sitemap entry, search record and filter bar.)

Optional, collection-specific fields (see `REQUIRED_FIELDS` /
`OPTIONAL_FIELDS` in `scripts/build_content.py`):

* **monthly-magazine** — `pdf`, `quiz`, `highlights` (bullet list rendered as
  its own section), `important_questions`, `revision_notes`, `cover`
* **strategy** — `category`, `difficulty`
* **live-sessions** — `time`, `start_time` (24h `HH:MM`, enables Event schema),
  `platform`, `join`, `status` (`upcoming` | `past`), `poster` (640×360),
  `recording`, `resources` (https URL or site path), `questions`, `doubts`,
  `summary`
* **recruitment** — `exam` (links the matching `exam-*.html` guide),
  `official_source`, `eligibility`, `syllabus`, `selection`, `dates`,
  `expected_questions`, `previous_papers`
* **news** — `official_url` (same official-source rule as recruitment)
* **announcements** — `join` (Telegram/live link, https only)
* **pdfs** — `subject`, `exams`, `tags`, `note`
* **success-stories** — `exam` (required), `tags`, `references`, `faq`
* **book-recommendations** — `book`, `book_author`, `publisher`
* **topic-guides** — `topic`; **daily-practice** — `quiz` (the set to attempt)
* **blogs** — `category` must normalise (spaces/underscores → hyphens) to one
  of the eight subtypes: `preparation-experience`, `study-plans`,
  `time-management`, `motivation`, `book-reviews`, `mistakes`,
  `strategy-articles`, `exam-analysis`

## PDF drops — a PDF alone is enough

A PDF placed in any collection folder is a document. No Markdown, no front
matter, no scaffold:

```
content/monthly-magazine/Current Affairs July 2026.pdf
    ──►  magazine-current-affairs-july-2026.html   (page in its collection hub)
    ──►  data/content-manifest.json + data/search-index.json + feed.xml
    ──►  archives.html, sitemap.xml, the homepage feed, the nav
```

Everything the site needs is derived from the file name:

| field | from the file name |
| --- | --- |
| `title` | `Current Affairs July 2026.pdf` → *Current Affairs July 2026* (title-cased, acronyms such as PPSC/SI/PYQ kept, cut to the site's 60-character limit) |
| `slug` | `current-affairs-july-2026` (the same lowercase-hyphen rule every document follows; a clash gets `-2`, `-3`, never a failed build) |
| `description` | assembled from the title and the collection label, always inside the site's 140–160 character window |
| `date` | `2026-08-12`, `July 2026`, `2026-07` in the name wins; otherwise the date the PDF first appeared, remembered in `data/pdf-meta.json` so a rebuild on another machine emits the same bytes |
| `download URL` | the file itself, percent-encoded (`content/pdfs/Punjab%20GK%20Sheet.pdf`) |

The record then enters exactly the pipeline a Markdown document does: hub card,
doc page with a Download button, archives, search corpus (with summary,
keywords and author), RSS, sitemap, content graph, homepage feed.

Rules worth knowing:

* **Subfolders count** — `content/monthly-magazine/english/CA August.pdf`
  publishes exactly like a top-level drop: the builder walks the collection
  folder (only hidden folders and `_drafts` are skipped). When two files in
  sibling folders would take the same title, the folder names them —
  *Current Affairs Sheet* / *Current Affairs Sheet (Punjabi)* — instead of
  inventing a subject.
* **`<name>.pdf` next to `<name>.md`** — the PDF becomes that document's
  download instead of a second page (one file, one URL).
* **`content/pdfs/`** — the registry hub has no pages: the PDF is listed on
  `pdfs.html` with its download button, nothing else is generated.
* **Required collection fields are relaxed** — a dropped PDF cannot invent a
  `subject`, `post` or `official_url`. What the name does carry is used (a
  magazine PDF named `… July 2026.pdf` gets `month: 2026-07`), everything else
  is simply absent and the page leads with *PDF download* instead.
* **English only** — there is no `.pa.md` twin to derive, so a dropped PDF
  publishes at the site root and the language switch stays honest.
* **Drafts are not a PDF concept** — anything in a collection folder is
  published; `content/_drafts/` is still never read.

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
  page, plus the Phase 4 fields `m` (summary), `w` (keywords), `a` (author) and
  `f` (difficulty) on each document row. The search overlay and `search.html`
  fetch it lazily on first open, so page load never waits for it.
* **Generated index pages** — `author-<id>.html` (every profiled author),
  `archive-tag-<slug>.html` and `archive-category-<slug>.html` (only when a
  document really carries the tag) and `search.html`. All four are registered
  in the manifest, so the sitemap, canonical URLs and the chrome checks cover
  them in the same run, and each is removed again when the last document that
  justified it disappears.
* **Taxonomy links** — every tag badge on a document links its archive page,
  and `archives.html` lists every tag and category page under *Browse by tag*
  / *Browse by category*. Nothing that exists is reachable only from the
  footer.
* **Filter bars** — a listing with more than one document and more than one
  value in some facet (Exam, Subject, Language, Difficulty, Date, Category)
  renders a chip bar; `assets/js/content.js` filters locally (OR inside a
  facet, AND across facets), with no request and no re-render.
* **RSS** — `feed.xml`, RSS 2.0, newest 20 documents, dates derived from
  `published` only (rebuilding emits byte-identical XML).
* **Archive** — `archives.html`: latest posts, popular posts (only when
  `data/popularity.json` carries real counts), and every document grouped by
  subject, exam and month.
* **Homepage** feed blocks, sitemap entry, stale-page cleanup (including the
  `pa/` folder and any generated page nobody produces any more).

## Hard rules (enforced by the build)

1. **No invented content.** Fields you do not fill in are not rendered. Empty
   collections publish an honest empty state, never placeholder articles.
2. **Recruitment = official sources only.** `official_url` must be a
   `.gov.in` / `.nic.in` domain (or pspcl.co.in). Anything else fails the build.
   Dates, vacancies and admit cards are only restated from that notification.
3. **Expected Questions / Previous Papers stay off** until verifiable data
   exists. They appear as dimmed *reserved* steps in the learning path and are
   never linked; nothing renders and nothing is promised.
4. **Bylines are registered authors only** — `data/authors.json` decides who
   signs a document; an unknown name fails the build. The profile itself is
   written once, in that file, never invented per article.
5. **Titles ≤ 60, descriptions 140–160 characters.**
6. **Popularity is measured, not guessed.** `data/popularity.json` ships empty;
   "Popular posts" stays off the archive page until analytics fill it in.
7. **Drafts are validated but never published** — they cannot reach the
   sitemap, feed, search index or archive by accident.

## Templates — seventeen page types, one contract (Phase 3 + 4)

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
| `personal-note` | Personal Note | `personal-notes/` | practice quiz, related subject, related notes, related articles |
| `subject-guide` | Subject Guide | `subject-guides/` | subject hub, practice quiz, study notes, preparation strategy |
| `topic-guide` | Topic Guide | `topic-guides/` | practice quiz, related subject, study notes, expected MCQs (reserved) |
| `daily-practice` | Daily Practice | `daily-practice/` | practice quiz, yesterday's practice, related subject, study notes |
| `success-story` | Success Story | `success-stories/` | preparation strategy, study notes, practice quiz |
| `book-recommend` | Book Recommendation | `book-recommendations/` | study notes, free PDFs, practice quiz, preparation strategy |

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
python3 scripts/new_content.py --list                 # the 17 templates + their hub
python3 scripts/new_content.py --type study-note --slug punjab-history-sikh-period
python3 scripts/new_content.py --type personal-note --slug revision-loop
python3 scripts/new_content.py --type success-story --slug first-attempt --pa  # EN + PA pair
python3 scripts/new_content.py --type study-note --slug x --stdout   # print only
```

Scaffolds land in `content/_drafts/`, which the builder never loads: an
unfinished file with placeholder text cannot reach a page, the sitemap, the
feed or the search index. Each stub is **valid the moment it is moved** — it
carries a working value for every field its collection requires (publish date,
subject, exam, category… with a comment saying what to replace), so the build
tells you about the writing, not about missing keys. `--pa` writes the Punjabi
edition **and** the English original it is paired with, because the builder
refuses a `.pa.md` with no source document. Fill the placeholders (titles ≤ 60
characters, descriptions 140–160) and `mv` the files into their collection
folder when they are real.

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
