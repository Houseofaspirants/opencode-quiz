#!/usr/bin/env node
/**
 * build_content_manifest.ts | House of Aspirants
 * ==============================================================================
 * The PDF drop scanner:  content/**  ->  data/content-manifest.json
 *
 * The quiz side of the site already works like this - JSON drop, manifest
 * generated, the site updates. This is the same pipeline for every other piece
 * of content that ships as a file:
 *
 *   (default)        scan every PDF under content/, derive its metadata from the
 *                    file name alone, stamp its dates in data/pdf-meta.json and
 *                    write the `drops` inventory into data/content-manifest.json
 *   --check          verify the committed manifest and sidecar describe exactly
 *                    what is on disk right now (exit 1 on drift)
 *   --derive a b ..  print {title, slug, date} for file names, so scripts/ci.sh
 *                    can prove this scanner and scripts/build_content.py derive
 *                    identical documents
 *
 * Contract
 *   * one record per PDF: path, filename, folder, category (the subfolder the
 *     file was dropped in), title, slug, language, scripts, size, sizeLabel,
 *     published, modified;
 *   * English, Punjabi and mixed file names all derive - Gurmukhi keeps its own
 *     shape in the title and is transliterated for the slug;
 *   * add / delete / rename are the same operation: rescan. Nothing is edited
 *     by hand - not the HTML, not the JS, not this manifest;
 *   * `drops` is the ONLY list the publisher (scripts/build_content.py) reads:
 *     it never walks the folders itself.
 *
 * `data/pdf-meta.json` is stamped, not measured: today's date is written once
 * when a file first appears (or its bytes change) and then kept, because an
 * mtime in a committed file would look like content drift to scripts/ci.sh
 * step 7 on every fresh checkout.
 *
 * Zero dependencies. Plain `node scripts/build_content_manifest.ts` - Node 22.6+
 * runs .ts files straight through type stripping, so there is no bundler, no
 * transpile step and no install.
 */

import { createHash } from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// ---------------------------------------------------------------------------
// shapes
// ---------------------------------------------------------------------------

/** One PDF on disk, described entirely by its file name and location. */
type Drop = {
  path: string;        // "content/notes/chapter 1/mobile phone.pdf"
  filename: string;    // "mobile phone.pdf"
  folder: string;      // "notes" - the collection folder it was dropped in
  category: string;    // "chapter 1" - its subfolder, "" at the top level
  title: string;       // "Mobile Phone" - "" only when the name proves nothing
  slug: string;        // "mobile-phone" - ASCII, before any collision suffix
  language: string;    // "en" | "pa"
  scripts: string;     // "latin" | "gurmukhi" | "mixed" | "none"
  size: number;        // bytes
  sizeLabel: string;   // "5.1 MB"
  published: string;   // ISO date the document claims: its name, or first seen
  modified: string;    // ISO date its bytes last changed (stamped once)
};

type SidecarEntry = { hash: string; published: string; updated: string };
type Sidecar = { version: number; files: Record<string, SidecarEntry> };
type Manifest = {
  version?: number;
  domain?: string;
  drops?: Drop[];
  [key: string]: unknown;
};

type Derive = { stem: string; title: string; slug: string; date: string };

const DROP_KEYS: (keyof Drop)[] = [
  "path", "filename", "folder", "category", "title", "slug", "language",
  "scripts", "size", "sizeLabel", "published", "modified",
];

// ---------------------------------------------------------------------------
// paths
// ---------------------------------------------------------------------------

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..");
const CONTENT = path.join(ROOT, "content");
const MANIFEST_FILE = path.join(ROOT, "data", "content-manifest.json");
const SIDECAR_FILE = path.join(ROOT, "data", "pdf-meta.json");
const SCANNER = "scripts/build_content_manifest.ts";
const SKIP_DIRS = new Set(["_drafts"]);

// ---------------------------------------------------------------------------
// ports of the Python helpers in scripts/build_content.py
//
// scripts/ci.sh runs `--derive` against both implementations over a fixture
// list of file names, so these must answer exactly what Python answers.
// ---------------------------------------------------------------------------

