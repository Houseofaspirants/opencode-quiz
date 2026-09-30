# Study Material — drop files here, nothing else

This folder is the **only** place study material lives. The folders *are* the
registration: there is no list to edit, no page to write and no index to update.

```
content/study-material/
├── metadata.json                     ← optional subject registry (icon, colour, blurb)
├── computer/
│   ├── README.md                     ← ignored by the build
│   ├── metadata.json                 ← optional per-file overrides
│   ├── english/
│   │   └── fundamentals-of-computer/
│   │       └── fundamentals-of-computer.pdf
│   └── punjabi/
│       └── fundamentals-of-computer/
│           └── fundamentals-of-computer-punjabi.pdf
├── history/
│   ├── english/
│   │   └── arrival-of-europeans/
│   │       ├── part-1-english-en.pdf
│   │       ├── part-2-english-en.pdf
│   │       └── part-3-english.pdf
│   └── punjabi/
│       └── arrival-of-europeans/
│           └── ...
├── english/
├── punjabi/
├── reasoning/
├── quant/
├── gk/
├── current-affairs/
├── economy/
├── geography/
├── polity/
├── science/
└── miscellaneous/
```

**Four levels: subject → language → chapter → part.** That is the whole
hierarchy the site renders:

| You create | The reader sees |
|---|---|
| `content/study-material/<subject>/` | a subject card on Study |
| `<subject>/<language>/` | a language card when they open that subject — **before** anything else |
| `<subject>/<language>/<chapter>/` | a chapter in that language's list |
| `<subject>/<language>/<chapter>/<file>` | a part, in reading order |

Nothing else appears at any step. A subject with no folder yet still shows its
language cards, saying plainly that there is nothing filed yet.

### Adding things

| You want | You do |
|---|---|
| a new subject | `mkdir content/study-material/history` |
| a new language | `mkdir content/study-material/history/urdu` |
| a new chapter | `mkdir content/study-material/history/english/medieval-history` |
| a new part | copy the file into that chapter folder |

Then `npm run publish`. That is the whole workflow — no subject list, no
language list, no chapter list, no manual edit to `subjects.json`,
`index.json`, `content-manifest.json`, `pages.json` or `search-index.json`.
All five are generated.

Languages are **discovered from the folder names**, so `english/` is English,
`punjabi/`, `panjabi/`, `gurmukhi/` and `ਪੰਜਾਬੀ/` are all Punjabi, and a folder
this site has never seen (`urdu/`, `hindi/`) becomes a language of its own with
its folder name as its display name. No code changes.

## Publish

```bash
npm run publish
```

`scripts/build_content_manifest.ts` scans the files, `scripts/build_content.py`
derives every field and renders the pages, `scripts/study_material.py` writes
the language → chapter → part tree into `data/study-manifest.json`, and the
build fills `data/content-manifest.json`, `data/search-index.json`, the sitemap
and the Study registry. Nothing is hand-registered.

## Supported files

| Extension | What happens |
|---|---|
| `.pdf`   | Scanned, described from the folder it sits in and its name, published as `material-<slug>.html` with Read Online and Download. Page count and the first-page summary are read out of the file itself. |
| `.md`    | Markdown with optional front matter. Published as `material-<slug>.html`. |
| `.json`  | A structured record. Published as `material-<slug>.html`. |
| anything else | Ignored (never fails the build). |

`README.md`, every hidden file or folder and every `_`-prefixed folder are
ignored. A file at the collection root (this README, `metadata.json`) is
configuration and publishes nothing.

## What is derived for you (Step 4)

Nothing has to be written down. From
`content/study-material/history/english/arrival-of-europeans/part-1-english-en.pdf`
the build derives:

