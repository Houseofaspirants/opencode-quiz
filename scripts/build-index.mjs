#!/usr/bin/env node
/* ============================================================================
 *  HOUSE OF ASPIRANTS QUIZ PORTAL - AUTO INDEX BUILDER
 * ----------------------------------------------------------------------------
 *  Scans the  questions/  folder and generates:
 *    • data/index.json   -> the single manifest consumed by the front-end
 *    • sitemap.xml       -> SEO sitemap (rebuilt on every deploy)
 *
 *  HIERARCHY (3 levels, config-driven):
 *      Subject  →  Category  →  Topic (one .json file)  →  Quiz
 *
 *    • Categories come from data/subjects.json ("categories" key per subject).
 *      Subjects without that key keep the original FLAT layout:
 *      questions/<subject>/*.json  →  topics directly under the subject.
 *    • Topic files are ALWAYS auto-detected inside their folder:
 *        questions/gk/polity/constitution.json   →  Polity › Constitution
 *      Add a file = a topic card appears. Edit = updated. Delete = removed.
 *      No topic name is ever hardcoded.
 *    • A category folder that exists on disk but is missing from the config is
 *      auto-appended, so nothing you upload can stay invisible.
 *
 *  ADMIN WORKFLOW (NO CODE, EVER):
 *    1. Drop a JSON file into a category folder, e.g.
 *         questions/gk/polity/constitution.json
 *    2. Push to GitHub  ->  Vercel runs this script automatically
 *    3. Subject › Category › Topic appears. Edit = update. Delete = removed.
 *
 *  IMPORTANT:
 *    • This script NEVER creates, generates or modifies questions.
 *    • It only READS your files and counts them.
 *    • Errors never crash the build: bad files are reported and skipped.
 * ============================================================================
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, "..");
const QUESTIONS_DIR = path.join(ROOT, "questions");
const DATA_DIR = path.join(ROOT, "data");

const readJSON = (p) => JSON.parse(fs.readFileSync(p, "utf8"));
const humanize = (id) =>
  String(id).replace(/[-_]+/g, " ").replace(/\b([a-z])/g, (m, c) => c.toUpperCase());
/* Folder / category slug: "Geography & Environment" -> "geography-environment" */
const slug = (s) =>
  String(s)
    .trim()
    .toLowerCase()
    .replace(/[&/\\]+/g, " ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
const hasJson = (dir) =>
  fs.readdirSync(dir).some((f) => f.endsWith(".json"));

/* --------------------------------------------------------------- languages --
 * A language bucket is a folder named for the language of the files inside it
 * (questions/<subject>/<Language>/...). It is a TRANSLATION axis, not a syllabus
 * category: "Punjabi" is not a lane of Current Affairs, it is the same content in
 * another language. Two translations of one set are paired up by
 * languageVariantKey() below and shipped as ONE topic carrying variants.
 * Kept in lockstep with build_index.py - see the parity harness notes there.
 */
const LANG_FOLDERS = {
  english: "en", eng: "en", en: "en",
  punjabi: "pa", panjabi: "pa", pa: "pa", gurmukhi: "pa",
};

const langCode = (dirname) => {
  const key = String(dirname).trim().toLowerCase();
  return LANG_FOLDERS[key] || LANG_FOLDERS[slug(dirname)] || null;
};

const PART_RX = /part[-_ ]?(\d+)/i;
const GURMUKHI_RX = /[\u0A00-\u0A7F]/;

/** Every .json under a language bucket, directly or one folder deeper.
 *  The repo has both shapes in use:
 *      questions/current-affairs/Punjabi/*.json
 *      questions/current-affairs/English/july/*.json
 *  Returns [fullPath, relPath] pairs in a deterministic order so the Node and
 *  Python twins walk the folders identically. */
function langFiles(subjectId, subjectDir, bucket) {
  const base = path.join(subjectDir, bucket);
  const out = [];
  for (const fname of fs.readdirSync(base).filter((f) => f.endsWith(".json")).sort()) {
    out.push([path.join(base, fname), `questions/${subjectId}/${bucket}/${fname}`]);
  }
  const dirs = fs
    .readdirSync(base, { withFileTypes: true })
    .filter((e) => e.isDirectory())
    .map((e) => e.name)
    .sort();
  for (const d of dirs) {
    const subBase = path.join(base, d);
    const files = fs.readdirSync(subBase).filter((f) => f.endsWith(".json")).sort();
    for (const fname of files) {
      out.push([path.join(subBase, fname), `questions/${subjectId}/${bucket}/${d}/${fname}`]);
    }
  }
  return out;
}

/** The name of a whole question SET. The house format is a bare array of
 *  questions, where `topic` sits on every question rather than on the file -
 *  so look at the file first, then fall back to question 0. */
const setTopicOf = (data) => {
  if (Array.isArray(data)) {
    const first = data[0] && typeof data[0] === "object" ? data[0] : null;
    return String((first && (first.topic || first.title)) || "");
  }
  if (data && typeof data === "object") {
    return String(data.topic || data.title || "");
  }
  return "";
};

/** Key shared by every translation of one question set.
 *  'current-affairs-july-2026-part1-geography-environment' (en) and
 *  'current-affairs-july-2026-part1-punjabi'              (pa) must land on the
 *  same key, so we pair on the part token plus the JSON topic rather than on the
 *  stem, which carries language-specific suffixes. */
function languageVariantKey(item, data) {
  const stem = item.file.replace(/\.json$/, "");
  const m = PART_RX.exec(stem);
  const part = m ? `part${Number(m[1])}` : "";
  const topic = slug(setTopicOf(data));
  if (part) return topic ? `${topic}/${part}` : part;
  // No part token: fall back to the stem minus a trailing language marker.
  return slug(stem).replace(/[-_](english|eng|punjabi|panjabi|gurmukhi|en|pa)$/, "");
}

/** True when the questions are written in Gurmukhi script. Used only for files
 *  that did NOT come from a language folder, where the folder name gives no
 *  signal. Script is an observed property of the text, not a guess about intent. */
function hasGurmukhi(questions) {
  for (const q of questions) {
    const qd = q && typeof q === "object" ? q : {};
    let opts = qd.options || qd.opts || [];
    if (!Array.isArray(opts)) opts = [];
    const text = [
      String(qd.question || qd.q || ""),
      String(qd.explanation || ""),
      ...opts.map((o) => String(o)),
    ].join(" ");
    if (GURMUKHI_RX.test(text)) return true;
  }
  return false;
}

let warnings = 0;
const warn = (msg) => {
  console.warn(`  \u26A0 ${msg}`);
  warnings++;
};
const info = (msg) => console.log(`  \u2714 ${msg}`);

console.log("\n\u{1F50D} House of Aspirants - building quiz index...\n");

/* ---------------------------------------------------------------- 1. CONFIG */
const sitePath = path.join(DATA_DIR, "site.json");
const subjectsPath = path.join(DATA_DIR, "subjects.json");
const site = fs.existsSync(sitePath) ? readJSON(sitePath) : {};
const meta = fs.existsSync(subjectsPath) ? readJSON(subjectsPath) : { subjects: [] };

const configSubject = (id) =>
  (meta.subjects || []).find((m) => m && m.id === id) || null;

/** Configured categories for a subject, or null when the subject has none.
 *  Accepts plain strings ("Polity") or objects ({name, folder, icon}). */
function configCategories(subjectId) {
  const m = configSubject(subjectId);
  const list = m && Array.isArray(m.categories) ? m.categories : null;
  if (!list) return null;
  const out = [];
  const seen = new Set();
  for (const raw of list) {
    if (!raw) continue;
    const isStr = typeof raw === "string";
    const name = isStr ? String(raw) : String(raw.name || raw.id || "").trim();
    if (!name) continue;
    const folder = (isStr ? slug(name) : String(raw.folder || raw.id || slug(name))).trim();
    const id = (isStr ? slug(name) : String(raw.id || slug(name))).trim();
    if (seen.has(id)) continue;
    seen.add(id);
    out.push({ id, name, folder, icon: isStr ? "" : String(raw.icon || "") });
  }
  return out;
}

/* ------------------------------------------------- 2. SUBJECT CONTAINERS */
const subjects = new Map();

function ensureSubject(id, extra = {}) {
  if (!subjects.has(id)) {
    subjects.set(id, {
      id,
      name: humanize(id),
      short: humanize(id),
      icon: "\u{1F4D8}",
      color: "#6366f1",
      description: "",
      order: 99,
      topics: [],
      categories: [],
      _topicsById: new Map(),
      _cats: null, // Map<folderKey, category> when the subject is hierarchical
    });
  }
  return Object.assign(subjects.get(id), extra);
}

/** Register (or fetch) a category inside a hierarchical subject. */
function ensureCategory(subject, key, preset = {}) {
  if (!subject._cats) subject._cats = new Map();
  if (!subject._cats.has(key)) {
    subject._cats.set(key, {
      id: preset.id || key,
      name: preset.name || humanize(key),
      folder: preset.folder || "",
      icon: preset.icon || "\u{1F4C1}",
      topics: [],
      _topicsById: new Map(),
    });
  }
  return subject._cats.get(key);
}

/* --------------------------------------------- 3. SCAN questions/ FOLDER
 *  Flat subject     : questions/<subject>/*.json
 *  Hierarchical     : questions/<subject>/<category>/*.json
 *  Every *.json file becomes exactly one Topic. No file = no topic.        */
let questionFiles = []; // { subjectId, file, full, rel, categoryId? }

if (!fs.existsSync(QUESTIONS_DIR)) {
  warn("questions/ folder not found. Create it - subjects are detected from it.");
} else {
  for (const entry of fs.readdirSync(QUESTIONS_DIR, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    if (!entry.isDirectory()) continue; // ignore stray files / .gitkeep
    const subjectId = entry.name;
    const subjectDir = path.join(QUESTIONS_DIR, subjectId);
    let subDirs = fs
      .readdirSync(subjectDir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name)
      .sort(); // deterministic order on every OS (parity with build_index.py)

    const cfgCats = configCategories(subjectId);

    /* Peel language buckets off BEFORE the flat/hierarchical decision: a folder
     * named for a language holds translations of one question set ("Punjabi" is
     * not a syllabus lane of Current Affairs), so it must never become a category
     * or decide the subject's layout. An explicit category with the same name
     * still wins. */
    const configured = new Set();
    for (const c of cfgCats || []) {
      for (const k of [c.folder, c.name, c.id]) if (k) configured.add(slug(k));
    }
    const langBuckets = subDirs.filter((d) => langCode(d) && !configured.has(slug(d)));
    if (langBuckets.length) {
      subDirs = subDirs.filter((d) => langBuckets.indexOf(d) === -1);
      for (const bucket of langBuckets) {
        for (const [full, rel] of langFiles(subjectId, subjectDir, bucket)) {
          questionFiles.push({
            subjectId, file: path.basename(full), full, rel, lang: langCode(bucket),
          });
        }
      }
    }

    const hierarchical = !!cfgCats || subDirs.some((d) => hasJson(path.join(subjectDir, d)));

    if (!hierarchical) {
      /* ---- FLAT subject (unchanged original behaviour) ---------------- */
      ensureSubject(subjectId);
      for (const file of fs.readdirSync(subjectDir).sort()) {
        if (!file.endsWith(".json")) continue;
        questionFiles.push({
          subjectId, file,
          full: path.join(subjectDir, file),
          rel: `questions/${subjectId}/${file}`,
        });
      }
      continue;
    }

    /* ---- HIERARCHICAL subject: config order first, disk folders next -- */
    const subject = ensureSubject(subjectId);
    if (cfgCats) {
      for (const c of cfgCats) {
        ensureCategory(subject, slug(c.folder), { ...c, name: c.name });
      }
    }

    for (const sub of subDirs) {
      const subPath = path.join(subjectDir, sub);
      const files = fs.readdirSync(subPath).filter((f) => f.endsWith(".json")).sort();
      const key = slug(sub);
      // Config match by slug(folder) | slug(name) | id — tolerant of naming.
      const preset =
        (cfgCats || []).find(
          (c) => slug(c.folder) === key || slug(c.name) === key || c.id === key
        ) || null;
      const cat = ensureCategory(subject, preset ? slug(preset.folder) : key, {
        id: preset ? preset.id : key,
        name: preset ? preset.name : humanize(sub.trim()),
        folder: preset ? preset.folder : sub.trim(),
        icon: preset ? preset.icon : "",
      });
      if (!preset && files.length) {
        info(`${subjectId}/${sub}/ - not in subjects.json, auto-added as category "${cat.name}"`);
      }
      for (const file of files) {
        questionFiles.push({
          subjectId, file, categoryId: cat.id,
          full: path.join(subPath, file),
          rel: `questions/${subjectId}/${sub}/${file}`,
        });
      }
    }

    /* JSON sitting directly in a hierarchical subject's root: never hide it */
    for (const file of fs.readdirSync(subjectDir).sort()) {
      if (!file.endsWith(".json")) continue;
      warn(
        `${subjectId}/${file} - not inside a category folder. ` +
          `Move it into questions/${subjectId}/<category>/ so it shows under a category.`
      );
      ensureCategory(subject, "uncategorized", {
        id: "uncategorized", name: "Uncategorized", folder: "",
      });
      questionFiles.push({
        subjectId, file, categoryId: "uncategorized",
        full: path.join(subjectDir, file),
        rel: `questions/${subjectId}/${file}`,
      });
    }
  }
}

/* ------------------------------ 3b. PAIR THE TRANSLATIONS OF ONE SET ------
 * A Punjabi file and its English twin describe the SAME 20 questions, so shipping
 * both as separate topics would double the library and put two near-identical
 * cards on the page. The primary file becomes the topic and its siblings ride
 * along as `variants`, which is what the quiz page uses to offer a language switch
 * without leaving the question you are on. */
function resolveLanguagePairs(items) {
  const normal = items.filter((i) => !i.lang);
  const multi = items.filter((i) => i.lang);
  if (!multi.length) return items;

  const groups = new Map();
  for (const i of multi) {
    let data = null;
    try {
      data = readJSON(i.full);
    } catch (err) {
      data = null; // the record loop reports the parse error for us
    }
    const key = JSON.stringify([i.subjectId, languageVariantKey(i, data)]);
    const m = PART_RX.exec(i.file.replace(/\.json$/, ""));
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key).push({
      item: i,
      part: m ? Number(m[1]) : 0,
      topic: setTopicOf(data),
    });
  }

  const out = normal.slice();
  for (const members of groups.values()) {
    // Code-point order (not localeCompare) so both twins sort identically.
    members.sort((a, b) => {
      const l = a.item.lang < b.item.lang ? -1 : a.item.lang > b.item.lang ? 1 : 0;
      if (l) return l;
      return a.item.file < b.item.file ? -1 : a.item.file > b.item.file ? 1 : 0;
    });
    // The English file owns the topic id/URL when it exists (descriptive stems);
    // the QUIZ page still decides what to SHOW from the reader's language
    // preference, which defaults to Punjabi.
    const primary = members.find((m) => m.item.lang === "en") || members[0];
    const variants = {};
    for (const m of members) {
      if (!(m.item.lang in variants)) variants[m.item.lang] = m.item.rel;
    }
    out.push({ ...primary.item, variants, part: primary.part, setTopic: primary.topic });
  }
  return out;
}

questionFiles = resolveLanguagePairs(questionFiles);

let totalQuestions = 0;
let quizCount = 0;

for (const {
  subjectId, file, full, rel, categoryId, lang, variants, part, setTopic,
} of questionFiles) {
  const id = file.replace(/\.json$/, "");

  let data;
  try {
    data = readJSON(full);
  } catch (err) {
    warn(`${rel} - invalid JSON, skipped: ${err.message}`);
    continue;
  }

  // Accept: [ ...questions ]  OR  { "questions": [ ... ] }  OR { "mcqs": [...] }
  // isObj also guards a JSON `null` file — property access on it must not throw.
  const isObj = typeof data === "object" && data !== null && !Array.isArray(data);
  const questions = Array.isArray(data)
    ? data
    : (isObj && (data.questions || data.mcqs || data.quiz)) || [];

  if (!Array.isArray(questions)) {
    warn(`${rel} - "questions" must be an array. File skipped.`);
    continue;
  }

  // Validate shape only (we never look at, generate or judge answer content).
  let ok = true;
  questions.forEach((q, i) => {
    const opts = q && (q.options || q.opts);
    const correct = q && (q.correct ?? q.answer ?? q.key);
    if (!q || !(q.q || q.question)) {
      warn(`${rel} - Q${i + 1} missing "q" text. Skipped file.`);
      ok = false;
    } else if (!Array.isArray(opts) || opts.length < 2) {
      warn(`${rel} - Q${i + 1} needs an "options" array. Skipped file.`);
      ok = false;
    } else if (correct === undefined || correct === null || correct === "") {
      warn(`${rel} - Q${i + 1} missing "correct" answer. Skipped file.`);
      ok = false;
    }
  });
  if (!ok) continue;

  const subject = ensureSubject(subjectId);
  const isEmpty = questions.length === 0; // valid file, but 0 questions yet

  const baseName = (isObj && (data.topic || data.title)) || humanize(id);
  // Parts 1-4 of one month all carry the same JSON "topic", so without this they
  // would be four identically named cards - and four identical <title>s.
  const name = part && setTopic ? `${setTopic} - Part ${part}` : baseName;

  // Language: a folder named for it is authoritative; otherwise read the script
  // the questions are actually written in. `variants` lists the translations that
  // really exist on disk - every badge and the quiz page's language switch are
  // driven by this field, never by an assumption.
  const language = lang || (hasGurmukhi(questions) ? "pa" : "en");
  const langVariants =
    variants && Object.keys(variants).length ? variants : { [language]: rel };

  const record = {
    id,
    name,
    description: (isObj && data.description) || "",
    file: rel,
    count: questions.length,
    empty: isEmpty,
    available: !isEmpty, // an "available" quiz = a quiz that has questions
    timeLimit: Number(isObj ? data.timeLimit : 0) || 0,
    // Whole milliseconds from nanoseconds - byte-identical to mtime_ms() in
    // scripts/build_index.py, so the two builders pass the parity gate in
    // scripts/ci.sh step 3 (a sub-ms float round-trips differently in Python).
    updatedAt: Number(fs.statSync(full, { bigint: true }).mtimeNs / 1000000n),
    ...(categoryId ? { category: categoryId } : {}),
    language,
    variants: langVariants,
  };

  if (subject._topicsById.has(id)) {
    warn(`${rel} - topic id "${id}" already exists in subject "${subjectId}". Rename this file.`);
  }
  subject._topicsById.set(id, record);

  const targetCat = categoryId
    ? [...(subject._cats || new Map()).values()].find((c) => c.id === categoryId)
    : null;
  if (targetCat) {
    if (targetCat._topicsById.has(id)) {
      warn(`${rel} - duplicate topic id in category "${targetCat.id}". Rename this file.`);
    }
    targetCat._topicsById.set(id, record);
  }

  totalQuestions += questions.length;
  if (!isEmpty) quizCount++;
}

/* ------------------------------- 4. REGISTER SUBJECTS FROM CONFIG + FOLDERS */
for (const m of meta.subjects || []) {
  if (!m || !m.id) continue;
  const s = ensureSubject(m.id, {
    name: m.name || humanize(m.id),
    short: m.short || m.name || humanize(m.id),
    icon: m.icon || "\u{1F4D8}",
    color: m.color || "#6366f1",
    description: m.description || "",
    order: typeof m.order === "number" ? m.order : 99,
  });
  s._fromConfig = true;
}

/* --------------------------------------------------------- 5. FINAL SHAPE */
const byName = (a, b) =>
  a.name.localeCompare(b.name) || a.id.localeCompare(b.id);

const outputSubjects = [...subjects.values()]
  .map((s) => {
    const topics = [...s._topicsById.values()].sort(byName);
    let categories = [];
    if (s._cats && s._cats.size) {
      categories = [...s._cats.values()].map((c) => {
        const cTopics = [...c._topicsById.values()].sort(byName);
        delete c._topicsById;
        return { ...c, topics: cTopics };
      });
    }
    delete s._topicsById;
    delete s._cats;
    delete s._fromConfig;
    return { ...s, topics, categories };
  })
  .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));

