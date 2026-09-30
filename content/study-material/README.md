# Study Material — drop files here, nothing else

This folder is the **only** place study material lives. The folder *is* the
registration: there is no list to edit, no page to write and no index to update.

```
content/study-material/
├── metadata.json                 ← optional subject registry (icon, colour, blurb)
├── computer/
│   ├── README.md                 ← ignored by the build
│   ├── fundamentals-of-computer.pdf
│   ├── fundamentals-of-computer-punjabi.pdf
│   └── metadata.json             ← optional per-file overrides
├── english/
├── punjabi/
├── reasoning/
├── quant/
├── gk/
├── current-affairs/
├── economy/
├── history/
├── geography/
├── polity/
├── science/
└── miscellaneous/
```

## Publish

```bash
npm run publish
```

That is the whole workflow. `scripts/build_content_manifest.ts` scans the PDFs,
`scripts/build_content.py` derives every field, renders the pages, fills
`data/content-manifest.json`, `data/search-index.json`, the sitemap and the
Study system's registry. Nothing is hand-registered.

## Supported files

| Extension | What happens |
|---|---|
| `.pdf`   | Scanned, described from the file name, published as `material-<slug>.html` with a download button. Page count and the first-page summary are read out of the file itself. |
| `.md`    | Markdown with optional front matter. Published as `material-<slug>.html`. |
| `.json`  | A structured record. Published as `material-<slug>.html`. |
| anything else | Ignored (never fails the build). |

`README.md` and every hidden file or folder are ignored. Subfolders other than
the subject folders are ignored too — only `content/study-material/<subject>/`
is read.

## What is derived for you (Step 4)

Nothing has to be written down. From `content/study-material/computer/fundamentals-of-computer.pdf`
the build derives:

| Field | Value |
|---|---|
| Title | `Fundamentals of Computer` |
| Slug | `fundamentals-of-computer` |
| Page | `material-fundamentals-of-computer.html` |
| Subject | `Computer` |
| Description | generated, 140–160 characters, the site's meta-description contract |
| Language | `English` — unless the name says `punjabi`, `panjabi`, `gurmukhi` or carries Gurmukhi script, in which case `ਪੰਜਾਬੀ` |
| Keywords | title + subject + `Study Material` |
| Search | title, file name, subject, keywords and description all joined into one searchable string |
| Dates | read from the file name when it carries one, otherwise stamped once into `data/pdf-meta.json` |
| File size | measured and shown as `2.1 MB` |
| Reading time | derived from the text, `200 wpm` |

Acronyms keep their capitals (`ppsc` → `PPSC`, `si` → `SI`), years keep their
shape (`2026`), Gurmukhi names are transliterated into a readable URL, and the
title is clipped to the site's 60-character limit.

## `metadata.json` — only when you want to override (optional)

Two different files, two different jobs.

### 1. Per file: `<subject>/metadata.json`

A map **keyed by the file name**. Every key is optional — whatever you leave
out keeps the value derived from the file name.

```json
{
  "fundamentals-of-computer.pdf": {
    "title": "Computer Fundamentals — Complete Notes",
    "description": "The full Computer fundamentals notes for Punjab Police and PSSSB exams, free to read online or download as a PDF for offline revision.",
    "language": "en",
    "keywords": ["computer fundamentals", "Punjab Police computer"],
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

### 2. Per subject: `content/study-material/metadata.json`

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

Every list is sorted **Featured → Newest → Alphabetical**, computed by the
build. There is no order field to maintain.

## Badges (Step 6)

`"featured": true`, `"new": true` and `"popular": true` in `metadata.json` put
the badge on the card. Nothing else can invent one.

## Where it shows up

| Surface | Source |
|---|---|
| Study → subject → **Study Material** | `study.html?subject=<subject>` |
| Study Material index | `study-material.html` |
| Site search (Ctrl+K and `/search`) | `data/search-index.json` |
| The subject tree in the header and drawer | `data/study-manifest.json` |
| Sitemap | `sitemap.xml` (every `material-*.html`) |

## Rules

- File names are the interface: lowercase letters, digits and hyphens.
  `fundamentals-of-computer.pdf`, not `Fundamentals Of Computer (final).pdf`.
- One subject per folder. A new subject = a new folder, nothing else.
- No affiliate links, no external download hosts, no signup walls. Study is
  free and reads like it.
- Delete a file, run `npm run publish`, and its page, its search row and its
  sitemap entry all disappear with it.
