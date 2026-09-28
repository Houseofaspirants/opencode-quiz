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
 *     published, modified - plus what only the bytes can say: pages, summary,
 *     thumbnail, thumbW, thumbH;
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
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { inflateRawSync, inflateSync } from "node:zlib";
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
  pages: number;       // page count read out of the file (0 = the file proves none)
  summary: string;     // <=300 chars read out of the file ("" = nothing readable)
  thumbnail: string;   // "assets/img/pdf/<hash>.jpg" when the preview exists, else ""
  thumbW: number;      // preview width in px (0 without a preview)
  thumbH: number;      // preview height in px (0 without a preview)
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
  "pages", "summary", "thumbnail", "thumbW", "thumbH",
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
// file content: page count, opening text, first-page preview
//
// A file name says what a PDF is called; only its bytes say how many pages it
// has, what it opens with and what page one looks like. Everything here reads
// the file and writes nothing, so the answer is the same on any machine - and
// a PDF this parser cannot open (a scanned page with no text layer, a
// compressed object tree) leaves its field empty instead of guessing.
// ---------------------------------------------------------------------------

/** One char per byte - exactly what Python's latin-1 decode answers. */
const asLatin1 = (buf: Buffer): string => buf.toString("latin1");

/** How one font turns the bytes it draws into characters. */
type FontText = {
  table: Map<number, string> | null;   // the file's own /ToUnicode CMap
  wide: boolean;                       // codes are two bytes wide (CID font)
  enc: string;                         // TextDecoder label when there is no table
};

/** The dictionary of object `num`, never the stream bytes that may follow it. */
const objectDict = (txt: string, num: number): string => {
  const m = new RegExp(`(?:^|[^0-9])${num}\\s+0\\s+obj`).exec(txt);
  if (!m) return "";
  const start = m.index + m[0].length;
  const stop = txt.indexOf("endobj", start);
  return txt.slice(start, stop < 0 ? start + 16384 : Math.min(stop, start + 16384));
};

/** The indirect reference `/Key N 0 R` in a dictionary, or 0. */
const refIn = (txt: string, key: string): number => {
  const m = new RegExp(`/${key}\\s+(\\d+)\\s+\\d+\\s+R`).exec(txt);
  return m ? Number(m[1]) : 0;
};

/** The dictionary that follows `/Key`, read with balanced `<<` `>>`. */
const dictAfter = (txt: string, key: string): string => {
  const at = txt.indexOf(`/${key}`);
  const open = at < 0 ? -1 : txt.indexOf("<<", at);
  if (open < 0) return "";
  let depth = 0;
  for (let i = open; i + 1 < txt.length; i++) {
    if (txt[i] === "<" && txt[i + 1] === "<") { depth++; i++; continue; }
    if (txt[i] === ">" && txt[i + 1] === ">") {
      depth--; i++;
      if (!depth) return txt.slice(open + 2, i - 1);
    }
  }
  return "";
};

const inflateAny = (raw: Buffer): Buffer | null => {
  const trim = Buffer.from(raw.toString("latin1").replace(/[\r\n]+$/, ""), "latin1");
  for (const buf of raw.length === trim.length ? [raw] : [raw, trim]) {
    try { return inflateSync(buf); } catch { /* not the zlib-wrapped form */ }
    try { return inflateRawSync(buf); } catch { /* not deflate at all */ }
  }
  return null;
};

/** The FlateDecode stream of object `num`, or null when there is none. */
const streamOf = (txt: string, num: number): Buffer | null => {
  const m = new RegExp(`(?:^|[^0-9])${num}\\s+0\\s+obj`).exec(txt);
  if (!m) return null;
  const start = m.index + m[0].length;
  const dict = txt.slice(start, start + 16384);
  const sm = /stream\r?\n/.exec(dict);
  if (!sm) return null;
  const data = start + sm.index + sm[0].length;
  const lm = /\/Length\s+(\d+)(\s+\d+\s+R)?/.exec(dict.slice(0, sm.index));
  if (lm && !lm[2]) {
    const buf = inflateAny(Buffer.from(txt.slice(data, data + Number(lm[1])), "latin1"));
    if (buf) return buf;
  }
  const end = txt.indexOf("endstream", data);
  return end < 0 ? null : inflateAny(Buffer.from(txt.slice(data, end), "latin1"));
};