| Field | Value |
|---|---|
| Title | `Arrival of Europeans - Part 1 (English)` |
| Slug | `part-1-english-en` (from the file name, so the URL never moves) |
| Page | `material-part-1-english-en.html` |
| Subject | `History` (from the first folder) |
| Language | `English` (from the second folder — `en`) |
| Chapter | `Arrival of Europeans` (from the third folder) |
| Part | `1 of 5` (its position among the files beside it) |
| Description | generated, 140–160 characters, the site's meta-description contract |
| Keywords | title + subject + `Study Material` + file name |
| Search | title, description, file name, subject, language, chapter and keywords joined into one searchable string |
| Dates | read from the file name when it carries one, otherwise stamped once into `data/pdf-meta.json` |
| File size | measured and shown as `1.6 MB` |
| Reading time | from the page count, `200 wpm` |
| Related chapters | the other chapters of this subject, this language first |
| Previous / next | the part before and after it inside the same chapter |

Acronyms keep their capitals (`ppsc` → `PPSC`, `si` → `SI`), years keep their
shape (`2026`), Gurmukhi names are transliterated into a readable URL, and the
title is clipped to the site's 60-character limit.

## `metadata.json` — only when you want to override (optional)

Three files, three different jobs.

### 1. Per file: next to the file (or any folder above it, up to the subject)

A map **keyed by the file name**. Every key is optional — whatever you leave
out keeps the value derived from the folders and the file name. The nearest
sidecar wins; layers are merged from the subject folder down to the file.

```json
{
  "part-1-english-en.pdf": {
    "title": "Arrival of Europeans — Complete Notes",
    "description": "The full Arrival of Europeans notes for Punjab Police and PSSSB exams, free to read online or download as a PDF for offline revision.",
    "keywords": ["arrival of europeans", "modern history"],
    "featured": true,
    "new": true,
    "published": "2026-09-01",
    "updated": "2026-09-30",
    "readingTime": 18,
    "difficulty": "Beginner",
    "exams": ["Punjab Police", "PSSSB"]
  }
}
```

If the folder holds exactly one file you may write a plain object instead of a
map and it is applied to that file.

`title` must fit 60 characters and `description` must be 140–160 characters —
the same rule every page on the site follows. The build fails loudly and tells
you the count rather than shipping a title Google will truncate.

### 2. Beside a chapter: `<subject>/<language>/metadata.json`

Same map, same rules — useful when a chapter's parts all need one exam tag.

### 3. Per subject: `content/study-material/metadata.json`

```json
{
  "subjects": {
    "computer": {
      "name": "Computer",
      "icon": "💻",
      "color": "#0ea5e9",
      "description": "Hardware, software, networking and the internet as Punjab exams actually ask them."
    }
  }
}
```

A subject folder is a subject whether or not it appears here. This file only
decorates it; a folder nobody listed still publishes, and a listed subject with
no folder is ignored.

## Ordering (Step 7)

The shelf and the Study Material index sort **Featured → Newest → Alphabetical**,
computed by the build. Inside a chapter, parts sort **by their part number**,
because a chapter is a sequence and not a shelf.

## Badges (Step 6)

`"featured": true`, `"new": true` and `"popular": true` in `metadata.json` put
the badge on the card. Nothing else can invent one.

## Where it shows up

| Surface | Source |
|---|---|
| Study → subject → **language** | `study.html?subject=<subject>` |
| … → **chapter** | `study.html?subject=<subject>&language=<language>` |
| … → **parts** | `study.html?subject=<subject>&language=<language>&chapter=<chapter>` |
| A part (Read Online, Download, Related Chapters, Previous / Next) | `material-<slug>.html` |
| Study Material index | `study-material.html` |
| Site search (Ctrl+K and `/search`) | `data/search-index.json` |
| The subject tree in the header and drawer | `data/study-manifest.json` |
| Sitemap | `sitemap.xml` (every `material-*.html`) |

## Rules

- File names are the interface: lowercase letters, digits and hyphens.
  `part-1-english-en.pdf`, not `Part 1 (final v2).pdf`. The file name is what
  fixes the URL, so renaming a file is the one thing that changes a URL.
- Folders are the hierarchy: subject, language, chapter. Never invent a fifth
  level to store something a sidecar could say.
- One subject per folder. A new subject = a new folder, nothing else.
- No affiliate links, no external download hosts, no signup walls. Study is
  free and reads like it.
- Delete a file, run `npm run publish`, and its part, its chapter (when the
  folder empties), its search row and its sitemap entry all disappear with it.
