// cloudflare/worker.js | houseofaspirants.in on Cloudflare Workers (static assets)
//
// Static files are served by Cloudflare directly (free, no Worker run). This
// Worker only runs for what the files cannot answer on their own:
//   1. /study?subject=... - the old study.html links (middleware.js, generated)
//   2. vercel.json redirects (cloudflare/redirects.json, from build_cf.mjs),
//      including every old /content/*.pdf link -> files.houseofaspirants.in
//   3. anything else that is not a file -> 404.html with status 404
import studyRedirect from "../middleware.js";
import REDIRECTS from "./redirects.json";

const PATTERNS = REDIRECTS.patterns.map((p) => ({ ...p, rx: new RegExp(p.re) }));

function norm(pathname) {
  let s = pathname;
  try { s = decodeURIComponent(pathname); } catch { /* keep raw */ }
  s = s.normalize("NFC").replace(/\.html$/, "");
  return s.length > 1 ? s.replace(/\/+$/, "") : s;
}

function redirect(url) {
  const hit = REDIRECTS.literal[norm(url.pathname)];
  let to = null, status = 308;
  if (hit) {
    [to, status] = hit;
  } else {
    for (const p of PATTERNS) {
      const m = p.rx.exec(url.pathname);
      if (m) {
        to = p.to.replace(/:([A-Za-z_][A-Za-z0-9_]*)/g, (all, k) =>
          m.groups && k in m.groups ? m.groups[k] : all);
        status = p.status;
        break;
      }
    }
  }
  if (!to) return null;
  const dest = new URL(to, url.origin);
  if (!dest.search && url.search) dest.search = url.search; // Vercel carries the query
  return new Response(null, { status, headers: { Location: dest.toString() } });
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/study" || url.pathname === "/study.html") {
      const r = studyRedirect(request);
      if (r) return r;
    }

    const r = redirect(url);
    if (r) return r;

    const res = await env.ASSETS.fetch(request);
    if (res.status !== 404) return res;

    const page = await env.ASSETS.fetch(new Request(new URL("/404", url.origin)));
    return new Response(page.body, {
      status: 404,
      headers: { "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-cache" },
    });
  },
};