/** The page count the file declares: /Count on the page tree, else the number
 *  of page objects. A file that declares neither reads 0 - never a guess. */
const pageCountOf = (txt: string): number => {
  const roots = [...txt.matchAll(/\/Root\s+(\d+)\s+\d+\s+R/g)];
  if (roots.length) {
    const cat = objectDict(txt, Number(roots[roots.length - 1][1]));
    const tree = refIn(cat, "Pages");
    if (tree) {
      const m = /\/Count\s+(\d+)/.exec(objectDict(txt, tree));
      if (m && Number(m[1]) > 0) return Number(m[1]);
    }
  }
  return (txt.match(/\/Type\s*\/Page(?![sA-Za-z])/g) || []).length;
};

/** Object numbers of the first `want` pages, in document order. */
const pageObjects = (txt: string, want: number): number[] => {
  const roots = [...txt.matchAll(/\/Root\s+(\d+)\s+\d+\s+R/g)];
  if (!roots.length) return [];
  const tree = refIn(objectDict(txt, Number(roots[roots.length - 1][1])), "Pages");
  if (!tree) return [];
  const out: number[] = [];
  const walk = (num: number, depth: number): void => {
    if (out.length >= want || depth > 12) return;
    const obj = objectDict(txt, num);
    if (!obj) return;
    if (/\/Type\s*\/Page(?![sA-Za-z])/.test(obj)) { out.push(num); return; }
    const kids = /\/Kids\s*\[([^\]]*)\]/.exec(obj);
    if (!kids) return;
    for (const k of kids[1].matchAll(/(\d+)\s+\d+\s+R/g)) {
      walk(Number(k[1]), depth + 1);
      if (out.length >= want) return;
    }
  };
  walk(tree, 0);
  return out;
};

const hexBytes = (hex: string): number[] => {
  const s = hex.replace(/\s+/g, "");
  const body = s.length % 2 ? s + "0" : s;
  const out: number[] = [];
  for (let i = 0; i < body.length; i += 2) out.push(parseInt(body.slice(i, i + 2), 16));
  return out;
};

const utf16Be = (bytes: number[]): string => {
  let out = "";
  for (let i = 0; i + 1 < bytes.length; i += 2) out += String.fromCharCode((bytes[i] << 8) | bytes[i + 1]);
  return out;
};

/** A font's /ToUnicode CMap: the code -> character table the file ships, plus
 *  whether a code is two bytes wide (a CID font) or one (a simple font). */
const toUnicode = (txt: string, num: number): { table: Map<number, string>; wide: boolean } | null => {
  const raw = streamOf(txt, num);
  if (!raw) return null;
  const cmap = asLatin1(raw);
  const table = new Map<number, string>();
  for (const block of cmap.match(/beginbfchar[\s\S]*?endbfchar/g) || []) {
    for (const m of block.matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) {
      const value = utf16Be(hexBytes(m[2]));
      if (value) table.set(parseInt(m[1], 16), value);
    }
  }
  for (const block of cmap.match(/beginbfrange[\s\S]*?endbfrange/g) || []) {
    for (const m of block.matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>/g)) {
      const lo = parseInt(m[1], 16);
      const hi = parseInt(m[2], 16);
      const value = utf16Be(hexBytes(m[3]));
      if (!value || hi < lo || hi - lo > 65535) continue;
      const first = value.codePointAt(0) || 0;
      for (let i = 0; i <= hi - lo; i++) table.set(lo + i, String.fromCodePoint(first + i));
    }
    for (const m of block.matchAll(/<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*\[([\s\S]*?)\]/g)) {
      const lo = parseInt(m[1], 16);
      [...m[3].matchAll(/<([0-9A-Fa-f]+)>/g)].forEach((v, i) => {
        const value = utf16Be(hexBytes(v[1]));
        if (value) table.set(lo + i, value);
      });
    }
  }
  const span = /begincodespacerange\s*<([0-9A-Fa-f]+)>/.exec(cmap);
  return table.size ? { table, wide: span ? span[1].length >= 4 : false } : null;
};