const pad = (n: number, width = 2): string => String(n).padStart(width, "0");

/** Local calendar day - `datetime.date.today()` is local, toISOString is not. */
const today = (): string => {
  const d = new Date();
  return `${pad(d.getFullYear(), 4)}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

/**
 * Non-ASCII runs become one space. Python's `\b` is Unicode-aware, JavaScript's
 * is not; folding first makes both mean the same thing - and for the ASCII
 * names this site has always had it changes nothing at all.
 */
const asciiFold = (text: string): string =>
  text.replace(/[^\u0000-\u007F]+/g, " ");

/** `clip()` on code points: Python counts str, JavaScript counts UTF-16 units. */
const clip = (text: unknown, limit = 60): string => {
  const s = Array.from(String(text).trim());
  if (s.length <= limit) return s.join("");
  const prefix = s.slice(0, limit).join("");
  const i = prefix.lastIndexOf(" ");
  const cut = (i < 0 ? prefix : prefix.slice(0, i)).replace(/[ ,;:-]+$/, "");
  return cut || prefix;
};

const MONTH_NAMES = (
  "january february march april may june july august september october " +
  "november december"
).split(" ");
const MONTHS: Record<string, number> = {};
for (let i = 0; i < MONTH_NAMES.length; i++) {
  MONTHS[MONTH_NAMES[i]] = i + 1;
  MONTHS[MONTH_NAMES[i].slice(0, 3)] = i + 1;
}

const PDF_SMALL_WORDS = new Set("a an the of for and or in on to at by from vs".split(" "));
const PDF_ACRONYMS = new Set(
  (
    "ppsc psssb ssb pcs upsc ias ips ssc ibps rbi nta clat neet jee aiims nda " +
    "cds afcat si asi po gk gs mcq mcqs pyq pyqs pdf ca pstet ptet ctet reet " +
    "htet gb ukpsc hppsc jpse"
  ).split(" ")
);
if (PDF_SMALL_WORDS.size !== 14 || PDF_ACRONYMS.size !== 38) {
  // tripwire: the two word lists must be the ones scripts/build_content.py uses
  throw new Error(`${SCANNER}: acronym/small-word tables are the wrong size`);
}

/** `YYYY-MM-DD` for a real calendar date, or '' - Python's `datetime.date`. */
const isoDate = (y: number, m: number, d: number): string => {
  if (m < 1 || m > 12 || d < 1 || d > 31) return "";
  const leap = (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
  const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (d > days[m - 1]) return "";
  return `${pad(y, 4)}-${pad(m)}-${pad(d)}`;
};

/**
 * `2026-07-15`, `July 2026`, `july-2026`, `2026-07` -> ISO date, else ''.
 * A date the file cannot prove (one still in the future) is ignored.
 */
const pdfDateFromName = (stem: string): string => {
  const day = today();
  const text = asciiFold(String(stem)).toLowerCase();
  let found = "";
  let m = /\b(20\d{2})-(\d{1,2})-(\d{1,2})\b/.exec(text);
  if (m) {
    found = isoDate(Number(m[1]), Number(m[2]), Number(m[3]));
  }
  if (!found) {
    for (const pat of [
      /\b([a-z]{3,9})[\s._-]+(20\d{2})\b/,
      /\b(20\d{2})[\s._-]+([a-z]{3,9})\b/,
    ]) {
      m = pat.exec(text);
      if (!m) continue;
      const a = m[1];
      const b = m[2];
      const month = MONTHS[a] || MONTHS[b];
      if (!month) continue;
      const year = MONTHS[a] ? Number(b) : Number(a);
      found = `${pad(year, 4)}-${pad(month)}-01`;
      break;
    }
  }
  if (!found) {
    m = /\b(20\d{2})-(\d{1,2})\b/.exec(text);
    if (m && Number(m[2]) >= 1 && Number(m[2]) <= 12) {
      found = `${pad(Number(m[1]), 4)}-${pad(Number(m[2]))}-01`;
    }
  }
  return found && found > day ? "" : found;
};

/**
 * Gurmukhi -> Latin, so a Punjabi file name still earns a readable URL.
 * ASCII passes through untouched, which is why every name the site has today
 * derives exactly as it did before this map existed.
 */
const GURMUKHI_COMBOS: Record<string, string> = {
  "\u0A38\u0A3C": "sh", // ਸ + nukta, the sequence that spells ਸ਼
};
/** Consonant letters: nukta, vowel signs and digits sit outside these ranges. */
const GURMUKHI_CONSONANT = /[\u0A15-\u0A39\u0A59-\u0A5E]/;
/** BindI and tippi - the nasal that carries a syllable's inherent vowel. */
const GURMUKHI_NASAL = new Set(["\u0A02", "\u0A70"]);
const GURMUKHI: Record<string, string> = {
  // independent vowels
  "\u0A05": "a",    // ਅ
  "\u0A06": "a",    // ਆ  (long A, same Latin vowel as the sign ਾ)
  "\u0A07": "i",    // ਇ
  "\u0A08": "i",    // ਈ
  "\u0A09": "u",    // ਉ
  "\u0A0A": "u",    // ਊ
  "\u0A0F": "e",    // ਏ
  "\u0A10": "ai",   // ਐ
  "\u0A13": "o",    // ਓ
  "\u0A14": "au",   // ਔ
  // dependent vowel signs
  "\u0A3E": "a",    // ਾ  (ਪੰਜਾਬੀ -> "panjabi")
  "\u0A3F": "i",    // ਿ
  "\u0A40": "i",    // ੀ
  "\u0A41": "u",    // ੁ
  "\u0A42": "u",    // ੂ
  "\u0A47": "e",    // ੇ
  "\u0A48": "ai",   // ੈ
  "\u0A4B": "o",    // ੋ
  "\u0A4C": "au",   // ੌ
  "\u0A4D": "",     // ੍  virama: the half-form is implied by the next letter
  "\u0A02": "n",    // ਂ  bindi
  "\u0A03": "",     // ਃ  visarga
  "\u0A3C": "",     // ਼  nukta on its own (composite letters are mapped below)
  "\u0A70": "n",    // ੰ  tippi
  "\u0A71": "",     // ੱ  addak
  "\u0A74": "",     // ੴ  ek onkar
  // consonants
  "\u0A15": "k",    // ਕ
  "\u0A16": "kh",   // ਖ
  "\u0A17": "g",    // ਗ
  "\u0A18": "gh",   // ਘ
  "\u0A19": "ng",   // ਙ
  "\u0A1A": "ch",   // ਚ
  "\u0A1B": "chh",  // ਛ
  "\u0A1C": "j",    // ਜ
  "\u0A1D": "jh",   // ਝ
  "\u0A1E": "nj",   // ਞ
  "\u0A1F": "t",    // ਟ
  "\u0A20": "th",   // ਠ
  "\u0A21": "d",    // ਡ
  "\u0A22": "dh",   // ਢ
  "\u0A23": "n",    // ਣ
  "\u0A24": "t",    // ਤ
  "\u0A25": "th",   // ਥ
  "\u0A26": "d",    // ਦ
  "\u0A27": "dh",   // ਧ
  "\u0A28": "n",    // ਨ
  "\u0A2A": "p",    // ਪ
  "\u0A2B": "ph",   // ਫ
  "\u0A2C": "b",    // ਬ
  "\u0A2D": "bh",   // ਭ
  "\u0A2E": "m",    // ਮ
  "\u0A2F": "y",    // ਯ
  "\u0A30": "r",    // ਰ
  "\u0A32": "l",    // ਲ
  "\u0A33": "l",    // ਲ਼
  "\u0A35": "v",    // ਵ
  "\u0A36": "sh",   // ਸ਼
  "\u0A38": "s",    // ਸ
  "\u0A39": "h",    // ਹ
  "\u0A59": "kh",   // ਖ਼
  "\u0A5A": "gh",   // ਗ਼
  "\u0A5B": "z",    // ਜ਼
  "\u0A5C": "r",    // ੜ
  "\u0A5E": "f",    // ਫ਼
  // digits
  "\u0A66": "0", "\u0A67": "1", "\u0A68": "2", "\u0A69": "3", "\u0A6A": "4",
  "\u0A6B": "5", "\u0A6C": "6", "\u0A6D": "7", "\u0A6E": "8", "\u0A6F": "9",
};

/**
 * One file name to a Latin slug: `ਪੰਜਾਬੀ ਟੈਸਟ.pdf` -> `panjabi-taist`.
 * A nasal carries its syllable's inherent vowel (`ਪੰ` = p + a + n, so "pan"
 * and never "pn"); everything else is a straight letter-for-letter mapping.
 * ASCII never touches a Gurmukhi code point, so Latin names are unchanged.
 */
const translit = (stem: string): string => {
  const chars = Array.from(String(stem));
  let out = "";
  let pending = false; // last emit was a consonant with no vowel sign yet
  for (let i = 0; i < chars.length; i++) {
    const two = chars[i] + (chars[i + 1] || "");
    const combo = GURMUKHI_COMBOS[two];
    if (combo !== undefined) {
      out += combo;
      pending = true;
      i += 1;
      continue;
    }
    const one = chars[i];
    const mapped = GURMUKHI[one];
    if (GURMUKHI_NASAL.has(one)) {
      if (pending) out += "a"; // the syllable's inherent vowel
      out += "n";
      pending = false;
    } else if (GURMUKHI_CONSONANT.test(one)) {
      out += mapped === undefined ? one : mapped;
      pending = true;
    } else {
      out += mapped === undefined ? one : mapped;
      pending = false;
    }
  }
  return out;
};

const GURMUKHI_RANGE = /[\u0A00-\u0A7F]/;
const LATIN_RANGE = /[A-Za-z]/;
const ASCII_WORD = /^[\u0000-\u007F]+$/;
const NAME_WORD = /[^A-Za-z0-9\u0A00-\u0A7F]+/;

/**
 * `Current Affairs July 2026` <- `Current Affairs July 2026.pdf`.
 * Acronyms (PPSC, SI) and years keep their shape, Gurmukhi keeps its script,
 * everything else is title cased, and the answer fits the 60-char title limit.
 */
const pdfTitleFromName = (stem: string): string => {
  const raw = String(stem);
  // A date written into the name is parked while the rest of the name is
  // title cased - it is part of the document, not a word to be re-spaced.
  const iso = /\b20\d{2}-\d{1,2}(?:-\d{1,2})?\b/.exec(asciiFold(raw));
  const guard = iso ? iso[0] : "";
  let name = raw;
  if (guard) name = name.replace(guard, "Dateday");
  const words = name.split(NAME_WORD).filter((w) => w.length > 0);
  const out: string[] = [];
  for (const w of words) {
    if (!ASCII_WORD.test(w)) {
      out.push(w); // Gurmukhi keeps its own shape
    } else if (/\d/.test(w)) {
      out.push(w); // 2026, SI-2, v3 keep theirs
    } else if (PDF_ACRONYMS.has(w.toLowerCase())) {
      out.push(w.toUpperCase()); // ppsc -> PPSC, ca -> CA, pyq -> PYQ
    } else {
      out.push(w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
    }
  }
  for (let i = 0; i < out.length; i++) {
    if (i && PDF_SMALL_WORDS.has(out[i].toLowerCase())) out[i] = out[i].toLowerCase();
  }
  let title = out.join(" ");
  if (guard) {
    // Clip the words around the date - never through it.
    const at = title.indexOf("Dateday");
    const before = at < 0 ? title : title.slice(0, at);
    const tail = at < 0 ? "" : title.slice(at + "Dateday".length);
    const head = clip(before, Math.max(10, 60 - guard.length - 1));
    title = `${head.trim()} ${guard} ${tail.trim()}`.trim();
    if (Array.from(title).length > 60) title = clip(`${head.trim()} ${guard}`, 60);
  } else {
    title = clip(title, 60);
  }
  return title.split(/\s+/).filter(Boolean).join(" ");
};

/** Filename -> the slug rule every other document follows, or ''. */
const pdfSlugFromName = (stem: string): string => {
  const s = translit(String(stem))
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/-{2,}/g, "-")
    .replace(/^-+/, "")
    .slice(0, 64)
    .replace(/-+$/, "");
  return /^[a-z0-9][a-z0-9-]*$/.test(s) ? s : "";
};

/** Python's `f"{x:.1f}"` - half-to-even on a tie, not half-away-from-zero. */
const fixed1 = (x: number): string => {
  const scaled = x * 10;
  const floor = Math.floor(scaled);
  const frac = scaled - floor;
  let n = floor;
  if (frac > 0.5) n = floor + 1;
  else if (frac === 0.5) n = floor % 2 === 0 ? floor : floor + 1;
  return `${(n / 10).toFixed(1)}`;
};

const sizeLabel = (size: number): string =>
  size < 1024 * 1024
    ? `${Math.floor(size / 1024)} KB`
    : `${fixed1(size / (1024 * 1024))} MB`;

/**
 * Which language the file says it is. The name wins over the folder it sits
 * in, a name written in Gurmukhi wins over everything, English is the default.
 */
const languageOf = (stem: string, category: string, folder: string): string => {
  const name = stem.toLowerCase();
  const sub = (category || "").toLowerCase();
  const dir = (folder || "").toLowerCase();
  const pa = (s: string): boolean =>
    /(^|[^a-z])(punjabi|panjabi|gurmukhi|ਪੰਜਾਬੀ)([^a-z]|$)/.test(s) ||
    /\.pa([.-]|$)/.test(s);
  const en = (s: string): boolean =>
    /(^|[^a-z])(english|en)([^a-z]|$)/.test(s) || /\.en([.-]|$)/.test(s);
  if (GURMUKHI_RANGE.test(stem)) return "pa";
  if (pa(name)) return "pa";
  if (en(name)) return "en";
  if (pa(sub)) return "pa";
  if (en(sub)) return "en";
  if (pa(dir)) return "pa";
  if (en(dir)) return "en";
  return "en";
};

/** What the file name is written in - the "mixed names" requirement. */
const scriptsOf = (stem: string): string => {
  const gurmukhi = GURMUKHI_RANGE.test(stem);
  const latin = LATIN_RANGE.test(stem);
  if (gurmukhi && latin) return "mixed";
  if (gurmukhi) return "gurmukhi";
  if (latin) return "latin";
  return "none";
};

// ---------------------------------------------------------------------------
// scan
// ---------------------------------------------------------------------------

/** Python sorts Path objects: component by component, shorter prefix first. */
const byParts = (a: string[], b: string[]): number => {
  const n = Math.min(a.length, b.length);
  for (let i = 0; i < n; i++) {
    if (a[i] !== b[i]) return a[i] < b[i] ? -1 : 1;
  }
  return a.length - b.length;
};

const sha256 = (file: string): string =>
  createHash("sha256").update(fs.readFileSync(file)).digest("hex");

/** Every publishable PDF under one collection folder, in Python's order. */
const walk = (base: string): string[][] => {
  const found: string[][] = [];
  const rec = (dir: string, parts: string[]): void => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      const rel = parts.concat(entry.name);
      if (entry.isDirectory()) {
        // hidden folders and `_drafts` never publish: they are parent parts
        if (entry.name.startsWith(".") || SKIP_DIRS.has(entry.name)) continue;
        rec(full, rel);
        continue;
      }
      if (!entry.isFile()) continue;
      if (path.extname(entry.name).toLowerCase() !== ".pdf") continue;
      if (entry.name.toLowerCase().startsWith("readme")) continue;
      found.push(rel);
    }
  };
  rec(base, []);
  found.sort(byParts);
  return found;
};

/** Every PDF on disk, described. This is the whole inventory. */
const scan = (): Drop[] => {
  const drops: Drop[] = [];
  if (!fs.existsSync(CONTENT)) return drops;
  const folders = fs
    .readdirSync(CONTENT, { withFileTypes: true })
    .filter((e) => e.isDirectory() && !e.name.startsWith(".") && !SKIP_DIRS.has(e.name))
    .map((e) => e.name)
    .sort();
  for (const folder of folders) {
    const cdir = path.join(CONTENT, folder);
    for (const parts of walk(cdir)) {
      const name = parts[parts.length - 1];
      const stem = name.replace(/\.pdf$/i, "");
      const category = parts.length > 1 ? parts[parts.length - 2] : "";
      const file = path.join(cdir, ...parts);
      const rel = path.relative(ROOT, file).split(path.sep).join("/");
      const size = fs.statSync(file).size;
      drops.push({
        path: rel,
        filename: name,
        folder,
        category,
        title: pdfTitleFromName(stem),
        slug: pdfSlugFromName(stem),
        language: languageOf(stem, category, folder),
        scripts: scriptsOf(stem),
        size,
        sizeLabel: sizeLabel(size),
        published: pdfDateFromName(stem),
        modified: "",
      });
    }
  }
  return drops;
};

// ---------------------------------------------------------------------------
// data/pdf-meta.json - the stamped (never measured) dates
// ---------------------------------------------------------------------------

const readSidecar = (): Sidecar => {
  if (!fs.existsSync(SIDECAR_FILE)) return { version: 1, files: {} };
  try {
    const data = JSON.parse(fs.readFileSync(SIDECAR_FILE, "utf8"));
    if (!data || typeof data.files !== "object" || data.files === null) {
      throw new Error("'files' must be an object");
    }
    return { version: 1, files: data.files as Record<string, SidecarEntry> };
  } catch {
    return { version: 1, files: {} };
  }
};

/**
 * -> (published, modified), stable across rebuilds.
 *
 * The file name wins when it carries a date; otherwise the day the PDF was
 * first published is read back from the sidecar. Today's date is stamped once,
 * never on every run.
 */
const stampDates = (drop: Drop, files: Record<string, SidecarEntry>): Drop => {
  const stored = files[drop.path];
  const digest = sha256(path.join(ROOT, drop.path));
  const published = drop.published || (stored && stored.published) || today();
  let modified: string;
  if (stored && stored.hash === digest) {
    modified = stored.updated || published;
  } else if (stored) {
    modified = today(); // the file was replaced since it was first seen
  } else {
    modified = published;
  }
  return { ...drop, published, modified };
};

/** The sidecar this scan would write: existing files keep their stamp. */
const stampSidecar = (drops: Drop[], old: Sidecar): Sidecar => {
  const files: Record<string, SidecarEntry> = {};
  for (const drop of drops) {
    files[drop.path] = {
      hash: sha256(path.join(ROOT, drop.path)),
      published: drop.published,
      updated: drop.modified,
    };
  }
  for (const rel of Object.keys(old.files).sort()) {
    if (rel in files) continue;
    // a file this run did not describe still exists -> its stamp survives
    if (fs.existsSync(path.join(ROOT, rel))) files[rel] = old.files[rel];
  }
  const sorted: Record<string, SidecarEntry> = {};
  for (const rel of Object.keys(files).sort()) sorted[rel] = files[rel];
  return { version: 1, files: sorted };
};

const json = (value: unknown): string => JSON.stringify(value, null, 2) + "\n";

/** Same answer whatever order the keys landed in - for the round-trip check. */
const ordered = (drop: Drop): Drop => {
  const out = {} as Drop;
  for (const key of DROP_KEYS) out[key] = drop[key];
  return out;
};

// ---------------------------------------------------------------------------
// data/content-manifest.json - merge, never truncate
// ---------------------------------------------------------------------------

const readManifest = (): Manifest => {
  try {
    const data = JSON.parse(fs.readFileSync(MANIFEST_FILE, "utf8"));
    return data && typeof data === "object" ? (data as Manifest) : {};
  } catch {
    return {};
  }
};

const domainOf = (): string => {
  try {
    const site = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "site.json"), "utf8"));
    if (site && typeof site.url === "string") return site.url;
  } catch {
    /* fall through to the domain every other builder hardcodes */
  }
  return "https://houseofaspirants.in";
};

/** The inventory, freshly derived - reading files, writing nothing. */
const inventory = (): { drops: Drop[]; sidecar: Sidecar } => {
  const old = readSidecar();
  const drops = scan().map((d) => stampDates(d, old.files));
  return { drops, sidecar: stampSidecar(drops, old) };
};

const fail = (message: string): never => {
  process.stderr.write(`\n\u274c ${message}\n`);
  process.exit(1);
};

const write = (): number => {
  const { drops, sidecar } = inventory();
  const manifest = readManifest();
  if (typeof manifest.version !== "number") manifest.version = 3;
  if (typeof manifest.domain !== "string") manifest.domain = domainOf();
  manifest.drops = drops;
  fs.writeFileSync(MANIFEST_FILE, json(manifest), "utf8");
  fs.writeFileSync(SIDECAR_FILE, json(sidecar), "utf8");
  process.stdout.write(
    `  \u2139 pdf drops: ${drops.length} file(s) described -> data/content-manifest.json\n`
  );
  return 0;
};

/** Round-trip proof: the committed manifest is exactly what is on disk. */
const check = (): void => {
  const manifest = readManifest();
  if (!Array.isArray(manifest.drops)) {
    fail(
      "data/content-manifest.json has no `drops` inventory - run " +
        `node ${SCANNER} before the build`
    );
  }
  const { drops, sidecar } = inventory();
  const committed = (manifest.drops as Drop[]).map(ordered);
  const fresh = drops.map(ordered);
  const problems: string[] = [];
  const have = new Map(committed.map((d) => [d.path, d]));
  const want = new Map(fresh.map((d) => [d.path, d]));
  for (const rel of want.keys()) {
    if (!have.has(rel)) problems.push(`  + ${rel} (new on disk, not in the manifest)`);
  }
  for (const [rel, d] of have) {
    const now = want.get(rel);
    if (!now) {
      problems.push(`  - ${rel} (gone from disk, still in the manifest)`);
    } else if (JSON.stringify(d) !== JSON.stringify(now)) {
      problems.push(`  ~ ${rel} (metadata drifted)`);
    }
  }
  if (problems.length) {
    process.stderr.write("\n\u274c content manifest is stale:\n");
    for (const p of problems) process.stderr.write(`${p}\n`);
    process.stderr.write(`\n      run: node ${SCANNER}\n`);
    process.exit(1);
  }
  const expected = json(sidecar);
  const onDisk = fs.existsSync(SIDECAR_FILE) ? fs.readFileSync(SIDECAR_FILE, "utf8") : "";
  if (onDisk !== expected && !(onDisk === "" && Object.keys(sidecar.files).length === 0)) {
    fail(`data/pdf-meta.json does not match the scan - run: node ${SCANNER}`);
  }
  process.stdout.write(`  \u2714 content manifest OK (${drops.length} drop(s), sidecar in sync)\n`);
};

// ---------------------------------------------------------------------------
// CLI
// ---------------------------------------------------------------------------

const derive = (stems: string[]): void => {
  const rows: Derive[] = stems.map((stem) => ({
    stem,
    title: pdfTitleFromName(stem),
    slug: pdfSlugFromName(stem),
    date: pdfDateFromName(stem),
  }));
  process.stdout.write(json(rows));
};

const main = (): number => {
  const args = process.argv.slice(2);
  if (args[0] === "--check") {
    check();
    return 0;
  }
  if (args[0] === "--derive") {
    derive(args.slice(1));
    return 0;
  }
  if (args.length) {
    fail(`unknown argument ${args[0]} - usage: node ${SCANNER} [--check|--derive ...]`);
  }
  return write();
};

process.exit(main());
