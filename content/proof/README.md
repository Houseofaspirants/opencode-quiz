# Official documents — `assets/proof/`

Every scan in this folder becomes a card in the **Official Documents** section
of [`/rank-2-blueprint`](../../rank-2-blueprint.html): preview, download, file
type, file size and — when you record it — the upload date.

There is no list of documents to edit. Drop the file in, publish, done.

```bash
npm run publish
```

That runs `scripts/proof_documents.py`, which writes `data/proof-manifest.json`,
and the page reads that file on load. **Never hand-edit `data/proof-manifest.json`**
— it is overwritten on every build.

## Naming

The file name decides which card it fills, by matching these tokens anywhere in
the name (case and punctuation are ignored):

| Card | Matches |
| --- | --- |
| Result Card | `result`, `marksheet`, `mark-sheet`, `scorecard` |
| Merit List | `merit` |
| Paper 1 Answer Sheet | `paper-1`, `answer-sheet-1`, `answersheet-1`, `sheet-1` |
| Paper 2 Answer Sheet | `paper-2`, `answer-sheet-2`, `answersheet-2`, `sheet-2` |
| Paper 3 Answer Sheet | `paper-3`, `answer-sheet-3`, `answersheet-3`, `sheet-3` |
| Appointment Letter | `appointment` *(only appears once a file exists)* |
| Training Photos | `training`, `joining` *(only appears once a file exists)* |

Anything that matches nothing still ships — it lands in an extra card at the end
rather than being hidden. Two files claiming one card: the first
(alphabetically) holds the card, the second becomes an extra.

Accepted: `.pdf`, `.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`, `.avif`.
Scans in the legacy `assets/img/proof/` folder are picked up too.

```
assets/proof/
├── official-result.jpg          → Result Card
├── official-merit-list.jpg      → Merit List
├── answer-sheet-1.pdf           → Paper 1 Answer Sheet
├── answer-sheet-2.pdf           → Paper 2 Answer Sheet
└── metadata.json                → optional, see below
```

## `metadata.json` — optional

Only needed for the things a file cannot tell you: a human title, a note, an
upload date, and the question-level detail that fills the *Original answer sheet
analysis* section. Every key is optional.

```json
{
  "answer-sheet-1.pdf": {
    "title": "Paper 1 original answer sheet",
    "note": "Scanned response sheet as released by the recruitment board.",
    "uploaded": "2026-10-04",
    "slot": "paper-1",
    "questions": [
      {
        "n": 1,
        "text": "Who was the first Governor-General of India?",
        "selected": "B",
        "correct": "C",
        "explanation": "Lord Mountbatten served first, then C. Rajagopalachari."
      }
    ]
  }
}
```

- `slot` overrides the name-based match above.
- `questions` is what turns a card into an analysis. **Publish only what the
  original sheet actually records** — no explanation is better than an invented
  one, and a question with no explanation simply renders without one.
- `uploaded` is only shown if you write it here. It is deliberately not derived
  from the file's timestamp or from git: both change under a fresh clone, and
  the SEO gate requires every generated file to be byte-identical between runs.

## What the page does with it

- **Section 2 — Verified result.** One card per slot. A slot with no file
  renders as an explicit *Not published yet* card, so the layout never shifts
  when a document lands and the page never claims a file it cannot display.
- **Analytics strip.** Under Paper 1 / Paper 2 cards: correct, wrong and
  skipped, read out of the attempt table on the same page. Under Paper 3:
  its qualifying status.
- **Section 7 — Original answer sheet analysis.** Cards appear only for a sheet
  that carries `questions`, each row showing selected option, correct option and
  explanation (if one exists).
- **Viewer.** Preview opens a full-screen viewer without navigating away:
  zoom in/out, fit width, fit page, previous/next page, page number, fullscreen,
  download, keyboard (`←` `→` `+` `-` `0` `1` `F` `S` `Esc`) and, on touch,
  swipe-to-turn and pinch-to-zoom. PDF.js is fetched only when Preview is first
  pressed, so it costs nothing to readers who never open a document.