// ---------------------------------------------------------------------------
// When the file does not know a glyph either
// ---------------------------------------------------------------------------

const u16At = (s: string, o: number): number => (s.charCodeAt(o) << 8) | s.charCodeAt(o + 1);
const u32At = (s: string, o: number): number => ((u16At(s, o) * 65536) + u16At(s, o + 2)) >>> 0;

/** The tables an sfnt font program declares: tag -> [offset, length]. */
const sfntTables = (sfnt: string): Map<string, [number, number]> => {
  const out = new Map<string, [number, number]>();
  if (sfnt.length < 12) return out;
  const count = u16At(sfnt, 4);
  if (count < 1 || count > 64 || 12 + 16 * count > sfnt.length) return out;
  for (let i = 0; i < count; i++) {
    const o = 12 + 16 * i;
    out.set(sfnt.slice(o, o + 4), [u32At(sfnt, o + 8), u32At(sfnt, o + 12)]);
  }
  return out;
};

/** code -> glyph index, as the font declares it (cmap formats 0/4/6/12). */
const sfntGlyphs = (sfnt: string, tables: Map<string, [number, number]>): Map<number, number> => {
  const out = new Map<number, number>();
  const cmap = tables.get("cmap");
  if (!cmap) return out;
  const subtables = u16At(sfnt, cmap[0] + 2);
  for (let i = 0; i < subtables && !out.size; i++) {
    const rec = cmap[0] + 4 + 8 * i;
    if (rec + 8 > sfnt.length) break;
    const sub = cmap[0] + u32At(sfnt, rec + 4);
    if (sub + 10 > sfnt.length) continue;
    const fmt = u16At(sfnt, sub);
    if (fmt === 0) {
      for (let c = 0; c < 256 && sub + 6 + c < sfnt.length; c++) out.set(c, sfnt.charCodeAt(sub + 6 + c));
    } else if (fmt === 6) {
      const first = u16At(sfnt, sub + 6), count = u16At(sfnt, sub + 8);
      for (let k = 0; k < count && sub + 11 + 2 * k < sfnt.length; k++) {
        out.set(first + k, u16At(sfnt, sub + 10 + 2 * k));
      }
    } else if (fmt === 4) {
      const seg2 = u16At(sfnt, sub + 6), seg = seg2 >> 1;
      const ends = sub + 14, starts = ends + seg2 + 2, deltas = starts + seg2, ros = deltas + seg2;
      for (let k = 0; k < seg && ros + 2 * k + 1 < sfnt.length; k++) {
        const from = u16At(sfnt, starts + 2 * k), to = u16At(sfnt, ends + 2 * k);
        const delta = u16At(sfnt, deltas + 2 * k), ro = u16At(sfnt, ros + 2 * k);
        for (let c = from; c <= to; c++) {
          let g: number;
          if (ro === 0) g = (c + delta) & 0xffff;
          else {
            const gi = ros + 2 * k + ro + 2 * (c - from);
            if (gi + 1 >= sfnt.length) continue;
            g = u16At(sfnt, gi);
            if (g) g = (g + delta) & 0xffff;
          }
          if (g) out.set(c, g);
        }
      }
    } else if (fmt === 12) {
      const groups = u32At(sfnt, sub + 12);
      for (let k = 0; k < groups; k++) {
        const o = sub + 16 + 12 * k;
        if (o + 12 > sfnt.length) break;
        const from = u32At(sfnt, o), to = u32At(sfnt, o + 4), g0 = u32At(sfnt, o + 8);
        for (let c = from; c <= to && c - from < 4096; c++) out.set(c, g0 + (c - from));
      }
    }
  }
  return out;
};

/** glyph index -> glyph name. A format-2 `post` is the only place a subset
 *  font still says what a glyph is called. */
