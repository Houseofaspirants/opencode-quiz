# House of Aspirants - Quiz Portal

> **An empty, production-ready quiz ENGINE.**
> It contains **zero questions, zero MCQs and zero sample data** on purpose —
> you add every question yourself, one JSON file at a time, with no coding.

**Practice Daily. Crack Punjab Police.**

A modern, fast, responsive and PWA-ready quiz website for Punjab Police, PSSSB,
Punjab Government Exam and other competitive exam aspirants.

---

## Table of contents

1. [What you got](#1-what-you-got)
2. [Folder structure](#2-folder-structure)
3. [How the auto-detection works](#3-how-the-auto-detection-works)
4. [Add your first quiz (no code)](#4-add-your-first-quiz-no-code)
5. [JSON format cheat-sheet](#5-json-format-cheat-sheet)
6. [Add a new Subject](#6-add-a-new-subject)
7. [Edit or delete a quiz](#7-edit-or-delete-a-quiz)
8. [Deploy on GitHub](#8-deploy-on-github)
9. [Deploy on Vercel](#9-deploy-on-vercel)
10. [Update the website later](#10-update-the-website-later)
11. [Local preview on your computer](#11-local-preview-on-your-computer)
12. [Configuration files](#12-configuration-files)
13. [Features list](#13-features-list)
14. [SEO files](#14-seo-files)
15. [PWA - install & offline](#15-pwa---install--offline)
16. [Advertisement slots](#16-advertisement-slots)
17. [Future backend migration](#17-future-backend-migration)
18. [Scalability notes](#18-scalability-notes)
19. [Troubleshooting](#19-troubleshooting)

---

## 1. What you got

| Area | Included |
|---|---|
| Pages | Home, Subject, Quiz, Result, Daily Quiz, Mock Tests, Bookmarks, Progress, Leaderboard, About, Contact, Privacy, Terms, 404 |
| Tech | HTML5 · CSS3 · Vanilla JS · JSON · No backend, no framework, no database |
| Quiz engine | Palette, progress bar, per-question timer, overall timer, auto-next, answer lock, mark for review, skip, keyboard nav, autosave/resume, bookmark |
| Result | Score ring, accuracy, pass/fail, time taken, subject-wise performance, weak/strong areas, full answer review with explanation & reference |
| Extras | Dark/light mode, instant search, streaks, achievements, leaderboard (backend-ready), Telegram branding, ad slots, offline PWA with install button |
| Content | **Ships 100% empty** — `questions/` contains only empty subject folders |

**You only ever edit two kinds of files:**

| You want to… | Edit |
|---|---|
| Add / change questions | a JSON file inside `questions/` |
| Change timers, links, marketing numbers | `data/site.json` |
| Change a subject card (name/icon/color) | `data/subjects.json` |

Everything else (nav, cards, counts, search, sitemap) updates by itself.

---

## 2. Folder structure

```
house-of-aspirants/
│
├── index.html                 ← Home page
├── subject.html               ← Topic list of one subject (?subject=gk)
├── quiz.html                  ← Quiz engine (?subject=gk&topic=polity | ?mode=daily | ?mode=mock)
├── result.html                ← Result + answer review
├── mock.html                  ← Mock test builder
├── bookmarks.html             ← Saved questions
├── progress.html              ← Progress + achievements
├── leaderboard.html           ← Leaderboard
├── about.html · contact.html · privacy.html · terms.html · 404.html
│
├── questions/                 ★ YOUR QUESTION BANK (starts EMPTY)
│   ├── gk/                    ← General Knowledge topic files
│   ├── quant/                 ← Quantitative Aptitude
│   ├── reasoning/
│   ├── punjabi/
│   ├── english/
│   ├── computer/
│   └── current-affairs/
│       (each folder holds only .gitkeep until you add a .json file)
│
├── templates/
│   └── topic-template.json    ← Empty template (0 questions). Copy it to start a topic
│
├── data/
│   ├── index.json             ★ AUTO-GENERATED manifest — never edit by hand
│   ├── subjects.json          ← Subject CARD only (name / icon / color / order)
│   └── site.json              ← Site-wide settings (timers, links, stats)
│
├── scripts/
│   ├── build-index.mjs        ← Auto-detects new/edited/deleted JSON files (Node)
│   └── build_index.py         ← Identical fallback if Node is not installed (Python 3)
│
├── assets/
│   ├── css/   style.css, quiz.css
│   ├── js/    core.js (shared header/footer/search/PWA/storage),
│   │          home.js, subject.js, quiz.js, result.js, mock.js,
│   │          bookmarks.js, leaderboard.js, dashboard.js, contact.js
│   └── img/   logo-mark.png (your logo), logo-sm.png (header), favicon-32.png,
│              og-cover.png (1200×630), icon-180.png, icon-192.png, icon-512.png
│
├── sw.js                      ← Service worker (offline support)
├── manifest.webmanifest       ← PWA manifest (install button, shortcuts)
├── robots.txt · sitemap.xml   ← SEO (sitemap also auto-regenerated at build)
├── vercel.json                ← Vercel deployment config
└── package.json               ← npm build/start shortcuts
```

> **Shared chrome:** every page contains only
> `<div data-site-header></div>` … `<div data-site-footer></div>`.
> `assets/js/core.js` fills them with the header, mobile menu, search box and
> footer. Change the navigation in **one place** (`HEADER_HTML` / `FOOTER_HTML`
> in `core.js`) and all pages update.

---

## 3. How the auto-detection works

```
questions/gk/polity.json   →   appears as a quiz card on the GK page
edit the file               →   question counts refresh automatically
delete the file             →   quiz card disappears automatically
create questions/new-topic/ →   a brand-new subject card appears everywhere
```

Every deploy (GitHub → Vercel) runs **`scripts/build-index.mjs`**, which:

1. scans every `questions/<subject>/*.json` file,
2. counts the questions and validates the format,
3. writes `data/index.json` (the manifest the website reads),
4. regenerates `sitemap.xml`.

You never touch any JavaScript, and **topics are never hardcoded** — the
subject page shows as many topic cards as files you have, sorted by name.

The build is **non-fatal**: an invalid file is reported as a warning and
skipped, so one broken JSON never breaks the whole deploy.

**No Node on your machine?** Use the identical Python fallback:

```bash
python3 scripts/build_index.py     # same output as build-index.mjs
```

> **Important:** `data/index.json` and `sitemap.xml` are committed already
> generated (empty state), so the site works even before your first build.
> On deploy they are always rebuilt from your `questions/` folder.

---

## 4. Add your first quiz (no code)

### Step 1 — Copy the template

```
templates/topic-template.json   →   questions/gk/polity.json
```

(The template contains `"questions": []` — it is a blank slate, not a quiz.)

### Step 2 — Fill it in

```json
{
  "topic": "Indian Polity",
  "description": "Constitution, Parliament, Judiciary and more.",
  "timeLimit": 600,
  "questions": [
    {
      "q": "Type your question here?",
      "options": ["Option A", "Option B", "Option C", "Option D"],
      "correct": 0,
      "explanation": "Why option A is right (optional).",
      "reference": "NCERT / book name (optional)",
      "difficulty": "Easy",
      "topic": "Indian Polity"
    }
  ]
}
```

* File name = topic name shown on the site (`polity.json` → “Polity”).
* `correct` may be an **index** (`0`–`3`), a **letter** (`"B"`) or the **exact option text**.
* `explanation` and `reference` are optional — the result page only shows them if present.
* `timeLimit` is the **overall quiz timer in seconds** (optional). `0` or missing = questions × per-question seconds.
* The per-question timer comes from `data/site.json → questionSeconds` (default 30).
* A file with `"questions": []` is still allowed: it shows a topic card with
  the message *“No questions available yet.”*

### Step 3 — Save, push, done

```bash
git add .
git commit -m "Add Polity quiz"
git push
```

Vercel rebuilds in ~10 seconds and the quiz card is live.

---

## 5. JSON format cheat-sheet

| Field | Required | Meaning |
|---|---|---|
| `q` (or `question`) | ✅ | Question text |
| `options` (or `opts`) | ✅ | Array of 2–4 choices (4 recommended) |
| `correct` (or `answer` / `key`) | ✅ | `0`, `"B"`, or exact option text |
| `explanation` (or `solution`) | optional | Shown in answer review |
| `reference` (or `ref`) | optional | Shown in answer review |
| `difficulty` | optional | Easy / Medium / Hard |
| `topic` | optional | Sub-tag used for Weak/Strong area analysis |
| `timeLimit` | optional | Overall seconds for the whole quiz |

Top-level file may be an **array of questions** or an **object** with
`questions`, `mcqs` or `quiz` array.

**Common mistakes the builder warns about (build still succeeds):**

* invalid JSON (missing comma / trailing comma),
* a question without `q`,
* options missing,
* missing `correct`.

---

## 6. Add a new Subject

1. Create a folder: `questions/my-subject/`
2. Drop any `.json` topic file inside it — **it is detected instantly**.
3. *(Optional, prettier card)* add it to `data/subjects.json`:

```json
{ "id": "my-subject", "name": "My Subject", "short": "MS",
  "icon": "📘", "color": "#4f46e5", "description": "What it covers.", "order": 8 }
```

`subjects.json` describes the **card only** (name, icon, colour, description,
order). It contains **no topic list** — topics always come from your files.

New subjects automatically appear in: home page grid, nav bar, mobile menu,
footer, search, page title and sitemap. If you skip step 3 the subject still
works; it just uses a default icon/colour.

---

## 7. Edit or delete a quiz

* **Edit** → change the JSON file, push. Counts update automatically.
* **Delete** → delete the JSON file, push. The card disappears.
* **Reorder** → file order does not matter; topics are sorted by name.
* **Rename a topic** → rename the file, push (old link becomes a 404 card).

---

## 8. Deploy on GitHub

1. Create a new repository, e.g. `house-of-aspirants`.
2. Push this folder:

```bash
git init
git add .
git commit -m "House of Aspirants Quiz Portal"
git branch -M main
git remote add origin https://github.com/<your-username>/house-of-aspirants.git
git push -u origin main
```

Empty `questions/*` folders are preserved because each contains `.gitkeep`.

---

## 9. Deploy on Vercel

### Option A — from GitHub (recommended)

1. Go to [vercel.com/new](https://vercel.com/new) → import your repository.
2. Vercel reads `vercel.json` automatically. Confirm:
   * **Build Command:** `node scripts/build-index.mjs`
   * **Output Directory:** `.`
3. Click **Deploy**. Done.

### Option B — Vercel CLI

```bash
npm i -g vercel
vercel        # first deploy (preview)
vercel --prod # production deploy
```

### After deploying

Update these places with your real domain (or keep the placeholder
`https://house-of-aspirants.vercel.app`):

* `data/site.json` → `"url"`
* `robots.txt` → sitemap line
* `index.html` → canonical / Open Graph URLs

Then redeploy. Every push to `main` = automatic redeploy.

---

## 10. Update the website later

**Only adding/editing questions (most common):**

```bash
# 1. edit a file in questions/
# 2. commit & push
git add questions/
git commit -m "Update History quiz"
git push
```

**Changing timers / links / Telegram / stats:** edit `data/site.json`, push.

**Changing a subject card:** edit `data/subjects.json`, push.

**Changing the navigation or footer:** edit `HEADER_HTML` / `FOOTER_HTML`
in `assets/js/core.js`, push.

**Changing the design:** edit `assets/css/style.css`.

**After changing core app files:** bump `VERSION` in `sw.js`.

---

## 11. Local preview on your computer

Browsers block `fetch()` from `file://`, so always use a tiny local server:

```bash
npm run build     # generate data/index.json   (needs Node)
npm start         # serve at http://localhost:3000
```

No Node installed? Use Python for both steps:

```bash
python3 scripts/build_index.py          # build the manifest
python3 -m http.server 8000             # serve at http://localhost:8000
```

Any static server works: `npx serve .` · `php -S localhost:8000` · VS Code
“Live Server”.

---

## 12. Configuration files

### `data/site.json` — site-wide settings

```json
{
  "url": "https://your-domain.com",   // used for sitemap + canonical tags
  "telegram": "https://t.me/HouseOfAspirants",
  "instagram": "https://instagram.com/houseofaspirants",
  "youtube": "https://youtube.com/@houseofaspirants",
  "questionSeconds": 30,               // per-question timer
  "dailyQuizSize": 20,                 // questions in Daily Challenge
  "passPercent": 40,                   // pass line on result page
  "studentsPracticed": 12500           // optional marketing number
}
```

### `data/subjects.json` — subject cards only

```json
{
  "subjects": [
    { "id": "gk", "name": "General Knowledge", "short": "GK",
      "icon": "🏛️", "color": "#6366f1",
      "description": "History, Polity, Geography, Punjab GK, Science and more.",
      "order": 1 }
  ]
}
```

* `id` **must** equal the folder name in `questions/`.
* There is **no `topics` array** — topics are detected from files at build time.

---

## 13. Features list

* **Quiz engine** — palette (answered / not answered / marked / visited), progress bar, per-question countdown, overall countdown, auto-next on timeout, answer lock on time-up, mark for review, skip, previous/next, submit confirmation.
* **Keyboard** — `←` `→` navigate · `1`–`4` answer · `M` mark · `S` skip · `Enter` submit · `Ctrl/⌘+K` search.
* **Autosave** — answers survive refresh; you resume where you stopped.
* **Result** — total, attempted, correct, wrong, skipped, accuracy, percentage, score, pass/fail, time taken, subject-wise bars, weak/strong areas, performance message.
* **Answer review** — question, your answer, correct answer, explanation & reference (only when present in JSON), filter by correct/wrong/skipped.
* **Daily Quiz** — random 20, same for everyone for that day, new every day.
* **Mock Tests** — full length, all subjects or one subject, configurable count & minutes.
* **Bookmarks** — saved locally, reveal answer, deep link back to the quiz.
* **Progress** — completed quizzes, average score, accuracy, study time, daily & weekly streaks, milestone badges.
* **Leaderboard** — today / weekly / all-time tabs, API-ready interface.
* **Search** — instant subject + topic filter, `Ctrl/⌘+K`.
* **Dark mode** — toggle, remembered, matches system by default.
* **PWA** — install button, offline quizzes, PNG app icons, shortcuts & splash colours.

---

## 14. SEO files

* Title + description + canonical on every page
* Open Graph & Twitter card tags with `og-cover.png` (1200×630)
* JSON-LD `WebSite` + `SearchAction` + `Organization` schema (home)
* `robots.txt` + auto-generated `sitemap.xml` (subject pages included)
* Semantic HTML (`header/nav/main/section/footer`), single `h1`, alt text, skip link

> Remember to swap `https://house-of-aspirants.vercel.app` for your real
> domain in `data/site.json`, `robots.txt` and `index.html`.

---

## 15. PWA - install & offline

* `manifest.webmanifest` — name, colours, PNG icons (192/512 + maskable) and shortcuts (Daily Quiz, Leaderboard).
* `sw.js` — app shell + question JSON are cached; quizzes work **fully offline** after first visit.
* Install button appears automatically (Chrome/Edge). iOS: Share → *Add to Home Screen*.

After changing core files, bump `VERSION` in `sw.js` so returning users get the update.

---

## 16. Advertisement slots

Search for `ad-slot` in the HTML files. Each is a clean, labelled, non-popup area:

```html
<div class="ad-slot">
  <div>
    <div class="ad-label">Advertisement</div>
    <!-- paste your ad / affiliate / promo HTML here -->
  </div>
</div>
```

To remove a slot, delete that block. No popups, no popunders, ever.

---

## 17. Future backend migration

The UI never touches `localStorage` directly — everything goes through
interfaces in `assets/js/core.js`:

| Today | Tomorrow |
|---|---|
| `HOA.loadIndex()` reads `data/index.json` | `fetch('/api/index')` (Firebase/Supabase/Express) |
| `HOA.loadQuestions()` reads `questions/…json` | `GET /api/questions/:subject/:topic` |
| `HOA.leaderboard.submit/get` | `POST /api/scores`, `GET /api/scores` |
| `HOA.bookmarks`, `HOA.progress` | user document in Firestore/Postgres |

Swap those functions and the rest of the site keeps working — no rewrite.

---

## 18. Scalability notes

* **100,000+ MCQs** — questions are split into many small JSON files; the
  browser only fetches the topic you open (a few KB), never the whole bank.
* `data/index.json` stays tiny (metadata only: names + counts).
* Daily/Mock load only a handful of files per session.
* Storage caps: 500 bookmarks, 300 leaderboard rows, 120 days of progress —
  automatic, so localStorage never fills up.

---

## 19. Troubleshooting

| Symptom | Fix |
|---|---|
| Topic not showing | File must be `questions/<subject>/<name>.json` with valid JSON. Run the build and read its warnings. |
| Page is blank locally | You opened `file://` — use `npm start` or `python3 -m http.server 8000`. |
| Stats still 0 after adding questions | Redeploy / run the build; the manifest is generated at build time. |
| Build warning about a question | Fix the mentioned Q number (missing `q`, `options` or `correct`). The build never fails — it skips bad files. |
| `node: command not found` | Use `python3 scripts/build_index.py` instead. |
| Old version shows after update | Bump `VERSION` in `sw.js`. |
| Subject card looks default | Add its entry to `data/subjects.json` (`id` = folder name). |
| Telegram / social link wrong | Edit `data/site.json` → `telegram`, `instagram`, `youtube`. |

---

### Support

* Telegram: [t.me/HouseOfAspirants](https://t.me/HouseOfAspirants)
* Instagram · YouTube — links in the site footer.

**© House of Aspirants** — Practice Daily. Crack Punjab Police.
