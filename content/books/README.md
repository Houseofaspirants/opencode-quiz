# content/books/ — the Books content system

One JSON file per book. Drop a file in here and rebuild; `scripts/books_engine.py`
publishes the shelf entry, the detail page, the sitemap entry, the search index,
the subject grouping and the structured data with **no route edit, no component
edit and no manual registration**.

## The shelf is a recommendation list, not a catalogue

A card shows exactly four things — cover, title, author and the book's
one-line `recommendation` — under a single **View on Amazon** button that
opens the store directly in a new tab. No price, no rating, no publisher, no
difficulty, no language filter, no "buy it if" / "skip it if". Books are filed
under `group`, and the chip bar is derived from the books that exist at build
time, so a new subject appears the moment a book carries it.

## The only three steps to publish a book

1. Create `<id>.json` in this folder (slug = file name, lowercase, hyphens).
2. Drop a cover into `assets/books/covers/<id>.jpg` (optional — until one
   lands the card uses the large initials cover, which occupies the same box).
3. Add the purchase link under `<id>` in `config/affiliate-links.json`.

That is the whole admin workflow: one file, one image, one link. No code.

## What is NOT here

**No links.** Affiliate and purchase URLs live only in
`config/affiliate-links.json`. The engine fails the build if it finds `url`,
`affiliate`, `buyUrl`, `link` or an `amazon.` / `flipkart.` host inside a book
file — so a link can never drift back into content.

The engine writes that URL straight into the button's `href`, so the reader
reaches the shop in **one click** — no popup, no redirect stub in between —
with the UTM parameters and the Associates tag merged on at build time. The URL
appears only as the href; it is never printed as visible text.

## Fields

| Field | Required | Notes |
| --- | --- | --- |
| `id`, `slug` | yes | lowercase slug, must equal the file name |
| `title` | yes | the book's title, plain text |
| `author` | yes | as printed on the book |
| `recommendation` | yes | **the one line the card prints** under the author. Max 140 characters — roughly two lines at phone width. Honest and specific. |
| `subject` | yes | an id from `data/subjects.json`. Drives related content, the search corpus and the schema — not the shelf. |
| `group` | no | the subject the shelf files it under, e.g. `Polity`, `Punjab GK`. Max 40 characters. Falls back to the subject's name. |
| `keywords`, `lastUpdated` | yes | search corpus; sitemap date (`YYYY-MM-DD`) |
| `seoTitle` | yes | ≤ 60 characters, unique across the site |
| `seoDescription` | yes | 140–160 characters, unique across the site |
| `cover` | no | path under `assets/books/covers/`, e.g. `assets/books/covers/x.jpg` |
| `subtitle` | no | one line under the title on the detail page |
| `description` | no | what the book covers — read by the JSON-LD and the related-content ranker, never shown on the shelf. Defaults to `recommendation`. |
| `priority` | no | sitemap `<priority>`, e.g. `"0.7"` (defaults to it) |
| `featured` | no | boolean — sorts that book first within its group |
| `publisher`, `edition`, `difficulty`, `rating`, `languages`, `examTags` | no | still read by the schema, the search corpus and the ranker — **never rendered on the shelf** |
| `bestFor`, `buyIf`, `avoidIf`, `howToUse`, `pros`, `cons`, `topicsCovered` | no | legacy review fields; not rendered anywhere any more. Harmless to keep, safe to delete. |
| `relatedBooks`, `relatedQuizzes`, `relatedNotes`, `relatedCurrentAffairs` | no | `{label, href}` seeds — **optional**; every related group is derived automatically from `data/index.json` and `data/content-manifest.json` even with none of these |

Everything not marked "yes" is filled with a default after validation, so a
file carrying only `id`, `slug`, `title`, `author`, `group`, `recommendation`,
`keywords`, `lastUpdated`, `seoTitle` and `seoDescription` publishes exactly
the same way a twenty-field one does.

## Voice

Honest and specific: no superlatives, no guarantees, no invented pass rates.
The `recommendation` should be true of the book and useful to a reader who has
never heard of it — a shelf nobody can trust is worth nothing.