const sfntNames = (sfnt: string, tables: Map<string, [number, number]>): Map<number, string> => {
  const out = new Map<number, string>();
  const post = tables.get("post");
  if (!post || u32At(sfnt, post[0]) !== 0x00020000) return out;
  const base = post[0], end = Math.min(base + post[1], sfnt.length);
  if (base + 34 > end) return out;
  const glyphs = u16At(sfnt, base + 32);
  const strings: string[] = [];
  let o = base + 34 + 2 * glyphs;
  while (o < end) {
    const size = sfnt.charCodeAt(o);
    if (o + 1 + size > end) break;
    strings.push(sfnt.slice(o + 1, o + 1 + size));
    o += 1 + size;
  }
  for (let g = 0; g < glyphs && base + 35 + 2 * g < end; g++) {
    const idx = u16At(sfnt, base + 34 + 2 * g);
    if (idx >= 258 && idx - 258 < strings.length) out.set(g, strings[idx - 258]);
  }
  return out;
};

/** The font program a font dictionary points at (a subset TrueType file). */
const fontProgram = (txt: string, fontDict: string): string => {
  const desc = refIn(fontDict, "FontDescriptor");
  const dict = desc ? objectDict(txt, desc) : fontDict;
  const ref = refIn(dict, "FontFile2");
  const buf = ref ? streamOf(txt, ref) : null;
  return buf ? asLatin1(buf) : "";
};

const isOwnAscii = (code: number, value: string): boolean =>
  value.length === 1 && value.charCodeAt(0) === code && code >= 0x20 && code < 0x7f;

/** Codes a producer maps to their own ASCII character - its way of saying "I
 *  do not know this glyph". In a font that writes real Unicode everywhere
 *  else that is a hole in the text layer (the Gurmukhi ligature for "ੋਂ"
 *  comes back as the equals sign), and the glyph's own name in the embedded
 *  font program is the last witness: "MatraOoBindi.gm" is that ligature.
 *  Names are learned from the codes the file does know, a compound name is
 *  read as its parts, and anything still unheard of is left alone. */
const repairUnknownGlyphs = (table: Map<number, string>, txt: string, fontObj: number): void => {
  const holes: number[] = [];
  for (const [code, value] of table) if (isOwnAscii(code, value)) holes.push(code);
  if (!holes.length) return;
  const sfnt = fontProgram(txt, objectDict(txt, fontObj));
  if (!sfnt) return;
  const tables = sfntTables(sfnt);
  const glyphs = sfntGlyphs(sfnt, tables);
  const names = sfntNames(sfnt, tables);
  if (!glyphs.size || !names.size) return;
  const known = new Map<string, string>();          // name stem -> character
  const stemOf = new Map<number, string>();
  for (const [code, value] of table) {
    const gid = glyphs.get(code);
    const name = gid === undefined ? undefined : names.get(gid);
    if (!name) continue;
    stemOf.set(code, name.split(".")[0]);
    if (!isOwnAscii(code, value)) known.set(name.split(".")[0], value);
  }
  for (const code of holes) {
    const stem = stemOf.get(code);
    if (!stem) continue;                            // no witness: keep the file's answer
    const direct = known.get(stem);
    if (direct !== undefined) { table.set(code, direct); continue; }
    for (let i = stem.length - 1; i > 1; i--) {     // a compound: "MatraOo" + "Bindi"
      const head = known.get(stem.slice(0, i));
      const tail = known.get(stem.slice(i));
      if (head === undefined || tail === undefined) continue;
      const conjunct = GURMUKHI_CONSONANT.test(head[0]) && GURMUKHI_CONSONANT.test(tail[0]);
      table.set(code, conjunct ? head + "\u0A4D" + tail : head + tail);
      break;
    }
  }
};

/** The built-in encoding named by a simple font, as a TextDecoder label. */
const ENCODINGS: Record<string, string> = {
  MacRomanEncoding: "macintosh",
  WinAnsiEncoding: "windows-1252",
  StandardEncoding: "latin1",
  PDFDocEncoding: "latin1",
};

