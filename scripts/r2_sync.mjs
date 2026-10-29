#!/usr/bin/env node
/* ============================================================================
 * r2_sync.mjs | Copy the site's PDFs to Cloudflare R2 (files.houseofaspirants.in)
 * ----------------------------------------------------------------------------
 *   node scripts/r2_sync.mjs            upload every new or changed PDF
 *   node scripts/r2_sync.mjs --dry-run  list what would be uploaded
 *   node scripts/r2_sync.mjs --check    exit 1 if any PDF is missing on R2
 *
 * Which files: every *.pdf under content/ and assets/pdfs/, stored on R2 under
 * the SAME path (content/…/x.pdf -> https://files.houseofaspirants.in/content/…/x.pdf),
 * so data/site.json -> files.pdfBase only has to name the host.
 *
 * Nothing is ever deleted on R2: a removed or renamed PDF keeps answering
 * old WhatsApp / Google links. "Changed" = size or MD5 differs from R2's ETag.
 *
 * Credentials (never committed - .r2.env is in .gitignore), from the
 * environment or a .r2.env file at the repo root:
 *   R2_ACCOUNT_ID=…          Cloudflare dashboard → R2 → Account ID
 *   R2_ACCESS_KEY_ID=…       R2 → Manage API tokens → Object Read & Write
 *   R2_SECRET_ACCESS_KEY=…
 *   R2_BUCKET=hoa-files
 *
 * No dependencies: plain Node (>= 18) fetch + crypto, AWS Signature V4.
 * ========================================================================== */
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ROOTS = ["content", "assets/pdfs"];
const CACHE = "public, max-age=604800"; // a week in browsers / Cloudflare's cache
const PARALLEL = 2;

/* ------------------------------------------------------------ SigV4 ----- */
const sha256 = (data) => crypto.createHash("sha256").update(data).digest("hex");
const hmac = (key, data) => crypto.createHmac("sha256", key).update(data).digest();
/** RFC 3986 encoding of one path segment, as S3 expects it. */
const enc = (s) => encodeURIComponent(s).replace(/[!'()*]/g, (c) => "%" + c.charCodeAt(0).toString(16).toUpperCase());
export const encodeKey = (key) => key.split("/").map(enc).join("/");

/**
 * Signs a request; returns the headers to send (Authorization included).
 * @param {{method:string, host:string, uri:string, query?:Record<string,string>,
 *          headers?:Record<string,string>, payloadHash:string, accessKey:string,
 *          secretKey:string, region:string, service?:string, date?:Date}} r
 */
export function sign(r) {
  const service = r.service || "s3";
  const amzDate = (r.date || new Date()).toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const day = amzDate.slice(0, 8);
  const headers = { ...(r.headers || {}), host: r.host, "x-amz-content-sha256": r.payloadHash, "x-amz-date": amzDate };
  const lower = Object.fromEntries(Object.entries(headers).map(([k, v]) => [k.toLowerCase(), String(v).trim()]));
  const names = Object.keys(lower).sort();
  const query = Object.entries(r.query || {})
    .map(([k, v]) => [enc(k), enc(v)]).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([k, v]) => `${k}=${v}`).join("&");
  const canonical = [r.method, r.uri, query, names.map((n) => `${n}:${lower[n]}\n`).join(""),
    names.join(";"), r.payloadHash].join("\n");
  const scope = `${day}/${r.region}/${service}/aws4_request`;
  const toSign = ["AWS4-HMAC-SHA256", amzDate, scope, sha256(canonical)].join("\n");
  let key = hmac("AWS4" + r.secretKey, day);
  for (const part of [r.region, service, "aws4_request"]) key = hmac(key, part);
  const signature = crypto.createHmac("sha256", key).update(toSign).digest("hex");
  return {
    ...headers,
    Authorization: `AWS4-HMAC-SHA256 Credential=${r.accessKey}/${scope}, SignedHeaders=${names.join(";")}, Signature=${signature}`,
  };
}

/* ------------------------------------------------------------ config ---- */
function loadEnv() {
  const file = path.join(ROOT, ".r2.env");
  if (fs.existsSync(file)) {
    for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
      const m = line.match(/^\s*([A-Z0-9_]+)\s*=\s*"?([^"#]*?)"?\s*(?:#.*)?$/);
      if (m && !process.env[m[1]]) process.env[m[1]] = m[2];
    }
  }
  const need = ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"];
  const missing = need.filter((k) => !process.env[k]);
  if (missing.length) {
    console.error(`r2_sync: missing ${missing.join(", ")} - put them in .r2.env (see the header of this file)`);
    process.exit(2);
  }
  return {
    host: `${process.env.R2_ACCOUNT_ID}.r2.cloudflarestorage.com`,
    bucket: process.env.R2_BUCKET,
    accessKey: process.env.R2_ACCESS_KEY_ID,
    secretKey: process.env.R2_SECRET_ACCESS_KEY,
  };
}

async function call(cfg, { method, key = "", query, headers, body }) {
  const payloadHash = body ? sha256(body) : sha256("");
  const uri = `/${cfg.bucket}${key ? "/" + encodeKey(key) : ""}`;
  const signed = sign({ method, host: cfg.host, uri, query, headers, payloadHash,
    accessKey: cfg.accessKey, secretKey: cfg.secretKey, region: "auto" });
  delete signed.host; // fetch sets it
  const qs = query ? "?" + Object.entries(query).map(([k, v]) => `${enc(k)}=${enc(v)}`).join("&") : "";
  for (let attempt = 1; ; attempt++) {
    let res;
    try {
      res = await fetch(`https://${cfg.host}${uri}${qs}`, { method, headers: signed, body });
    } catch (e) { // network blip (reset / proxy timeout): retry, then give up
      if (attempt >= 5) throw new Error(`${method} ${key || "list"}: ${(e.cause && e.cause.code) || e.message}`);
      await new Promise((r) => setTimeout(r, 2000 * attempt));
      continue;
    }
    if (res.ok || attempt >= 5 || res.status < 500) return res;
    await new Promise((r) => setTimeout(r, 2000 * attempt));
  }
}

/* ------------------------------------------------------------ files ----- */
function localPdfs() {
  const out = [];
  const walk = (dir) => {
    if (!fs.existsSync(dir)) return;
    for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
      const p = path.join(dir, e.name);
      if (e.isDirectory()) walk(p);
      else if (e.isFile() && /\.pdf$/i.test(e.name)) {
        out.push({ key: path.relative(ROOT, p).split(path.sep).join("/"), file: p, size: fs.statSync(p).size });
      }
    }
  };
  ROOTS.forEach((r) => walk(path.join(ROOT, r)));
  return out.sort((a, b) => a.key.localeCompare(b.key));
}

