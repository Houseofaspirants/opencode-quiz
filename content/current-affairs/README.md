# content/current-affairs/

Current affairs, one issue at a time, in Punjabi and in English. This folder
is the **only** authoring surface for Current Affairs: the section in the top
navigation is built entirely from what is filed here.

    content/current-affairs/
        <language>/                 which language the issue is written in
            <Month YYYY>/           which month it belongs to
                <file>.pdf          the issue itself

    content/current-affairs/punjabi/August 2026/current-affairs-august.pdf
    content/current-affairs/english/July 2026/current-affairs-july.pdf

## What the two folders become

| You create | The reader reaches |
|---|---|
| `content/current-affairs/<language>/` | `/current-affairs` → that language card → `/current-affairs/<language>` |
| `<language>/<Month YYYY>/` | `/current-affairs/<language>/<month>`, listed under **Archives** |
| `<language>/<Month YYYY>/<file>.pdf` | the issue itself: a page under `ca-…`, a row under **PDF Downloads**, and a card on the month page |

The month folder has to name **both** the month and the year, because the URL
promises both — `August 2026` publishes at
`/current-affairs/punjabi/august-2026`. A folder that reads any other way is
warned about during the build: its files still publish on the language page,
but no month URL is invented for a folder that never said when it was.

## Adding an issue

```bash
mkdir -p "content/current-affairs/punjabi/September 2026"
cp "september-2026.pdf" "content/current-affairs/punjabi/September 2026/"
npm run publish
```

That is the whole job. The month card, the archive entry, the download row and
the sitemap entry all appear on the next build — no list is maintained by hand,
and no month ever has to be registered anywhere. (The issue's own page stays in
the site search exactly as it does today; the month and language pages are
navigation, so they are deliberately left out of the search corpus.)

A new language is a folder too: `content/current-affairs/hindi/…` becomes a
third language card with its own page on the next build.

## Where each file lives in the section

- **`/current-affairs`** — the one front door. It opens with the language
  cards, then lists every published issue.
- **`/current-affairs/<language>`** — Daily Current Affairs, Monthly
  Magazine, PDF Downloads and Archives, followed by the months and the files
  in that language.
- **`/current-affairs/<language>/<month>`** — everything published for that
  month, newest first.

Everything else about Current Affairs — the magazine shelf, the archive page
and the practice sets — is reached from those pages, not duplicated by them.

- Schemas, fields and general rules: [`content/README.md`](../README.md).
- What the section renders: `scripts/current_affairs.py` (grouping) and
  `scripts/build_content.py` (`ca_section_page`).