const DECODERS = new Map<string, TextDecoder | null>();

/** Bytes -> text through the font's own encoding. */
const decodeBytes = (bytes: number[], font: FontText | null): string => {
  if (!bytes.length) return "";
  if (font && font.table) {
    const out: string[] = [];
    if (font.wide) {
      for (let i = 0; i + 1 < bytes.length; i += 2) out.push(font.table.get((bytes[i] << 8) | bytes[i + 1]) ?? "");
    } else {
      for (const b of bytes) out.push(font.table.get(b) ?? (b >= 32 && b < 127 ? String.fromCharCode(b) : ""));
    }
    return out.join("");
  }
  if (font && font.wide) return utf16Be(bytes);
  const label = font ? font.enc : "latin1";
  if (label === "latin1") return Buffer.from(bytes).toString("latin1");
  let decoder = DECODERS.get(label);
  if (decoder === undefined) {
    try { decoder = new TextDecoder(label); } catch { decoder = null; }
    DECODERS.set(label, decoder);
  }
  return decoder ? decoder.decode(Uint8Array.from(bytes)) : Buffer.from(bytes).toString("latin1");
};

/** A literal PDF string `( ... )` -> its bytes, escapes resolved. */
const unescapePdf = (s: string): number[] => {
  const simple: Record<string, number> = { n: 10, r: 13, t: 9, b: 8, f: 12, "(": 40, ")": 41, "\\": 92 };
  const out: number[] = [];
  let i = 0;
  while (i < s.length) {
    const ch = s[i];
    if (ch !== "\\") { out.push(s.charCodeAt(i) & 0xff); i++; continue; }
    const nx = s[i + 1];
    if (nx === undefined) break;
    if (nx === "\n" || nx === "\r") { i += nx === "\r" && s[i + 2] === "\n" ? 3 : 2; continue; }
    if (nx in simple) { out.push(simple[nx]); i += 2; continue; }
    if (nx >= "0" && nx <= "7") {
      let oct = "", j = i + 1;
      while (j < s.length && oct.length < 3 && s[j] >= "0" && s[j] <= "7") { oct += s[j]; j++; }
      out.push(parseInt(oct, 8) & 0xff); i = j; continue;
    }
    i += 2;                                  // a backslash before anything else
  }
  return out;
};

/** Every font one page can draw with, keyed by its resource name. */
const pageFonts = (txt: string, page: string): { byName: Map<string, number>; fonts: Map<number, FontText> } => {
  const resRef = refIn(page, "Resources");
  const res = resRef ? objectDict(txt, resRef) : page;
  const byName = new Map<string, number>();
  const fonts = new Map<number, FontText>();
  for (const m of dictAfter(res, "Font").matchAll(/\/([A-Za-z0-9]+)\s+(\d+)\s+\d+\s+R/g)) {
    byName.set(m[1], Number(m[2]));
  }
  for (const num of new Set(byName.values())) {
    const dict = objectDict(txt, num);
    const tu = refIn(dict, "ToUnicode");
    const mapped = tu ? toUnicode(txt, tu) : null;
    if (mapped) repairUnknownGlyphs(mapped.table, txt, num);
    const cid = /\/Encoding\s+\d+\s+\d+\s+R/.test(dict);   // a CID font draws 2-byte codes
    const name = /\/Encoding\s+\/([A-Za-z0-9+-]+)/.exec(dict);
    fonts.set(num, {
      table: mapped ? mapped.table : null,
      wide: mapped ? mapped.wide : cid,
      enc: (name && ENCODINGS[name[1]]) || "latin1",
    });
  }
  return { byName, fonts };
};

