# content/books/ — the Books content system

One JSON file per book. Drop a file in here and rebuild; `scripts/books_engine.py`
publishes the shelf entry, the detail page, the sitemap entry, the search index,
the filter facets and the structured data with **no route edit, no component edit
and no manual registration**.

## The only three steps to publish a book

1. Create `<id>.json` in this folder (slug = file name, lowercase, hyphens).
2. Drop a cover into `assets/books/covers/<id>.jpg` (optional — without one the
   page renders the initials cover the shelf already uses).
3. Add the purchase links under `<id>` in `config/affiliate-links.json`.

That is the whole admin workflow.

## What is NOT here

**No links.** Affiliate and purchase URLs live only in
`config/affiliate-links.json`. The engine fails the build if it finds `url`,
`affiliate`, `buyUrl`, `link` or an `amazon.` / `flipkart.` host inside a book
file — so a link can never drift back into content.

## Fields

| Field | Required | Notes |
| --- | --- | --- |
| `id`, `slug` | yes | lowercase slug, must equal the file name |
| `title` | yes | the book's title, plain text |
| `subtitle` | no | one line under the title |
| `author`, `publisher` | yes | as printed on the book |
| `cover` | no | path under `assets/books/covers/`, e.g. `assets/books/covers/x.jpg` |
| `subject` | yes | an id from `data/subjects.json` |
| `difficulty` | yes | `Beginner` \| `Intermediate` \| `Advanced` |
| `rating` | yes | 0–5 in half steps |
| `edition` | yes | e.g. `Latest revised edition`, `Monthly`, `Annual` |
| `languages` | yes | array of display names |
| `examTags` | yes | exam ids or free tags |
| `description` | yes | what the book actually covers — one or two sentences |
| `bestFor`, `buyIf`, `avoidIf`, `howToUse` | yes | the four honest judgements |
| `pros`, `cons` | yes | arrays of short, factual bullets |
| `topicsCovered` | yes | array of the chapters/areas it covers |
| `relatedBooks` | no | array of other book `id`s |
| `relatedQuizzes`, `relatedNotes`, `relatedCurrentAffairs` | no | `{label, href}` seeds — **optional**; every related group is derived automatically from `data/index.json` and `data/content-manifest.json` even with none of these |
| `featured` | yes | boolean — the featured chip on the shelf |
| `priority` | yes | sitemap `<priority>` string, e.g. `"0.7"` |
| `seoTitle` | yes | ≤ 60 characters, unique across the site |
| `seoDescription` | yes | 140–160 characters, unique across the site |
| `keywords` | yes | comma-separated |
| `lastUpdated` | yes | `YYYY-MM-DD` |

## Voice

Honest and specific: no superlatives, no guarantees, no invented pass rates.
`avoidIf` should genuinely talk a reader out of a purchase when the book is
wrong for them — a shelf nobody can trust is worth nothing.
