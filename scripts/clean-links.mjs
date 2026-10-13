/* clean-links.mjs - rewrite internal links from "page.html" to the clean URL "page".
 *
 * Vercel serves the site with cleanUrls:true, so every "page.html" link answers
 * with a 308 redirect to "/page". Google Search Console then reports those .html
 * addresses as "Page with redirect" and spends crawl time on them. This pass
 * points every internal href straight at the clean address.
 *
 * Only plain hrefs to files that exist are touched; templated names (${...}),
 * external URLs and non-href strings are left alone.
 * Run on its own (`node scripts/clean-links.mjs`) or via build-index.mjs.
 */
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
// Google AdSense site code (publisher ID is public; it appears on every page that shows ads).
const ADSENSE = `<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-7889829175568995" crossorigin="anonymous"></script>`;
const SKIP = new Set(["node_modules", ".git", "content", "scripts", "templates", "data", "config", "Claude outputs"]);
const RE = /(\bhref=|data-subject-base=)(["'`])((?:\.\/|\/)?(?:[A-Za-z0-9_-]+\/)*)([A-Za-z0-9_.-]+)\.html(?=[?#"'`])/g;

function files(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    if (e.name.startsWith(".") || SKIP.has(e.name)) continue;
    const p = path.join(dir, e.name);
    if (e.isDirectory()) files(p, out);
    else if (e.name.endsWith(".html") || (e.name.endsWith(".js") && p.includes(`${path.sep}assets${path.sep}js${path.sep}`))) out.push(p);
  }
  return out;
}

export function cleanLinks({ quiet = false } = {}) {
  let changedFiles = 0, changedLinks = 0;
  for (const f of files(ROOT)) {
    const src = fs.readFileSync(f, "utf8");
    let out = src;
    // Every HTML page gets the AdSense code once, just before </head>.
    if (f.endsWith(".html") && !out.includes("adsbygoogle.js") && out.includes("</head>"))
      out = out.replace("</head>", `  ${ADSENSE}\n</head>`);
    out = out.replace(RE, (m, attr, q, prefix, name) => {
      // Resolve against the site root (Punjabi pages use <base href="/">).
      const target = path.join(ROOT, prefix.replace(/^\.?\//, ""), `${name}.html`);
      if (!fs.existsSync(target)) return m;
      changedLinks++;
      if (name === "index") return `${attr}${q}${prefix || "./"}`;
      return `${attr}${q}${prefix}${name}`;
    });
    if (out !== src) { fs.writeFileSync(f, out); changedFiles++; }
  }
  if (!quiet) console.log(`  clean-links: ${changedLinks} link(s) in ${changedFiles} file(s) -> clean URLs`);
  return { changedFiles, changedLinks };
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) cleanLinks();