/* -------------------------------------------- 4b. LANDING PAGE CROSS-REF
 * data/landing-manifest.json is written by scripts/build_landing_pages.py.
 * When a static landing page exists for an entity, its record carries a
 * "landing" path so (a) the front-end canonicalises the query-string URL onto
 * it and (b) the sitemap lists the clean URL instead. No manifest (or a page
 * the generator has not built yet) keeps today's query-string behaviour. */
const LANDING = new Map();
const landPath = path.join(DATA_DIR, "landing-manifest.json");
if (fs.existsSync(landPath)) {
  try {
    for (const p of JSON.parse(fs.readFileSync(landPath, "utf8")).pages || []) {
      const f = String(p.file || "");
      if (f.endsWith(".html") && fs.existsSync(path.join(ROOT, f))) {
        LANDING.set(`${p.type}|${p.entity}`, `/${f.slice(0, -5)}`);
      } else {
        warn(`landing-manifest: file missing for ${f || p.url || "?"}`);
      }
    }
  } catch (e) {
    warn(`landing-manifest.json unreadable: ${e.message}`);
  }
}
const land = (kind, entity) => LANDING.get(`${kind}|${entity}`);

for (const s of outputSubjects) {
  const sl = land("subject", s.id);
  if (sl) s.landing = sl;
  for (const c of s.categories) {
    const cl = land("category", `${s.id}/${c.id}`);
    if (cl) c.landing = cl;
    for (const t of c.topics) {
      const ql = land("quiz", `${s.id}/${t.id}`);
      if (ql) t.landing = ql;
    }
  }
  for (const t of s.topics) {
    const ql = land("quiz", `${s.id}/${t.id}`);
    if (ql) t.landing = ql;
  }
}