/** The text a page draws, in the order the file draws it. */
const pageText = (txt: string, pageObj: number): string => {
  const page = objectDict(txt, pageObj);
  if (!page) return "";
  const { byName, fonts } = pageFonts(txt, page);
  const refs: number[] = [];
  const one = refIn(page, "Contents");
  if (one) refs.push(one);
  else {
    const arr = /\/Contents\s*\[([^\]]*)\]/.exec(page);
    if (arr) for (const m of arr[1].matchAll(/(\d+)\s+\d+\s+R/g)) refs.push(Number(m[1]));
  }
  let stream = "";
  for (const r of refs) {
    const buf = streamOf(txt, r);
    if (buf) stream += asLatin1(buf);
  }
  if (!stream) return "";
  const parts: string[] = [];
  let font: FontText | null = null;
  // Where the next glyph lands: the graphics translation (cm) plus the text
  // matrix (Tm). A run that drops down the page opens a new line, so a space
  // is owed; runs that stay put are one sentence drawn in pieces - a ligature
  // is often its own run, and spacing those would spell "ef fi cient".
  let gx = 0, gy = 0, scaleX = 1, tx = 0, ty = 0, size = 12;
  let prevY: number | null = null;
  let last = "";
  const tokens =
    /(-?[\d.]+\s+){5}-?[\d.]+\s+(?:cm|Tm)|\/([A-Za-z0-9]+)\s+[\d.]+\s+Tf|\((?:\\.|[^\\()])*\)|<[0-9A-Fa-f\s]+>|\bTJ\b|\bTj\b|\bT\*|\bTD\b|\bTd\b|\bBT\b|\bET\b/g;
  const show = (text: string): void => {
    const y = gy + ty;
    if (prevY !== null) {
      const downThePage = Math.abs(y - prevY) > Math.max(1, size * 0.5);
      const atSentenceEdge = last !== "" && /[.,;:!?)\]]/.test(last);
      if (downThePage || atSentenceEdge) parts.push(" ");
    }
    parts.push(text);
    prevY = y;
    last = text.slice(-1);
  };
  for (const m of stream.matchAll(tokens)) {
    const tok = m[0];
    if (/cm$/.test(tok)) {
      const n = tok.match(/-?[\d.]+/g) || [];
      if (n.length >= 6) { gx = +n[4]; gy = +n[5]; scaleX = Math.abs(+n[0]) || 1; }
      continue;
    }
    if (/Tm$/.test(tok)) {
      const n = tok.match(/-?[\d.]+/g) || [];
      if (n.length >= 6) {
        size = Math.abs(+n[0]) * scaleX || size;
        tx = +n[4]; ty = +n[5];
      }
      continue;
    }
    if (tok[0] === "/") { font = fonts.get(byName.get(m[2]) ?? -1) ?? null; continue; }
    if (tok[0] === "(") { show(decodeBytes(unescapePdf(tok.slice(1, -1)), font)); continue; }
    if (tok[0] === "<") { show(decodeBytes(hexBytes(tok.slice(1, -1)), font)); continue; }
  }
  return parts.join("");
};

/** The ligatures a font draws as one glyph, spelled out the way prose reads. */
const LIGATURES: Record<string, string> = {
  "\uFB00": "ff", "\uFB01": "fi", "\uFB02": "fl", "\uFB03": "ffi",
  "\uFB04": "ffl", "\uFB05": "st", "\uFB06": "st",
};
/** The house welcome page every PDF is bound to open with - front matter.
 *  Every page carries the brand in its footer, so only the opening of a page
 *  can tell front matter from content. */
const HOUSE_PAGE = /house\s+of\s+aspirants/i;
const isFrontMatter = (s: string): boolean => HOUSE_PAGE.test(s.slice(0, 90));

/** Drawn text -> text a page can quote: control characters out, ligatures
 *  spelled out, the Gurmukhi pre-base matra put back where the script writes
 *  it (the file stores glyphs in visual order), whitespace collapsed. */
const cleanText = (raw: string): string => {
  let s = raw.replace(/[\u0000-\u0008\u000B\u000C\u000E-\u001F\u007F]/g, "");
  s = s.replace(/[\uFB00-\uFB06]/g, (c) => LIGATURES[c] || c);
  s = s.replace(/\u0A3F([\u0A15-\u0A39\u0A59-\u0A5E])/g, "$1\u0A3F");
  s = s.replace(/\s+/g, " ").trim();
  return s.replace(/^[^\p{L}\p{N}]+/u, "");
};

