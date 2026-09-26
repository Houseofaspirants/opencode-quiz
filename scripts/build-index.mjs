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
    const subDirs = fs
      .readdirSync(subjectDir, { withFileTypes: true })
      .filter((d) => d.isDirectory())
      .map((d) => d.name)
      .sort(); // deterministic order on every OS (parity with build_index.py)

    const cfgCats = configCategories(subjectId);
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

let totalQuestions = 0;
let quizCount = 0;

for (const { subjectId, file, full, rel, categoryId } of questionFiles) {
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
  const record = {
    id,
    name: (isObj && (data.topic || data.title)) || humanize(id),
    description: (isObj && data.description) || "",
    file: rel,
    count: questions.length,
    empty: isEmpty,
    available: !isEmpty, // an "available" quiz = a quiz that has questions
    timeLimit: Number(isObj ? data.timeLimit : 0) || 0,
    updatedAt: fs.statSync(full).mtimeMs,
    ...(categoryId ? { category: categoryId } : {}),
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
  for (const s of outputSubjects) {
    urls.push({ loc: `${base}/subject?subject=${s.id}`, p: "0.9" });
    for (const c of s.categories) {
      urls.push({ loc: `${base}/subject?subject=${s.id}&category=${c.id}`, p: "0.85" });
    }
    for (const t of s.topics.filter((x) => x.available)) {
      const cat = t.category ? `&category=${encodeURIComponent(t.category)}` : "";
      urls.push({ loc: `${base}/quiz?subject=${s.id}&topic=${t.id}${cat}`, p: "0.8" });
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