const unxml = (s) => s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"')
  .replace(/&apos;/g, "'").replace(/&#(\d+);/g, (_, n) => String.fromCodePoint(+n)).replace(/&amp;/g, "&");

async function remoteObjects(cfg) {
  const map = new Map();
  for (const prefix of ROOTS) {
    let token = "";
    do {
      const query = { "list-type": "2", prefix: prefix + "/", "max-keys": "1000" };
      if (token) query["continuation-token"] = token;
      const res = await call(cfg, { method: "GET", query });
      const xml = await res.text();
      if (!res.ok) throw new Error(`list ${prefix}: HTTP ${res.status} ${xml.slice(0, 300)}`);
      for (const c of xml.match(/<Contents>[\s\S]*?<\/Contents>/g) || []) {
        const key = unxml((c.match(/<Key>([\s\S]*?)<\/Key>/) || [])[1] || "");
        const etag = unxml((c.match(/<ETag>([\s\S]*?)<\/ETag>/) || [])[1] || "").replace(/"/g, "");
        const size = Number((c.match(/<Size>(\d+)<\/Size>/) || [])[1] || -1);
        map.set(key, { etag, size });
      }
      token = /<IsTruncated>true<\/IsTruncated>/.test(xml)
        ? unxml((xml.match(/<NextContinuationToken>([\s\S]*?)<\/NextContinuationToken>/) || [])[1] || "") : "";
    } while (token);
  }
  return map;
}

/* ------------------------------------------------------------ main ------ */
async function main() {
  const args = new Set(process.argv.slice(2));
  const dry = args.has("--dry-run"), check = args.has("--check");
  const cfg = loadEnv();
  const local = localPdfs();
  const remote = await remoteObjects(cfg);

  const todo = [];
  for (const f of local) {
    const r = remote.get(f.key);
    if (!r) { todo.push({ ...f, why: "new" }); continue; }
    if (r.size !== f.size) { todo.push({ ...f, why: "changed" }); continue; }
    if (check) continue; // --check: same size on R2 is enough
    const md5 = crypto.createHash("md5").update(fs.readFileSync(f.file)).digest("hex");
    if (r.etag && !r.etag.includes("-") && r.etag !== md5) todo.push({ ...f, why: "changed" });
  }
  const mb = (n) => (n / 1048576).toFixed(1) + " MB";
  const total = todo.reduce((s, f) => s + f.size, 0);
  console.log(`r2_sync: ${local.length} PDF(s) here, ${remote.size} on R2 (bucket ${cfg.bucket}); ` +
    `${todo.length} to upload (${mb(total)})`);

  if (check) {
    todo.forEach((f) => console.log(`  ✗ ${f.why}: ${f.key}`));
    if (todo.length) { console.error("r2_sync --check: R2 is not up to date - run node scripts/r2_sync.mjs"); process.exit(1); }
    console.log("r2_sync --check: every PDF is on R2 ✓");
    return;
  }
  if (dry) { todo.forEach((f) => console.log(`  · ${f.why}: ${f.key} (${mb(f.size)})`)); return; }

  let done = 0, failed = 0;
  const queue = [...todo];
  await Promise.all(Array.from({ length: PARALLEL }, async () => {
    for (let f; (f = queue.shift());) {
      const body = fs.readFileSync(f.file);
      const res = await call(cfg, { method: "PUT", key: f.key, body, headers: {
        "content-type": "application/pdf", "cache-control": CACHE } });
      if (res.ok) console.log(`  ✓ [${++done}/${todo.length}] ${f.key} (${mb(f.size)})`);
      else { failed++; console.error(`  ✗ ${f.key}: HTTP ${res.status} ${(await res.text()).slice(0, 200)}`); }
    }
  }));
  console.log(`r2_sync: uploaded ${done}, failed ${failed}`);
  if (failed) process.exit(1);
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main().catch((e) => { console.error("r2_sync:", e.message || e); process.exit(1); });
}
