#!/usr/bin/env node
/* ============================================================================
 * build_cf.mjs | Prepare the site for Cloudflare Workers (static assets)
 * ----------------------------------------------------------------------------
 *   node scripts/build_cf.mjs        then   npx wrangler deploy
 *
 * The site is prebuilt static HTML (the builders' committed output), so this
 * script only *selects* and *describes* it - it never rebuilds a page:
 *
 *   dist/                         every tracked public file (git ls-files),
 *                                 minus PDFs (served from R2 at
 *                                 files.houseofaspirants.in), sources, scripts
 *                                 and docs
 *   dist/_headers                 vercel.json "headers"  -> Cloudflare format
 *   cloudflare/redirects.json     vercel.json "redirects" -> read by
 *                                 cloudflare/worker.js
 *   wrangler.json                 Worker config; run_worker_first lists the
 *                                 paths that must reach the Worker even though
 *                                 a file exists there (redirect sources that
 *                                 shadow a file, and /study for middleware.js)
 *
 * vercel.json stays the one place redirects and headers are written; this
 * file translates it on every deploy. Clean URLs (page.html -> /page) and the
 * no-trailing-slash rule are Cloudflare's html_handling "drop-trailing-slash".
 * ========================================================================== */
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DIST = path.join(ROOT, "dist");
const vercel = JSON.parse(fs.readFileSync(path.join(ROOT, "vercel.json"), "utf8"));

/* ------------------------------------------------------------ files ----- */
const EXCLUDE_DIRS = [".github/", ".claude/", "scripts/", "templates/", "config/",
  "content/", "cloudflare/", "node_modules/", "dist/", ".wrangler/"];
const EXCLUDE_FILES = new Set(["vercel.json", "wrangler.json", "package.json",
  "package-lock.json", "jsconfig.json", "firestore.rules", "middleware.js",
  "publish.sh", "r2-cors.json", ".r2.env", ".r2.env.example", ".vercelignore",
  ".gitignore", "_headers", "_redirects"]);
const keep = (f) =>
  !EXCLUDE_DIRS.some((d) => f.startsWith(d)) &&
  !EXCLUDE_FILES.has(f) &&
  !(/^[^/]+\.md$/i.test(f)) &&          // root docs (README, reports)
  !/\.pdf$/i.test(f) &&                 // PDFs live on R2
  !/(^|\/)\.DS_Store$/.test(f) &&
  !/\.(py|ts|sh)$/.test(f);

const tracked = execFileSync("git", ["ls-files", "-z"], { cwd: ROOT })
  .toString("utf8").split("\0").filter(Boolean);

fs.rmSync(DIST, { recursive: true, force: true });
let copied = 0, bytes = 0;
for (const f of tracked) {
  if (!keep(f)) continue;
  const src = path.join(ROOT, f);
  if (!fs.existsSync(src) || !fs.statSync(src).isFile()) continue;
  const size = fs.statSync(src).size;
  if (size > 25 * 1024 * 1024) { console.warn(`  skip (over 25 MB): ${f}`); continue; }
  const dst = path.join(DIST, f);
  fs.mkdirSync(path.dirname(dst), { recursive: true });
  fs.copyFileSync(src, dst);
  copied++; bytes += size;
}

/* ------------------------------------------------------------ headers --- */
/** Vercel source pattern -> Cloudflare _headers paths. Handles the forms
    vercel.json uses: literal paths, "(.*)" and "(a|b|c)" alternations. */
