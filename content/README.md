# content/ — the Markdown source of truth

House of Aspirants has no CMS. Every note, magazine issue, strategy article,
live session, recruitment record and PDF listing on this site is a Markdown
file in this folder, reviewed in Git and rendered to a static page by
`scripts/build_content.py`.

```
content/<collection>/<slug>.md   ──►  <prefix>-<slug>.html      (one page)
content/<collection>/<slug>.pa.md ──►  <prefix>-<slug>-pa.html  (Punjabi variant)
                                  ──►  data/content-manifest.json
                                  ──►  sitemap.xml + homepage feed blocks
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
| `published` | yes* | `YYYY-MM-DD` — drives sort order and `datePublished` |
| `updated` | no | `YYYY-MM-DD` — falls back to `published` for `dateModified` |
| `author` | no | defaults to *House of Aspirants Editorial Team* |
| `tags` | no | free-form topic tags (also drive Related Notes) |
| `subjects` | no | subject ids from `data/subjects.json` |
| `exams` | no | exam names shown as badges |
| `slug` | no | override the filename-derived slug |
| `pdf` | no | `assets/pdfs/…` path; the Download button appears only if the file exists |

\* `pdfs/` records only need `title`, `description` and `file`.

Unknown keys raise a warning (catches typos); missing required keys fail the
build.

## Collections

| folder | page prefix | hub | extra required fields |
| --- | --- | --- | --- |
| `notes/` | `note-` | `study-notes.html` | `subject` |
| `magazine/` | `magazine-` | `magazine.html` | `month` (`YYYY-MM`) |
| `strategy/` | `strategy-` | `strategy.html` | `category` |
| `sessions/` | `session-` | `live-sessions.html` | `date` |
| `recruitment/` | `recruit-` | `recruitment.html` | `post`, `official_url` |
| `pdfs/` | — (registry) | `pdfs.html` | `file` |

Optional, collection-specific fields (see `REQUIRED_FIELDS` /
`OPTIONAL_FIELDS` in `scripts/build_content.py`):

* **notes** — `difficulty`, `subjects`, `tags`
* **magazine** — `pdf`, `quiz`, `highlights`, `cover`
* **strategy** — `category`, `difficulty`
* **sessions** — `time`, `start_time` (24h `HH:MM`, enables Event schema),
  `platform`, `join`, `status` (`upcoming` | `past`), `questions`, `doubts`
* **recruitment** — `exam` (links the matching `exam-*.html` guide),
  `official_source`, `eligibility`, `syllabus`, `selection`, `dates`,
  `expected_questions`, `previous_papers`
* **pdfs** — `subject`, `exams`, `tags`, `note`

## Punjabi variants (Punjabi first, English always available)

Add `<slug>.pa.md` next to `<slug>.md`. It carries **its own** front matter —
Gurmukhi `title` and `description` (same length rules) — and its own body.
Both pages link to each other with a language badge.

## Automatic on every page

SEO title/description/canonical, Open Graph + Twitter cards, JSON-LD
(`Article` + `WebPage`, `Event` for sessions with `start_time`, `CollectionPage`
+ `ItemList` on hubs, `BreadcrumbList` everywhere), breadcrumb, table of
contents, reading time, difficulty/exam badges, related notes, related quizzes,
previous/next navigation, share buttons, PDF download button when a real file
exists, and homepage feed blocks.

## Hard rules (enforced by the build)

1. **No invented content.** Fields you do not fill in are not rendered. Empty
   collections publish an honest empty state, never placeholder articles.
2. **Recruitment = official sources only.** `official_url` must be a
   `.gov.in` / `.nic.in` domain (or pspcl.co.in). Anything else fails the build.
   Dates, vacancies and admit cards are only restated from that notification.
3. **Expected Questions / Previous Papers stay off** until verifiable data
   exists. The fields are schema-ready; leave them out until then.
4. **Bylines are brand-only** — no invented person names.
5. **Titles ≤ 60, descriptions 140–160 characters.**

## Future content workflow

1. Write `content/<collection>/<slug>.md` (optionally `<slug>.pa.md`).
2. `python3 scripts/build_content.py` — fixes every validation error locally.
3. `bash scripts/ci.sh` — builds both index builders, the landing set, runs
   `seo_check.py` + `rich_results_check.py` and proves the committed tree is
   exactly what the builders emit.
4. Commit the Markdown **and** the generated HTML + `data/content-manifest.json`
   (static hosting needs the rendered bytes in Git).
5. Push — GitHub Actions runs the same `scripts/ci.sh`.
