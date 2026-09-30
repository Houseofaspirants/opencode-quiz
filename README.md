# House of Aspirants - Free Competitive Exam Learning Platform

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
15. [Offline - service worker](#15-offline---service-worker)
16. [Advertisement slots](#16-advertisement-slots)
17. [Future backend migration](#17-future-backend-migration)
18. [Scalability notes](#18-scalability-notes)
19. [Study guides & articles (no code)](#19-study-guides--articles-no-code)
20. [Google sign-in & cloud sync (Firebase)](#20-google-sign-in--cloud-sync-firebase)
21. [Troubleshooting](#21-troubleshooting)
22. [Telegram growth & conversion system](#22-telegram-growth--conversion-system)
23. [Leaderboard & gamification](#23-leaderboard--gamification)
24. [Content system — Markdown to live pages (no CMS, no code)](#24-content-system--markdown-to-live-pages-no-cms-no-code)
25. [Multilingual quizzes — one topic, many languages](#25-multilingual-quizzes--one-topic-many-languages)

---

## 1. What you got

| Area | Included |
|---|---|
| Pages | Home, Subject, Quiz, Result, Daily Quiz, Mock Tests, Bookmarks, Progress, Leaderboard, About, Contact, Privacy, Terms, 404 |
| Tech | HTML5 · CSS3 · Vanilla JS · JSON · No backend, no framework, no database |
| Quiz engine | Palette, progress bar, per-question timer, overall timer, auto-next, answer lock, mark for review, skip, keyboard nav, autosave/resume, bookmark |
| Result | Score ring, accuracy, pass/fail, time taken, subject-wise performance, weak/strong areas, full answer review with explanation & reference |
| Extras | Dark/light mode, instant search, streaks, achievements, leaderboard (backend-ready), Telegram branding, ad slots, offline PWA |
| Content | **Ships 100% empty** — `questions/` contains only empty folders (each with a `.gitkeep`) |

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
├── subject.html               ← Categories/topics (?subject=gk | ?subject=gk&category=polity)
├── quiz.html                  ← Quiz engine (?subject=gk&topic=polity | ?mode=daily | ?mode=mock)
├── result.html                ← Result + answer review
├── mock.html                  ← Mock test builder
├── bookmarks.html             ← Saved questions
├── progress.html              ← Progress + achievements
├── leaderboard.html           ← Leaderboard
├── about.html · contact.html · privacy.html · terms.html · 404.html
│
├── questions/                 ★ YOUR QUESTION BANK (starts EMPTY)
│   │   FLAT:         questions/<subject>/<topic>.json
│   │   CATEGORIZED:  questions/<subject>/<category>/<topic>.json
│   ├── gk/                    ← General Knowledge = CATEGORIZED (see below)
│   │   ├── polity/            ← one category = one folder; the folder list
│   │   ├── history/              comes from "categories" in data/subjects.json
│   │   ├── punjab-gk/
│   │   ├── geography-environment/
│   │   ├── economy/
│   │   └── others/
│   ├── quant/                 ← Quantitative Aptitude (FLAT: topics directly inside)
│   ├── reasoning/             ← FLAT
│   ├── punjabi/               ← FLAT
│   ├── english/               ← FLAT
│   ├── computer/              ← FLAT
│   └── current-affairs/       ← FLAT
│       (each folder holds only .gitkeep until you add a .json file)
│
├── templates/
│   └── topic-template.json    ← Empty template (0 questions). Copy it to start a topic
│
├── data/
│   ├── index.json             ★ AUTO-GENERATED manifest — never edit by hand
│   ├── subjects.json          ← Subject CARD only (name / icon / color / order)
│   ├── articles.json          ← Study-guide registry (hub, related cards, sitemap)
│   └── site.json              ← Site-wide settings (timers, links, stats)
│
├── scripts/
│   ├── build-index.mjs        ← Auto-detects new/edited/deleted JSON files (Node)
│   └── build_index.py         ← Identical fallback if Node is not installed (Python 3)
│
├── assets/
│   ├── css/   style.css, quiz.css
│   ├── js/    core.js (shared header/footer/search/offline/storage),
│   │          home.js, subject.js, related.js (related subjects/quizzes/guides),
│   │          quiz.js, result.js, mock.js,
│   │          bookmarks.js, leaderboard.js, dashboard.js, contact.js
│   └── img/   logo-mark.png (your logo), logo-sm.png (header), favicon-32.png,
│              og-cover.png (1200×630), icon-180.png, icon-192.png, icon-512.png
│
├── sw.js                      ← Service worker (offline support)
├── manifest.webmanifest       ← PWA manifest (icons, shortcuts)
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
FLAT subject (e.g. Punjabi):
questions/punjabi/punjabi-mcq-10.json   →  Punjabi Mcq 10 topic card

CATEGORIZED subject (e.g. General Knowledge):
questions/gk/polity/constitution.json    →  Constitution under GK › Polity
questions/gk/history/ancient-history.json→  Ancient History under GK › History

edit the file                 →   question counts refresh automatically
delete the file               →   quiz card disappears automatically
create questions/new-subject/ →   a brand-new subject card appears everywhere
```

Every deploy (GitHub → Vercel) runs **`scripts/build-index.mjs`**, which:

1. scans every `questions/` folder:
   * subjects **with** a `categories` list in `data/subjects.json` are read
     one level deeper — `questions/<subject>/<category>/<topic>.json`
     (Subject › Category › Topic),
   * subjects **without** that key stay flat — `questions/<subject>/<topic>.json`,
2. counts the questions and validates the format,
3. writes `data/index.json` (the manifest the website reads),
4. regenerates `sitemap.xml`.

You never touch any JavaScript, and **topics are never hardcoded** — the page
shows as many cards as files you have, sorted by name. Drop
`questions/gk/polity/parliament.json` into place and the *Parliament* card
appears on the GK › Polity page after the next deploy, with its own question
count and Play button.

A category folder that exists on disk but is missing from `subjects.json` is
**auto-added** (name humanized from the folder name), so nothing you upload
can ever stay invisible — add it to the config later for a custom name/icon.

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
templates/topic-template.json   →   questions/gk/polity/your-topic.json
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
order) plus — optionally — its **`categories`** list (next section). It
contains **no topic list** — topics always come from your files.

New subjects automatically appear in: home page grid, nav bar, mobile menu,
footer, search, page title and sitemap. If you skip step 3 the subject still
works; it just uses a default icon/colour.

### Categories — Subject › Category › Topic (optional, per subject)

Add a `categories` array to any subject in `data/subjects.json` to give it a
third level — this is how General Knowledge works today:

```json
{ "id": "gk", "name": "General Knowledge", "short": "GK", "icon": "🏛️",
  "color": "#6366f1", "description": "…", "order": 1,
  "categories": ["Polity", "History", "Punjab GK",
                 "Geography & Environment", "Economy", "Others"] }
```

* Opening the subject shows **only the category cards**; clicking one lists
  every JSON file inside `questions/gk/<category>/` as a topic card
  (name, question count, Play) — all read from the files, never hardcoded.
* Plain strings are enough: the folder is generated from the name
  (`"Punjab GK"` → `questions/gk/punjab-gk/`). Use an object
  `{ "name": "…", "folder": "…", "icon": "…" }` when you want to control
  the folder name or icon yourself.
* Subjects **without** `categories` keep the original flat layout and are
  completely unaffected. To categorize another subject later (Computer,
  Punjabi, English, Reasoning, Maths), create the category folders first —
  the build auto-appends any folder it finds — then add the config.
* Unlimited categories and unlimited topics per subject, with no code
  changes ever.

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
git commit -m "House of Aspirants"
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

If your domain ever changes, update it in these places (currently
`https://houseofaspirants.in`):

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
  "telegram": "https://t.me/HouseOfAspirant",
  "instagram": "https://instagram.com/si.gurpreetsingh.pp",
  "youtube": "https://youtube.com/@houseofaspirants-y5s",
  "questionSeconds": 30,               // per-question timer
  "dailyQuizSize": 20,                 // questions in Daily Challenge
  "passPercent": 40,                   // pass line on result page
  "studentsPracticed": 12500,          // optional marketing number
  "auth": {                            // Google sign-in, anonymous-first (§20)
    "enabled": true,                   // false = whole feature inert
    "requireLogin": true,              // progress + leaderboard ask first
    "gateQuizzes": false,              // true = quizzes ask too (opt-in)
    "preview": true,                   // demo sign-in until Firebase keys exist
    "firebase": {                      // public web config — see §20
      "apiKey": "", "authDomain": "", "projectId": "", "appId": ""
    }
  }
}
```

### `data/subjects.json` — subject cards (+ optional categories)

```json
{
  "subjects": [
    { "id": "gk", "name": "General Knowledge", "short": "GK",
      "icon": "🏛️", "color": "#6366f1",
      "description": "History, Polity, Geography, Punjab GK, Science and more.",
      "order": 1,
      "categories": ["Polity", "History", "Punjab GK",
                     "Geography & Environment", "Economy", "Others"] }
  ]
}
```

* `id` **must** equal the folder name in `questions/`.
* There is **no `topics` array** — topics are detected from files at build time.
* `categories` is **optional**: add it only where you want the 3-level
  hierarchy (Subject › Category › Topic). Either plain name strings (folder
  name auto-generated) or `{ "name": "…", "folder": "…", "icon": "…" }`
  objects. Omit the key and the subject stays flat. Category folders found
  on disk but not listed here are auto-appended by the build.

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
* **Google sign-in, anonymous-first** — every quiz, mock and note opens with no sign-in at all; the blurred **Continue with Google** modal appears only on the personalised pages (progress, leaderboard), remembers students automatically, and syncs progress, attempts and the global leaderboard to their Google account ([§20](#20-google-sign-in--cloud-sync-firebase)).
* **Offline** — offline quizzes, PNG app icons, shortcuts & splash colours.

---

## 14. SEO files

* Title + description + canonical on every page
* Open Graph & Twitter card tags with `og-cover.png` (1200×630)
* JSON-LD `WebSite` + `SearchAction` + `Organization` schema (home)
* `robots.txt` + auto-generated `sitemap.xml` (subject pages included)
* Semantic HTML (`header/nav/main/section/footer`), single `h1`, alt text, skip link

> The site URL lives in three places: `data/site.json`, `robots.txt` and
> `index.html` — keep `https://houseofaspirants.in` in sync in all three.

---

## 15. Offline - service worker

* `manifest.webmanifest` — name, colours, PNG icons (192/512 + maskable) and shortcuts (Daily Quiz, Leaderboard).
* `sw.js` — app shell + question JSON are cached; quizzes work **fully offline** after first visit.
* The site ships **no install UI**: no prompt, no banner, no toast. Adding it to a home screen is done from the browser's own menu.

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

Google sign-in already runs on this model: `assets/js/auth.js` exposes
`HOA.auth.ensure / syncResult / fetchScores`, which talk to Firestore today
and can be pointed at any other API tomorrow (see §20).

---

## 18. Scalability notes

* **100,000+ MCQs** — questions are split into many small JSON files; the
  browser only fetches the topic you open (a few KB), never the whole bank.
* `data/index.json` stays tiny (metadata only: names + counts).
* Daily/Mock load only a handful of files per session.
* Storage caps: 500 bookmarks, 300 leaderboard rows, 120 days of progress —
  automatic, so localStorage never fills up.

---

## 19. Study guides & articles (no code)

Study guides power three things at once: the `/articles` hub, the **Related
study guides** card on every subject page, and the sitemap / Article schema.
One guide = **one `.html` file at the site root** + **one entry in
`data/articles.json`**.

**Add a new guide:**

1. Copy an existing guide (e.g. `punjab-gk-study-guide.html`) to a new
   root-level filename: `my-new-guide.html`.
2. Update its `<title>` (max 60 chars), meta description (140–160 chars),
   `canonical` and `og:url` (extensionless URL), breadcrumbs and
   body content.
3. Register it in `data/articles.json`:

```json
{
  "id": "my-new-guide",
  "title": "My New Guide — must match the page <title>",
  "url": "my-new-guide.html",
  "description": "Same 140–160 char text as the page meta description.",
  "subjects": ["gk"],
  "categories": ["punjab-gk"],
  "published": "2026-09-25",
  "modified": "2026-09-25"
}
```

4. Add a card for it on `articles.html` (copy an existing card).
5. Push — the build adds it to `sitemap.xml` automatically.

`subjects` decides **which subject pages** show the guide in their Related
cards; `categories` (optional) makes it rank **first** on that category page.
Guides are ranked most-specific first. `scripts/seo_check.py` verifies that
the file exists, title/description match the page, the hub cross-links it and
the sitemap contains it.

**Related subjects / quizzes cards** need no configuration — they render on
subject pages straight from `subjects.json` + `index.json` + `articles.json`.

---

## 20. Google sign-in & cloud sync (Firebase)

Study content is **anonymous-first**: Daily Quiz, topic quizzes, Latest-quiz
cards, related-quiz links and Mock Tests open for signed-out visitors with no
prompt at all. Sign-in is asked for only where an account adds something —
the personalised pages (progress and leaderboard). Signed-out visitors there
get a clean modal (background blur, benefits list, one **Continue with
Google** button); after signing in they land **directly on the requested
page**, never on an intermediate dashboard. Signed-in students are remembered
automatically, so the modal never shows again.

Set `auth.gateQuizzes: true` if you want the old behaviour where every quiz
entry checks sign-in first.

Everything is configured from `data/site.json` — no code changes, ever.

### 20.1 The `site.auth` block

| Key | Meaning |
|---|---|
| `enabled` | `false` → the whole feature is inert (old open behaviour) |
| `requireLogin` | `true` → progress + leaderboard ask for sign-in; `false` → nothing asks |
| `gateQuizzes` | `true` → quiz/mock entry asks too; `false` (shipped) → quizzes stay public |
| `preview` | `true` → demo sign-in (local only) until real Firebase keys exist |
| `firebase.*` | Your Firebase **web** config — public by design; `firestore.rules` guards the data |

Shipped default: `enabled: true`, `requireLogin: true`, `gateQuizzes: false`,
`preview: true` — every quiz and note is public, while the full flow (modal →
sign-in → progress → leaderboard) works immediately with a local demo profile.
**The moment you paste real Firebase keys, preview sign-in switches itself off
automatically** — demo profiles can never reach your Firestore.

### 20.2 Go live in 6 steps (free Spark plan)

1. <https://console.firebase.google.com> → **Add project** (Analytics optional).
2. **Build → Authentication → Get started → Sign-in method → Google → Enable** → Save.
3. **Build → Firestore Database → Create database** → *Production mode* → region `asia-south1` (closest to India).
4. **Project settings → Your apps → Web (`</>`)** → register the app → copy the `firebaseConfig` values.
5. Paste them into `data/site.json` → `auth.firebase` (fill every key you received; leave optional ones as `""`).
6. **Firestore → Rules** → paste the contents of [`firestore.rules`](firestore.rules) → **Publish**.

Then deploy (git push / `vercel --prod`). Also add your domain under
**Authentication → Settings → Authorised domains** (Firebase lists
`localhost` and your project domain by default).

### 20.3 What is stored where

| Data | Where | Used by |
|---|---|---|
| Google name, e-mail, photo, uid | `users/{uid}` | account card, leaderboard name |
| Progress stats (merged, never double-counted) | `users/{uid}` → `stats` | dashboard on any device |
| One document per completed quiz | `users/{uid}/attempts/{resultId}` | quiz history |
| Public attempt (name, score, %) | `leaderboard/{uid}_{at}` | global leaderboard |
| Bookmarks, theme, resume data | this device (`localStorage`) | unchanged |

Sync rules of thumb:

* Stats merge with **field-wise maximums** — a second device can never
  double-count or erase what you already earned.
* The leaderboard shows the **global board** to signed-in students and the
  local board to everyone else; offline always falls back to local.
* Quiz attempts are written once per result id — refreshing a result page
  never duplicates it.
* Nothing syncs in `preview` mode; it is purely on-device.

### 20.4 Troubleshooting the sign-in flow

| Symptom | Fix |
|---|---|
| “Sign-in isn’t configured yet” | No Firebase keys and `preview` is `false` → do §20.2 or set `auth.preview: true`. |
| “This domain isn’t authorised” | Firebase Console → Authentication → Settings → **Authorised domains** → add `houseofaspirants.in`. |
| “Google sign-in is switched off” | Authentication → Sign-in method → **Google → Enable**. |
| Popup blocked by the browser | The flow automatically falls back to full-page redirect sign-in. |
| Permission denied in Firestore console | Publish `firestore.rules` (step 6). |
| Quizzes should demand sign-in again | `data/site.json` → `auth.gateQuizzes: true` → redeploy. |

---

## 21. Troubleshooting

| Symptom | Fix |
|---|---|
| Topic not showing | Flat: `questions/<subject>/<topic>.json` · Categorized: `questions/gk/polity/<topic>.json` — valid JSON, then run the build and read its warnings. |
| Category page shows 0 topics | The file must sit inside the category folder (`questions/gk/polity/x.json`), not directly in `questions/gk/`. |
| Page is blank locally | You opened `file://` — use `npm start` or `python3 -m http.server 8000`. |
| Stats still 0 after adding questions | Redeploy / run the build; the manifest is generated at build time. |
| Build warning about a question | Fix the mentioned Q number (missing `q`, `options` or `correct`). The build never fails — it skips bad files. |
| `node: command not found` | Use `python3 scripts/build_index.py` instead. |
| Old version shows after update | Bump `VERSION` in `sw.js`. |
| Subject card looks default | Add its entry to `data/subjects.json` (`id` = folder name). |
| Telegram / social link wrong | Edit `data/site.json` → `telegram`, `instagram`, `youtube`. |

---

## 22. Telegram growth & conversion system

The site doubles as a conversion funnel for the
[House of Aspirants Telegram community](https://t.me/HouseOfAspirant) —
without ever forcing a join, blocking a quiz or hiding a result.

**UX rules baked into the code**

* Quizzes, results and downloads always work without joining Telegram.
* No popup on the quiz attempt page. Exit-intent runs desktop-only, once every
  7 days (`localStorage: hoa_exit_intent`), with a "Maybe Later" button.
* Rotating banners pause on hover/focus, stop entirely under
  `prefers-reduced-motion`, and expose a visible ⏸ pause control.
* The floating "📲 Free Study Material" button sits bottom-left (z-index below
  every overlay) and never covers page content.

**Where everything lives**

| Piece | File |
|---|---|
| Hero CTA, mentor card, 8 value-prop cards, desktop rail, between-categories rotator | `index.html` |
| 6-banner rotation (`TG_BANNERS`), `initTgRotators()`, exit intent, floating 📲 button, footer community block | `assets/js/core.js` |
| Quiz-completion celebration (🎉 + 5 benefits + Join / Continue to Result) | `assets/js/quiz.js` |
| Dashboard resource cards + "Telegram Community Benefits" | `progress.html` |
| "🏆 Improve Your Rank" block | `leaderboard.html` |
| Resource-lock cards (downloadable files only — never quizzes) | `articles.html` |
| All promo styling — `--tg-blue` accent is the AA-safe `#1a7ba6` | `assets/css/style.css` |
| Completion-screen styling | `assets/css/quiz.css` |

**Adding another rotating banner** — on any `.banner-telegram` block add
`data-tg-rotator`, put `data-tg-cta` on its link and insert
`<button type="button" class="tg-rot-pause" data-tg-pause aria-label="Pause banner rotation">⏸</button>`
before the closing tag. The banner's existing copy becomes slide 1. Quiz pages
must stay banner-free — enforced by `scripts/seo_check.py`.

---

## 23. Leaderboard & gamification

`leaderboard.html` is a mobile-first Global Rankings page (stats → season →
Daily/Weekly/Monthly/All Time tabs → exam/category/sort filters + instant
search → ranked rows → sticky **My Rank** → per-quiz boards → profile modal →
CTA grid). No page redesigns elsewhere; it reuses the existing `.page-hero`,
`.banner-telegram` and design tokens.

**Config — `data/site.json` → `site.leaderboard`** (flows verbatim into
`data/index.json` on every build):

```json
"leaderboard": { "enabled": true, "provider": "auto", "apiBase": "", "sample": true, "pageSize": 20 }
```

| `provider` | Meaning |
|---|---|
| `auto` *(default)* | Picks the first available one, in this order: `apiBase` set → `http` · Firebase configured → `firebase` · `sample` flag → `sample` · otherwise `local` |
| `http` | Your REST backend at `site.leaderboard.apiBase` |
| `firebase` | Firestore, using the rules in `firestore.rules` |
| `sample` | Deterministic demo board (seeded, 186 students) shown **with an honest disclosure chip and notice** |
| `local` | Only this device's attempts — never invents global rows |

Whatever the provider, the visitor's own device attempts are merged in as a
real `isMe` row, so **My Rank, XP, level, streak and percentile are always the
user's own data**. A backend failure degrades to `sample` instead of dying.

**Endpoint contract (the only TODO — `assets/js/leaderboard-api.js` →
`ENDPOINTS`)**

| Method | Path | Returns |
|---|---|---|
| GET | `/leaderboard?period=&exam=&category=&sort=&q=&page=&limit=` | `{entries: Entry[], total, hasMore}` |
| GET | `/leaderboard/stats?period=` | `{students, attempts, accuracy, activeToday, highestToday}` |
| GET | `/leaderboard/quizzes?period=` | `{quizzes: [{quizId, quizName, total, entries}]}` |
| POST | `/leaderboard/attempts` (body = Entry) | `204` |

Set `site.leaderboard.apiBase` and the `http` provider takes over — **no
front-end change required**. Responses are already normalised by
`fromApi()`/`paginate()`; ranking, filtering, search and pagination run
client-side so every provider behaves identically. Move aggregation
server-side above ~100k students.

**Entry shape** — `userId, name, username, profilePhoto, quizName, score,
totalQuestions, accuracy, timeTaken, xp, level, streak, badges[], attemptDate`
(+ `rank`, `verified`, `isMe`, `percentile` once ranked).

**Rules** live in `assets/js/gamification.js` (`HOA.game`): XP (+10/correct,
+100 perfect, +25 daily login, +150 7-day streak, +500 30-day, +1000 for 100
tests), levels (L1 0, L2 250, L3 600, then a +45% gap rounded to ×5), the eight
badges, and the monthly season countdown. `verified` is only ever set for real
Google accounts — demo rows are never marked verified.

**Files**

| Piece | File |
|---|---|
| Page | `leaderboard.html` |
| Styles | `assets/css/leaderboard.css` |
| Controller | `assets/js/leaderboard.js` |
| Provider abstraction | `assets/js/leaderboard-api.js` |
| XP / levels / badges / season | `assets/js/gamification.js` |
| Config | `data/site.json` → `site.leaderboard` |

---

## 24. Content system — Markdown to live pages (no CMS, no code)

Everything on the site that is *written* (as opposed to *built*) lives as
Markdown under **`content/`**. One command turns it into static HTML with its
own metadata, schema, breadcrumbs, TOC and internal links:

```bash
node scripts/build_content_manifest.ts # scan the PDFs in content/ first
python3 scripts/build_content.py       # build once (Markdown + the PDF inventory)
python3 scripts/build_content.py --strict # build + fail on any warning
bash scripts/ci.sh                     # scan → content → manifest → landing → gates
```

### What lives where

| Folder | Becomes | Notes |
|---|---|---|
| `content/notes/*.md` | `note-<slug>.html` + cards on `study-notes.html` | + sibling `<slug>.pa.md` for the Punjabi edition |
| `content/current-affairs/*.md` | `ca-<slug>.html` + cards on `current-affairs.html` | explained CA, linked to the CA quiz set |
| `content/monthly-magazine/*.md` | `magazine-<slug>.html` + cards on `magazine.html` | cover, PDF, highlights, linked quiz |
| `content/strategy/*.md` | `strategy-<slug>.html` + cards on `strategy.html` | study plans, revision, mistakes, motivation |
| `content/live-sessions/*.md` | `session-<slug>.html` + cards on `live-sessions.html` | emits `Event` schema **only** with `date` + `start_time` |
| `content/recruitment/*.md` | `recruit-<slug>.html` + cards on `recruitment.html` | official source required |
| `content/blogs/*.md` | `blog-<slug>.html` + cards on `blogs.html` | the reflective side of preparation |
| `content/news/*.md` | `news-<slug>.html` + cards on `news.html` | restated only from the official notification |
| `content/announcements/*.md` | `announce-<slug>.html` + cards on `announcements.html` | what changed on this platform, and when |
| `content/pdfs/*.md` | record on `pdfs.html` (no page — the PDF *is* the artefact) | `file:` must exist |
| `content/personal-notes/*.md` | `pnote-<slug>.html` + cards on `personal-notes.html` | a method that was really used, written up afterwards |
| `content/subject-guides/*.md` | `sguide-<slug>.html` + cards on `subject-guides.html` | one subject end to end |
| `content/topic-guides/*.md` | `tguide-<slug>.html` + cards on `topic-guides.html` | one topic: scope, exceptions, practice |
| `content/daily-practice/*.md` | `practice-<slug>.html` + cards on `daily-practice.html` | a dated set and what to fix after attempting it |
| `content/success-stories/*.md` | `story-<slug>.html` + cards on `success-stories.html` | one honest attempt (`exam:` required) |
| `content/book-recommendations/*.md` | `book-<slug>.html` + cards on `book-recommendations.html` | one book, judged for this syllabus |
| `content/<folder>/*.pdf` | `<prefix>-<slug>.html` (+ the collection hub card) | **a PDF alone is enough** — no Markdown, no front matter |

### Drop a PDF, get a page

A PDF in any collection folder publishes from its file name. The scanner
derives the metadata and the builder runs the record through exactly the
pipeline a Markdown document uses:

```bash
cp "Current Affairs July 2026.pdf" content/monthly-magazine/
node scripts/build_content_manifest.ts
#  ℹ pdf drops: 1 file(s) described -> data/content-manifest.json
python3 scripts/build_content.py
#  ℹ content/monthly-magazine/Current Affairs July 2026.pdf -> magazine-current-affairs-july-2026.html
```

* **Two steps, both automatic** — `scripts/build_content_manifest.ts` walks
  `content/**`, derives each file's metadata and writes it into the **`drops`**
  inventory of `data/content-manifest.json` (stamping `data/pdf-meta.json` on
  the way). `build_content.py` then publishes *from that inventory* and never
  opens a folder itself, so the manifest is the one list the pages, the sitemap
  and the SEO gate read. Adding, renaming or deleting a file needs no other
  edit anywhere — `node scripts/build_content_manifest.ts --check` fails the
  build if the committed inventory is stale.
* **Date** — `2026-08-12`, `July 2026` or `2026-07` in the name wins;
  otherwise the date the file first appeared is remembered in
  `data/pdf-meta.json`, so a rebuild on another machine emits the same bytes
  (the determinism rule `scripts/ci.sh` step 7 depends on).
* **Subfolders count** — `content/monthly-magazine/english/CA August.pdf`
  publishes too: the scanner walks the collection folder, not just its top
  level. Files with the same name in sibling folders are told apart by the
  folder name in their title, never by a guess.
* **Same name as a Markdown file** — `Quant Shortcuts.pdf` next to
  `quant-shortcuts.md` becomes that document's download, not a second page.
* **`content/pdfs/`** — listed on `pdfs.html` with its download button (that
  hub has no pages: the PDF is the artefact).
* **Fields a file name cannot carry** (`subject`, `post`, `official_url`)
  are simply absent; the page and its card lead with *PDF download* instead
  of inventing them. Nothing else changes — design, Quiz Engine, SEO rules
  and the 95+ gates are untouched.
* **English, Punjabi and mixed names** — `ਪੰਜਾਬੀ ਨੋਟ.pdf` derives title
  *ਪੰਜਾਬੀ ਨੋਟ*, slug `panjabi-not` and `language: pa` in the inventory. A PDF
  has no Punjabi twin to switch to, so it still publishes at the root and the
  language switch stays honest.
* **Read out of the file, not the name** — the scanner also opens the PDF:
  `pages` (the page count it declares), `summary` (the first page that reads
  like prose — clipped to 300 characters) and `thumbnail` (a preview of page
  one, drawn once to `assets/img/pdf/<hash>.jpg` and committed, with the
  `thumbW`/`thumbH` of the pixels actually written). A summary never quotes
  the welcome page every PDF opens with, because the brand match runs on the
  page's **opening** only — every page carries the brand in its footer — and
  where the file's own `/ToUnicode` maps a glyph to itself the glyph's name
  inside the embedded font decides what it really says.
* **What that puts on the page** — a first-page preview at the top (the
  issue-cover box, so the layout does not move), a **Summary** section in the
  file's own words (also the search row and the JSON-LD `abstract`), `11
  pages` beside the size on the Download line, a **Related PDFs** group of
  the PDFs it sits beside (its folder first, then its collection, then the
  rest of the library — three at most, chosen from the inventory alone), and
  `LearningResource` JSON-LD: `learningResourceType: PDF`, the file as its
  `encoding` (`DataDownload` + `contentUrl`), the summary as its `abstract`.
  `scripts/seo_check.py` checks all five new inventory fields.

### What the build generates around them (Phase 4)

* **Index pages** — `search.html` (crawlable GET search), `author-<id>.html`
  for every entry in `data/authors.json` with `profile: true`, and
  `archive-tag-<slug>.html` / `archive-category-<slug>.html` for every tag and
  category an English document really carries. All are registered in
  `data/content-manifest.json`, so the sitemap, canonical tags and chrome
  checks cover them, and each disappears again when the last document that
  justified it goes.
* **Filters** — listings with more than one document render a chip bar
  (Exam / Subject / Language / Difficulty / Date / Category) that filters the
  already-shipped DOM locally.
* **Bylines** — `data/authors.json` decides who may sign a document; an
  unknown name fails the build, a profiled author gets a `ProfilePage` and a
  footer link, everything else stays the site Organization.
* **Search fields** — every document row in `data/search-index.json` also
  carries its summary, keywords, author and difficulty.

Each folder has its own `README.md` with the front-matter schema for that
collection; `content/README.md` holds the hard rules.

**Language URLs:** English publishes at the site root
(`houseofaspirants.in/<prefix>-<slug>`), Punjabi under `/pa/`
(`houseofaspirants.in/pa/<prefix>-<slug>`). The pair ships reciprocal
`hreflang`, a language badge and a language switch — neither language is a
hidden fallback.

### The rules the builder enforces

* `title` ≤ 60 chars, `description` 140–160 chars, ISO dates — it refuses to
  write anything if a file is off (fail-fast, nothing half-built).
* **Recruitment links must be official** (`.gov.in`, `.nic.in`, `pspcl.co.in`)
  and every field is a *summary of the notification*, never a paraphrase of a
  rumour. Eligibility / syllabus / dates blocks render only when the Markdown
  carries them — empty means honest silence, not filler.
* **No invented byline.** Author is the House of Aspirants editorial brand.
* **No fabricated facts.** The builder validates structure, not truth: the
  writer does that. Nothing is auto-generated.
* Punjabi is opt-in per file (`<slug>.pa.md`); an English page never links to a
  Punjabi page that does not exist.
* **Drafts are validated but never published** — `draft: true` keeps a document
  out of the pages, sitemap, RSS, search index and archive until it is ready.

### What the build wires up automatically

sitemap entry (0.6 priority) · `Article`/`Event`/`CollectionPage` JSON-LD ·
BreadcrumbList · Open Graph + Twitter cards · reciprocal `hreflang` · reading
time, difficulty, exam and subject badges · table of contents + scrollspy ·
related notes and related quizzes · previous/next · share row · homepage feed
blocks (hidden until the first file exists) · stale-page cleanup (root **and**
`/pa/`).

### What Phase 2 added to the same run

* **Navigation is data, not markup** — the Study menu, drawer Study group and
  footer Study column are rewritten between `<!-- HOA-NAV:* -->` markers in
  `assets/js/core.js` from the `HUBS` table, so a new folder reaches the header,
  drawer, footer, sitemap and search index in one build.
* **Content Index** — `data/content-manifest.json` (hubs, index pages, every
  document with its language pair, category, author and reading time, plus
  `drops`: the PDF inventory written by `scripts/build_content_manifest.ts`
  and read by the publisher, the sitemap and the SEO gate).
* **Full-site search** — `data/search-index.json` over title, description,
  body, tags, subjects, exams and categories; fetched lazily when the search
  overlay first opens, so it costs nothing on page load.
* **RSS** — `feed.xml` (RSS 2.0, newest 20, dates derived from `published`
  only, so rebuilds are byte-identical).
* **Archive** — `archives.html`: latest posts, popular posts (only when
  `data/popularity.json` holds real counts) and every document grouped by
  subject, exam and month.
* **Learning path** — every document links the next real step (note → related
  quiz → current affairs → magazine → strategy); Previous Year Questions and
  Expected MCQs render as dimmed *reserved* steps until verified data exists.

### What Phase 3 added to the same run

* **11 content templates** (`scripts/content_engine.py`) — Study Note,
  Current Affairs, Monthly Magazine, Expected MCQs, Previous Year Questions,
  Preparation Strategy, Weekly Live Session Summary, Recruitment Notification,
  Exam Analysis, Motivation Article, Book Review. Each one owns its front
  matter contract, its JSON-LD type, its table-of-contents rules and its
  recommendation plan.
* **`scripts/new_content.py`** — scaffolds a correctly-shaped draft from a
  template into `content/_drafts/` (never loaded by the build), so an
  unfinished draft cannot break CI.
* **Facet recommendation engine** — every document ranks its related content
  on subject (6), exam (4), tags (3), category (3), difficulty (2), featured
  (2) and shared section (1); language is a tie-break, never a reason to call
  two documents related. Slots whose data does not exist yet render a single
  honest *Reserved* line instead of a dead link.
* **Recommendation blocks per page type** — a study note recommends the
  practice quiz, subject hub, current affairs, expected MCQs and previous
  papers plus next/previous chapter; current affairs recommends the magazine
  issue, a set, related news, schemes and Punjab GK; recruitment recommends
  eligibility, syllabus, strategy, books, papers, expected questions and the
  live session, with on-page anchors for eligibility and syllabus when the
  document declares them.
* **`data/content-graph.json`** — nodes (every hub, document and archive),
  contextual edges (re-read out of the shipped `<main>` markup, so the graph
  can never claim a link the site does not serve) and 28 silos: subject and
  exam pillar → hub → cluster → leaf.
* **Link floor** — every page carries at least five contextual internal links
  inside `<main>`; a page short of them gets an "Explore the library" module,
  and `seo_check.py` fails the build if any page still falls below five.
* **Homepage engine** — measured popularity for Popular notes / Trending quiz
  (ships off) plus *Continue learning* and *Recommended for you* computed in
  the browser from this reader's own last subject and bookmarks.

**Reserved, inactive until real data exists:** Previous Year Questions,
Expected Questions and Mock paper pages. The types and templates are ready;
nothing renders and nothing is linked until verifiable sources land — see
`content/README.md`.

---

### Support

* Telegram: [t.me/HouseOfAspirant](https://t.me/HouseOfAspirant)
* Instagram · YouTube — links in the site footer.

---

## 25. Multilingual quizzes — one topic, many languages

**One quiz = one topic.** Language is a *view* of a quiz, never part of its
identity. The topic id, the URL, search, bookmarks, XP, progress, the
leaderboard and analytics are all keyed on the topic id alone — so switching
language never restarts a quiz, never drops an answer and never creates a
second card.

### How a translation is recognised (no config to write)

Drop a translation next to the original and mark it with a **file-name
language marker**, or put it in a **language folder**:

| Shape | Example |
| --- | --- |
| folder | `questions/gk/punjab-gk/English/sikhism-part1.json` + `…/Punjabi/sikhism-part1.json` |
| word marker | `sikhism-part1-punjabi.json`, `…-english.json`, `…-gurmukhi.json` |
| dotted code | `sikhism-part1.en.json`, `sikhism-part1.pa.json`, **`sikhism-part1.ta.json`** |

The dotted form accepts any 2–3 letter ISO code, so **adding a language is a
data change only**: copy a JSON file, translate it, save it as `topic.ta.json`,
run the build — Tamil appears in the badge, in the in-quiz switch and in the
manifest with zero code changes. (Word markers are table-driven in `LANG_WORDS`
inside both builders, because `…-mcq` and `…-ta` cannot be told apart by
shape.)

Two files become one topic when **either** their stems match with the language
marker stripped, **or** their JSON `topic` + part token match — always within
the same subject and category. Two files in the *same* language are never
grouped (that would swallow a topic instead of pairing it). The English file
becomes the primary record when it exists, otherwise the first by
`(language, file)`.

### What the build emits

Each record in `data/index.json` carries the topic and its translations:

```json
{
  "id": "sikhism-part1-20-mcqs",
  "variants":            { "en": "…/sikhism-part1-20-mcqs.json", "pa": "…/…-punjabi.json" },
  "availableLanguages":  ["en", "pa"],
  "titles":              { "en": "Sikhism (Sikh Dharam) - Part 1", "pa": "Sikhism (Sikh Dharam) - Part 1" },
  "counts":              { "en": 30, "pa": 30 }
}
```

`data/quiz-manifest.json` is a flat, timestamp-free projection of exactly that
(`version`, `topics[]` with `id`, `subject`, `category`,
`availableLanguages`, `count`, `counts`, `titles`, `variants`) — the contract
tooling and future front ends should read instead of walking question files at
page load. Both builders emit it byte-for-byte identically and `ci.sh` diffs it.

### What the reader sees

* **one card per quiz** — the four Sikhism sets are four cards, not eight —
  with a `ਪੰ · EN` badge only when two languages really exist, and a plain
  `English` / `Punjabi` label on a single-language subject card;
* the quiz opens in the reader's language (Punjabi by default) and switches
  **inside** the quiz: question text and options are replaced while the
  question number, answers, marks, palette, running score and both countdowns
  stay exactly where they were;
* a missing translation falls back preferred language → English → whatever
  exists, and never errors;
* search, the Daily Challenge and Mock Tests resolve through the same helper
  (`pickVariantFile()`), so one search for "Sikhism" returns four quizzes, not
  eight.

### Validation — warnings, never crashes

At build time every pair must agree on question count, question ids, option
count and the option marked correct (saved answers are indices, so drift would
silently re-point them). A disagreement prints
`Translation mismatch: <file> …` once per pair and the build still succeeds.
The browser runs the same check when switching language: it refuses the swap,
warns in the console and keeps the current language.

### Type checking (no bundler, no transpile)

The site ships plain scripts, so type safety comes from `// @ts-check` +
JSDoc, `jsconfig.json` and `assets/js/hoa-types.d.ts` (the `window.HOA`,
`gtag`, `dataLayer` globals):

```bash
npm run typecheck      # tsc --noEmit -p jsconfig.json — 0 errors
bash scripts/ci.sh     # 7 gates, including the type check
```

## 26. Auto-publish watcher — you never run `npm run publish`

`scripts/watch_content.mjs` watches `content/` recursively. The moment a PDF
is **added, modified or deleted**, it runs `npm run publish` end to end, then
commits anything left over and pushes `main`.

```bash
npm run watch                 # foreground — useful to watch it work
```

### Run it in the background (macOS, survives restarts)

```bash
bash scripts/watch_service.sh install    # start now, and at every login
bash scripts/watch_service.sh status     # is it alive?
bash scripts/watch_service.sh logs       # follow its output
bash scripts/watch_service.sh restart    # bounce it
bash scripts/watch_service.sh stop       # stop until the next login
bash scripts/watch_service.sh uninstall  # stop for good
```

`install` writes `~/Library/LaunchAgents/com.houseofaspirants.content-watch.plist`
and boots it into launchd. `RunAtLoad` starts it the moment you log in and
`KeepAlive` restarts it if it ever crashes, so **after a computer restart you
do nothing — it is already watching**. Output accumulates in
`~/Library/Logs/houseofaspirants-content-watch.log`.

Verify it after a restart:

```bash
bash scripts/watch_service.sh status
# ✓ loaded in launchd
# ✓ process running (pid …)
```

### What you see

```
✓ PDF detected
✓ Publishing...
✓ Build successful
✓ Pushing...
✓ Website Live
```

### How the events are handled

| behaviour | how |
| --- | --- |
| duplicate events ignored | every event re-stats every PDF under `content/`; only a real difference counts |
| waits for the copy to finish | the 3-second timer restarts on each event, so publishing starts 3 s after the **last** change |
| a folder of PDFs copied at once publishes **once** | all changes collect into a single batch, one publish |
| PDFs only | `content/README.md` and other non-PDF files are never a trigger |
| never two builds at once | a change arriving mid-build is queued for the next cycle |

### Where the commits come from

1. `publish.sh` commits its own build output as `publish content`.
2. The watcher then runs `git add -A` and, **if anything is still uncommitted**
   (a change made outside the build), commits it as `content: auto publish`.
3. `git push origin main` → `✓ Website Live`.

### One-time setup: push authentication

The watcher pushes over **SSH**, so it never needs a password or a GUI
keychain prompt — neither of which a background job could answer.

```bash
[ -f ~/.ssh/id_ed25519 ] || ssh-keygen -t ed25519 -N "" -C "houseofaspirants-autowatch" -f ~/.ssh/id_ed25519
cat ~/.ssh/id_ed25519.pub      # → GitHub → Settings → SSH and GPG keys → New SSH key
ssh -T git@github.com          # expect: Hi Houseofaspirants/opencode-quiz! …
```

Until the key is added, every publish still builds, gates and commits — only
the push fails, and the watcher logs the reason instead of `✓ Website Live`.
Nothing is ever lost; the next run pushes the backlog.

**© House of Aspirants** — Practice Daily. Crack Punjab Police.