function headerPaths(src) {
  const alt = src.match(/^(.*)\(([^()]*\|[^()]*)\)(.*)$/);
  if (alt) return alt[2].split("|").flatMap((a) => headerPaths(alt[1] + a + alt[3]));
  return [src.replace(/\(\.\*\)/g, "*").replace(/:[A-Za-z_]+\*/g, "*")];
}
const headerLines = [];
for (const rule of vercel.headers || []) {
  for (const p of headerPaths(rule.source)) {
    const ps = [p];
    // A clean-URL page rule (/about) must also cover its file (/about.html)
    if (!p.includes("*") && !p.includes(".") && p !== "/") ps.push(p + ".html");
    for (const q of ps) {
      headerLines.push(q);
      for (const h of rule.headers) headerLines.push(`  ${h.key}: ${h.value}`);
    }
  }
}
fs.writeFileSync(path.join(DIST, "_headers"), headerLines.join("\n") + "\n");

/* ------------------------------------------------------------ redirects - */
const norm = (p) => {
  let s = p;
  try { s = decodeURIComponent(p); } catch { /* keep as is */ }
  s = s.normalize("NFC").replace(/\.html$/, "");
  return s.length > 1 ? s.replace(/\/+$/, "") : s;
};
const literal = {};
const patterns = [];
for (const r of vercel.redirects || []) {
  const status = r.statusCode || (r.permanent === false ? 307 : 308);
  if (/[:(*]/.test(r.source)) {
    // "/content/:path(.*\\.(?:pdf|PDF))"  ->  ^/content/(?<path>.*\.(?:pdf|PDF))$
    let re = "", src = r.source, m;
    const tok = /:([A-Za-z_][A-Za-z0-9_]*)(\((?:[^()]|\([^()]*\))*\))?(\*)?|\(\.\*\)/y;
    for (let i = 0; i < src.length;) {
      tok.lastIndex = i;
      if ((m = tok.exec(src))) {
        if (m[0] === "(.*)") re += "(.*)";
        else re += `(?<${m[1]}>${m[2] ? m[2].slice(1, -1) : m[3] ? ".*" : "[^/]+"})`;
        i = tok.lastIndex;
      } else { re += src[i].replace(/[.+?^${}|[\]\\]/g, "\\$&"); i++; }
    }
    patterns.push({ re: `^${re}$`, to: r.destination, status });
  } else {
    literal[norm(r.source)] = [r.destination, status];
  }
}
fs.mkdirSync(path.join(ROOT, "cloudflare"), { recursive: true });
fs.writeFileSync(path.join(ROOT, "cloudflare", "redirects.json"),
  JSON.stringify({ literal, patterns }, null, 1) + "\n");

/* ------------------------------------------------------------ wrangler -- */
// Redirect sources that are also a real page: the Worker must see those first
// (Vercel applies redirects before the filesystem).
const assetPaths = new Set();
for (const f of tracked) {
  if (!keep(f)) continue;
  const p = "/" + f;
  assetPaths.add(norm(p));
  if (p.endsWith("/index.html")) assetPaths.add(norm(p.slice(0, -"/index.html".length) || "/"));
}
const shadowing = Object.keys(literal).filter((p) => assetPaths.has(p));
const firstPaths = ["/study", "/study.html"];
for (const p of shadowing) firstPaths.push(p, p + ".html");

const wrangler = {
  $schema: "node_modules/wrangler/config-schema.json",
  name: "houseofaspirants",
  main: "cloudflare/worker.js",
  compatibility_date: "2025-09-01",
  workers_dev: true,
  preview_urls: false,
  assets: {
    directory: "./dist",
    binding: "ASSETS",
    html_handling: "drop-trailing-slash",
    run_worker_first: [...new Set(firstPaths)].map((p) => encodeURI(p)),
  },
  routes: [{ pattern: "houseofaspirants.in", custom_domain: true }],
  observability: { enabled: false },
};
fs.writeFileSync(path.join(ROOT, "wrangler.json"), JSON.stringify(wrangler, null, 2) + "\n");

console.log(`build_cf: ${copied} files (${(bytes / 1048576).toFixed(1)} MB) -> dist/; ` +
  `${Object.keys(literal).length} redirects + ${patterns.length} patterns; ` +
  `${shadowing.length} redirect(s) shadow a page; ${headerLines.filter((l) => !l.startsWith(" ")).length} header paths`);