/** Readable means letters and words - not a code table decoded as noise. */
const isReadable = (s: string): boolean => {
  const chars = Array.from(s);
  if (chars.length < 40) return false;
  const good = chars.filter((c) => /[\p{L}\p{N}\p{P}\p{S}\s]/u.test(c)).length;
  return good / chars.length >= 0.7;
};

// ---------------------------------------------------------------------------
// first-page preview: assets/img/pdf/<hash>.<ext>
// ---------------------------------------------------------------------------

const PREVIEW_DIR = path.join(ROOT, "assets", "img", "pdf");
const PREVIEW_EDGE = 600;                     // px on the long edge of page one
const PREVIEW_NAME = /^[0-9a-f]{12}\.(jpg|png)$/;
let previewsMade = 0;

/** PNG IHDR / JPEG SOF - the two formats a preview can be written as. */
const imageSize = (buf: Buffer): { width: number; height: number } => {
  if (buf.length > 24 && buf.toString("latin1", 0, 8) === "\x89PNG\r\n\u001a\n") {
    return { width: buf.readUInt32BE(16), height: buf.readUInt32BE(20) };
  }
  let i = 2;
  while (i + 9 < buf.length) {
    if (buf[i] !== 0xff) { i++; continue; }
    const marker = buf[i + 1];
    if (marker === 0xd8 || marker === 0x01 || (marker >= 0xd0 && marker <= 0xd7)) { i += 2; continue; }
    if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
      return { width: buf.readUInt16BE(i + 7), height: buf.readUInt16BE(i + 5) };
    }
    const len = buf.readUInt16BE(i + 2);
    if (len < 2) return { width: 0, height: 0 };
    i += 2 + len;
  }
  return { width: 0, height: 0 };
};

/** Draw page one. Every tool here is optional - a machine without one simply
 *  has no preview to make, and reads the committed file instead. */
const rasterize = (src: string, png: string, jpg: string): string => {
  try {
    execFileSync("/usr/bin/sips",
      ["-s", "format", "jpeg", "-s", "formatOptions", "70",
       "-Z", String(PREVIEW_EDGE), src, "--out", jpg], { stdio: "ignore" });
    if (fs.existsSync(jpg)) return jpg;
  } catch { /* sips is not on this machine */ }
  try {
    execFileSync("/usr/bin/qlmanage",
      ["-t", "-s", String(PREVIEW_EDGE), "-o", PREVIEW_DIR, src], { stdio: "ignore" });
    const made = path.join(PREVIEW_DIR, path.basename(src) + ".png");
    if (fs.existsSync(made)) { fs.renameSync(made, png); return png; }
  } catch { /* Quick Look is not on this machine */ }
  return "";
};

/**
 * The preview of one PDF: read when the file already draws it (a preview is
 * generated once and committed, so a machine with no rasteriser reproduces the
 * same manifest instead of failing), drawn only when it does not exist yet.
 */
const ensurePreview = (file: string, digest: string, allowCreate: boolean):
  { path: string; width: number; height: number } => {
  const stem = digest.slice(0, 12);
  for (const ext of ["jpg", "png"]) {
    const full = path.join(PREVIEW_DIR, `${stem}.${ext}`);
    if (fs.existsSync(full)) {
      const size = imageSize(fs.readFileSync(full));
      if (size.width && size.height) {
        return { path: `assets/img/pdf/${stem}.${ext}`, width: size.width, height: size.height };
      }
    }
  }
  if (!allowCreate) return { path: "", width: 0, height: 0 };
  fs.mkdirSync(PREVIEW_DIR, { recursive: true });
  const made = rasterize(file, path.join(PREVIEW_DIR, `${stem}.png`),
                         path.join(PREVIEW_DIR, `${stem}.jpg`));
  if (!made) return { path: "", width: 0, height: 0 };
  const size = imageSize(fs.readFileSync(made));
  if (!size.width || !size.height) { fs.unlinkSync(made); return { path: "", width: 0, height: 0 } };
  previewsMade += 1;
  return { path: `assets/img/pdf/${path.basename(made)}`, width: size.width, height: size.height };
};