const countTopics = (fn) =>
  outputSubjects.reduce((n, s) => n + s.topics.filter(fn).length, 0);
const countCategories = () =>
  outputSubjects.reduce((n, s) => n + s.categories.length, 0);

const index = {
  version: 2,
  generatedAt: new Date().toISOString(),
  stats: {
    subjects: outputSubjects.length,
    categories: countCategories(),
    topics: countTopics(() => true), // every JSON file = one topic
    quizzes: quizCount, // topics that currently hold questions
    questions: totalQuestions,
    studentsPracticed: Number(site.studentsPracticed) || 0,
  },
  site,
  subjects: outputSubjects,
};

fs.mkdirSync(DATA_DIR, { recursive: true });
fs.writeFileSync(path.join(DATA_DIR, "index.json"), JSON.stringify(index, null, 2));
info(
  `data/index.json - ${index.stats.subjects} subjects, ${index.stats.categories} categories, ` +
    `${index.stats.topics} topics, ${index.stats.quizzes} quizzes, ${index.stats.questions} questions`
);
if (index.stats.questions === 0) {
  console.log(
    "  \u2139 Database is EMPTY (as intended). Add questions/<subject>/<category>/<topic>.json to publish a quiz."
  );
}

/* ----------------------------------------------------------- 6. SITEMAP */
if (site.url) {
  const base = String(site.url).replace(/\/+$/, "");
  const today = new Date().toISOString().slice(0, 10);
  // ONLY indexable URLs are listed. (bookmarks/progress/result are indexable
  // utility pages — the 404 page and runtime noindex modes stay out.)
  const urls = [
    { loc: `${base}/`, p: "1.0" },
    { loc: `${base}/punjab-exams`, p: "0.9" },
    { loc: `${base}/faq`, p: "0.9" },
    { loc: `${base}/articles`, p: "0.8" },
    { loc: `${base}/mock`, p: "0.9" },
    { loc: `${base}/leaderboard`, p: "0.7" },
    { loc: `${base}/result`, p: "0.6" },
    { loc: `${base}/bookmarks`, p: "0.5" },
    { loc: `${base}/progress`, p: "0.5" },
    { loc: `${base}/about`, p: "0.6" },
    { loc: `${base}/contact`, p: "0.6" },
    { loc: `${base}/privacy`, p: "0.4" },
    { loc: `${base}/terms`, p: "0.4" },
    { loc: `${base}/editorial-policy`, p: "0.4" },
  ];
  // Study guides — config-driven from data/articles.json (same registry the
  // /articles hub, Related Articles modules and Article schema read).
  try {
    const guidesPath = path.join(DATA_DIR, "articles.json");
    if (fs.existsSync(guidesPath)) {
      for (const a of JSON.parse(fs.readFileSync(guidesPath, "utf8")).articles || []) {
        const page = String(a.url || "");
        if (page.endsWith(".html") && fs.existsSync(path.join(ROOT, page))) {
          urls.push({ loc: `${base}/${page.slice(0, -5)}`, p: "0.7" });
        } else {
          warn(`articles.json: page file missing for ${a.id || "?"} (${page})`);
        }
      }
    }
  } catch (e) {
    warn(`articles.json unreadable: ${e.message}`);
  }
  // Study notes, magazine, strategy, live sessions, recruitment and PDFs -
  // config-driven from data/content-manifest.json (scripts/build_content.py).
  try {
    const contentPath = path.join(DATA_DIR, "content-manifest.json");
    if (fs.existsSync(contentPath)) {
      const cm = JSON.parse(fs.readFileSync(contentPath, "utf8"));
      for (const hub of cm.hubs || []) {
        const u = String(hub.url || "");
        const f = String(hub.file || "");
        if (u.startsWith(base) && fs.existsSync(path.join(ROOT, f))) {
          urls.push({ loc: u, p: "0.8" });
        } else {
          warn(`content-manifest: hub missing for ${f || hub.collection || "?"}`);
        }
      }
      for (const item of cm.items || []) {
        const u = String(item.url || "");
        const f = String(item.file || "");
        if (u.startsWith(base) && fs.existsSync(path.join(ROOT, f))) {
          urls.push({ loc: u, p: "0.6" });
        } else {
          warn(`content-manifest: page missing for ${f || item.title || "?"}`);
        }
      }
      // Generated index pages (archives.html today) - same contract as hubs:
      // the URL only ships when the file really exists on disk.
      for (const page of cm.pages || []) {
        const u = String(page.url || "");
        const f = String(page.file || "");
        if (u.startsWith(base) && fs.existsSync(path.join(ROOT, f))) {
          urls.push({ loc: u, p: "0.7" });
        } else {
          warn(`content-manifest: index page missing for ${f || page.title || "?"}`);
        }
      }
    }
  } catch (e) {
    warn(`content-manifest.json unreadable: ${e.message}`);
  }
  for (const s of outputSubjects) {
    // Static landing page wins over the query-string variant; an entity the
    // generator has not built yet keeps the URL it has today.
    const sl = land("subject", s.id);
    urls.push({ loc: sl ? `${base}${sl}` : `${base}/subject?subject=${s.id}`, p: "0.9" });
    for (const c of s.categories) {
      const cl = land("category", `${s.id}/${c.id}`);
      urls.push({
        loc: cl ? `${base}${cl}` : `${base}/subject?subject=${s.id}&category=${c.id}`,
        p: "0.85",
      });
    }
    for (const t of s.topics.filter((x) => x.available)) {
      const tl = land("quiz", `${s.id}/${t.id}`);
      if (tl) {
        urls.push({ loc: `${base}${tl}`, p: "0.8" });
      } else {
        const cat = t.category ? `&category=${encodeURIComponent(t.category)}` : "";
        urls.push({ loc: `${base}/quiz?subject=${s.id}&topic=${t.id}${cat}`, p: "0.8" });
      }
    }
  }
  // Landing pages with no query-string variant: topic guides, exam pages and
  // subject clusters. (Subject, category and quiz landing pages are covered
  // by the loops above.)
  for (const [key, p] of [...LANDING.entries()].sort()) {
    const kind = key.split("|")[0];
    if (kind === "topic" || kind === "exam" || kind === "cluster") {
      const prio = { topic: "0.8", exam: "0.85", cluster: "0.7" }[kind];
      urls.push({ loc: `${base}${p}`, p: prio });
    }
  }
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls
      .map(
        (u) =>
          `  <url><loc>${u.loc.replace(/&/g, "&amp;")}</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq><priority>${u.p}</priority></url>`
      )
      .join("\n") +
    `\n</urlset>\n`;
  fs.writeFileSync(path.join(ROOT, "sitemap.xml"), xml);
  info(`sitemap.xml - ${urls.length} URLs`);
}

console.log(`\n\u2705 Index build complete.\n`);
if (warnings > 0) {
  console.log(
    `\u26A0\uFE0F ${warnings} warning(s) above - fix those JSON files so their quizzes publish.\n`
  );
}
