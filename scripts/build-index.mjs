#!/usr/bin/env node
/**
 * ============================================================================
 *  HOUSE OF ASPIRANTS QUIZ PORTAL - AUTO INDEX BUILDER
 * ----------------------------------------------------------------------------
 *  Scans the  questions/  folder and generates:
 *    • data/index.json   -> the single manifest consumed by the front-end
 *    • sitemap.xml       -> SEO sitemap (rebuilt on every deploy)
 *
 *  ADMIN WORKFLOW (NO CODE, EVER):
 *    1. Create one JSON file, e.g.  questions/gk/indian-history.json
 *    2. Push to GitHub  ->  Vercel runs this script automatically
 *    3. The topic appears as a quiz card. Edit = update. Delete = removed.
 *
 *  IMPORTANT:
 *    • This script NEVER creates, generates or modifies questions.
 *    • It only READS your files and counts them.
 *    • The database starts completely EMPTY - that is expected.
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
      _topicsById: new Map(),
    });
  }
  return Object.assign(subjects.get(id), extra);
}

/* --------------------------------------------- 3. SCAN questions/ FOLDER
 *  EVERY *.json file found here becomes one Topic (one Quiz).
 *  No file = no topic. Delete a file = topic disappears. Nothing else to do. */
let questionFiles = [];

if (!fs.existsSync(QUESTIONS_DIR)) {
  warn("questions/ folder not found. Create it - subjects are detected from it.");
} else {
  for (const entry of fs.readdirSync(QUESTIONS_DIR, { withFileTypes: true })) {
    if (!entry.isDirectory()) continue; // ignore stray files / .gitkeep
    const subjectDir = path.join(QUESTIONS_DIR, entry.name);
    for (const file of fs.readdirSync(subjectDir)) {
      if (!file.endsWith(".json")) continue; // only JSON files become quizzes
      questionFiles.push({ subjectId: entry.name, file, subjectDir });
    }
  }
}

let totalQuestions = 0;
let quizCount = 0;

for (const { subjectId, file, subjectDir } of questionFiles) {
  const rel = `questions/${subjectId}/${file}`;
  const full = path.join(subjectDir, file);
  const id = file.replace(/\.json$/, "");

  let data;
  try {
    data = readJSON(full);
  } catch (err) {
    warn(`${rel} - invalid JSON, skipped: ${err.message}`);
    continue;
  }

  // Accept: [ ...questions ]  OR  { "questions": [ ... ] }  OR { "mcqs": [...] }
  const questions = Array.isArray(data)
    ? data
    : data.questions || data.mcqs || data.quiz || [];

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
  subject._topicsById.set(id, {
    id,
    name: (typeof data === "object" && !Array.isArray(data) && (data.topic || data.title)) || humanize(id),
    description: (typeof data === "object" && !Array.isArray(data) && data.description) || "",
    file: rel,
    count: questions.length,
    empty: isEmpty,
    available: !isEmpty, // an "available" quiz = a quiz that has questions
    timeLimit: Number(data.timeLimit) || 0,
    updatedAt: fs.statSync(full).mtimeMs,
  });

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
const outputSubjects = [...subjects.values()]
  .map((s) => {
    const topics = [...s._topicsById.values()].sort(
      (a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id)
    );
    delete s._topicsById;
    delete s._fromConfig;
    return { ...s, topics };
  })
  .sort((a, b) => a.order - b.order || a.name.localeCompare(b.name));

const countTopics = (fn) =>
  outputSubjects.reduce((n, s) => n + s.topics.filter(fn).length, 0);

const index = {
  version: 1,
  generatedAt: new Date().toISOString(),
  stats: {
    subjects: outputSubjects.length,
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
  `data/index.json - ${index.stats.subjects} subjects, ${index.stats.topics} topics, ${index.stats.quizzes} quizzes, ${index.stats.questions} questions`
);
if (index.stats.questions === 0) {
  console.log(
    "  \u2139 Database is EMPTY (as intended). Add questions/<subject>/<topic>.json to publish a quiz."
  );
}

/* ----------------------------------------------------------- 6. SITEMAP */
if (site.url) {
  const base = String(site.url).replace(/\/+$/, "");
  const today = new Date().toISOString().slice(0, 10);
  // ONLY indexable URLs are listed. Local-only pages (bookmarks, progress,
  // result) declare noindex and must stay out of the sitemap.
  const urls = [
    { loc: `${base}/`, p: "1.0" },
    { loc: `${base}/mock`, p: "0.9" },
    { loc: `${base}/leaderboard`, p: "0.7" },
    { loc: `${base}/about`, p: "0.6" },
    { loc: `${base}/contact`, p: "0.6" },
    { loc: `${base}/privacy`, p: "0.4" },
    { loc: `${base}/terms`, p: "0.4" },
  ];
  for (const s of outputSubjects) {
    urls.push({ loc: `${base}/subject?subject=${s.id}`, p: "0.9" });
    for (const t of s.topics.filter((x) => x.available)) {
      urls.push({ loc: `${base}/quiz?subject=${s.id}&topic=${t.id}`, p: "0.8" });
    }
  }
  const xml =
    `<?xml version="1.0" encoding="UTF-8"?>\n` +
    `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n` +
    urls
      .map(
        (u) =>
          `  <url><loc>${u.loc}</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq><priority>${u.p}</priority></url>`
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