/**
 * What only the bytes know: page count, opening text, first-page preview.
 *
 * The summary is the first page that says something THIS file says alone - a
 * welcome page shipped in every PDF is front matter, not a summary of the
 * document, so the scan walks on to page two and three before it quotes
 * anything. When every opening page is front matter, the first one is quoted
 * anyway: it really is what the file opens with.
 */
const describeContent = (drops: Drop[], allowCreate: boolean): Drop[] => {
  type Opened = { pages: number; texts: string[]; file: string; digest: string };
  const opened: Opened[] = [];
  const count = new Map<string, number>();
  const key = (s: string): string => s.slice(0, 120).toLowerCase();

  for (const drop of drops) {
    const file = path.join(ROOT, drop.path);
    const digest = sha256(file);
    const txt = asLatin1(fs.readFileSync(file));
    const pages = pageCountOf(txt);
    const texts: string[] = [];
    for (const obj of pageObjects(txt, 3)) {
      const text = cleanText(pageText(txt, obj));
      if (text && isReadable(text)) texts.push(text);
    }
    for (const t of texts) count.set(key(t), (count.get(key(t)) || 0) + 1);
    opened.push({ pages, texts, file, digest });
  }

  return drops.map((drop, i) => {
    const { pages, texts, file, digest } = opened[i];
    const shared = (t: string): boolean => (count.get(key(t)) || 0) > 1;
    const pick = texts.find((t) => !isFrontMatter(t) && !shared(t))
      || texts.find((t) => !isFrontMatter(t))
      || texts[0]
      || "";
    const preview = ensurePreview(file, digest, allowCreate);
    return {
      ...drop,
      pages,
      summary: clip(pick, 300),
      thumbnail: preview.path,
      thumbW: preview.width,
      thumbH: preview.height,
    };
  });
};

/** A preview no drop points at anymore (its file changed) is dead weight. */
const sweepPreviews = (drops: Drop[]): void => {
  if (!fs.existsSync(PREVIEW_DIR)) return;
  const live = new Set(drops.map((d) => path.basename(d.thumbnail)).filter(Boolean));
  let gone = 0;
  for (const name of fs.readdirSync(PREVIEW_DIR)) {
    if (live.has(name) || !PREVIEW_NAME.test(name)) continue;
    fs.unlinkSync(path.join(PREVIEW_DIR, name));
    gone += 1;
  }
  if (gone) process.stdout.write(`  \u2139 pdf previews: ${gone} stale preview(s) removed\n`);
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
        pages: 0,
        summary: "",
        thumbnail: "",
        thumbW: 0,
        thumbH: 0,
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

/** The inventory, freshly derived - reading files, writing nothing (unless
 *  `allowCreate` draws the first-page previews that do not exist yet). */
const inventory = (allowCreate = false): { drops: Drop[]; sidecar: Sidecar } => {
  const old = readSidecar();
  const drops = describeContent(scan().map((d) => stampDates(d, old.files)), allowCreate);
  return { drops, sidecar: stampSidecar(drops, old) };
};

const fail = (message: string): never => {
  process.stderr.write(`\n\u274c ${message}\n`);
  process.exit(1);
};

const write = (): number => {
  const { drops, sidecar } = inventory(true);
  const manifest = readManifest();
  if (typeof manifest.version !== "number") manifest.version = 3;
  if (typeof manifest.domain !== "string") manifest.domain = domainOf();
  manifest.drops = drops;
  fs.writeFileSync(MANIFEST_FILE, json(manifest), "utf8");
  fs.writeFileSync(SIDECAR_FILE, json(sidecar), "utf8");
  sweepPreviews(drops);
  if (previewsMade) {
    process.stdout.write(
      `  \u2139 pdf previews: ${previewsMade} first-page preview(s) drawn -> assets/img/pdf/\n`
    );
  }
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
