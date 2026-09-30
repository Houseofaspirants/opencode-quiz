# Book covers

Drop one image per book here and set its path on the book's `cover` field in
`content/books/<book-id>.json`:

```json
"cover": "assets/books/covers/laxmikanth-indian-polity.jpg"
```

That is the whole step. The Books Engine reads the file, records its pixel
size, ships both dimensions on the shelf card so the grid never reflows when
the image lands, and gives the book page a `Book.image` node for search
results and rich results.

## Rules

| Rule | Why |
| --- | --- |
| One file per book, named after the book id | Nothing else has to be edited to add a cover |
| Portrait, close to **2:3** (600 × 900 is plenty) | That is the shape a book cover actually is; anything else gets cropped by `object-fit` |
| WebP or JPEG, **under 120 KB** | The shelf loads them lazily; this keeps it under one card's budget on 4G |
| Front cover only, no shop banners or price stickers | This platform does not sell anything — the buy buttons do that |
| **Never** put a buy link, price or "best seller" badge in the image | The image is content; links and claims belong in `content/books/<id>.json` |

An image the engine cannot measure (truncated, not really an image) is simply
treated as absent: the book keeps rendering the initials block it uses today,
and the build still passes. A missing cover is never a build failure.

## Publishing a book, start to finish

1. `content/books/<book-id>.json` — the review itself.
2. `assets/books/covers/<book-id>.jpg` — the cover (optional).
3. `config/affiliate-links.json` → `books.<book-id>` — where its buy buttons go
   (optional; a book with no entry renders "Currently unavailable").

Then `python3 scripts/build_index.py` (or `bash scripts/ci.sh`) publishes the
shelf, the detail page and the tracked `/go/` hops.
