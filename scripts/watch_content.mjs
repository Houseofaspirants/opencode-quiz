#!/usr/bin/env node
/**
 * watch_content.mjs — hands-free publishing.
 *
 * Watches content/ and questions/ recursively and, whenever a source is added, changed or
 * removed, runs `npm run publish` (build → gates → commit), then commits
 * anything left uncommitted as "content: auto publish" and pushes main.
 *
 *   node scripts/watch_content.mjs            # live
 *   node scripts/watch_content.mjs --dry-run  # detect and log, publish nothing
 *
 * Design notes:
 *
 *   - fs.watch reports the *signal*; a stat snapshot of the source trees
 *     is the *truth*. Copying one file on macOS emits create + write
 *     + rename events, and comparing snapshots is what collapses them into a
 *     single "something changed" — duplicate events never start a second
 *     publish. PDFs, Markdown and JSON metadata/questions are tracked.
 *
 *   - the debounce restarts on every event, so a folder of PDFs copied in at
 *     once publishes exactly once, 3 seconds after the last byte lands.
 *
 *   - one publish at a time. A change that arrives mid-build is queued and
 *     published by the next cycle rather than racing it, so two builds can
 *     never contend for the same git index.
 */

import {
  watch,
  readdirSync,
  statSync,
  readFileSync,
  writeFileSync,
  unlinkSync,
  existsSync,
} from "node:fs";
import { spawn } from "node:child_process";
import { join, resolve, dirname, relative } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import process from "node:process";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const CONTENT = join(ROOT, "content");
const QUESTIONS = join(ROOT, "questions");
const SOURCE_ROOTS = [CONTENT, QUESTIONS];
const DEBOUNCE_MS = 3000;
const RETRY_MS = 60000;
const POLL_MS = 15000;
const DRY_RUN = process.argv.includes("--dry-run");
const LOCK = join(tmpdir(), "houseofaspirants-content-watch.lock");
// Manual publishing is the safe default when the setting is absent or invalid.
let AUTO_PUSH = false;
try {
  AUTO_PUSH = JSON.parse(readFileSync(join(ROOT, "config", "publishing.json"), "utf8")).autoPush === true;
} catch {
  // Building and committing still work; publishing stays in GitHub Desktop.
}

/**
 * launchd starts processes with a near-empty PATH, so the tools the pipeline
 * needs (npm, python3, git) have to be found by hand. Prepending node's own
 * directory puts npm next to it, which is where Homebrew installs both.
 */
process.env.PATH = [
  dirname(process.execPath),
  "/opt/homebrew/bin",
  "/usr/local/bin",
  process.env.PATH || "/usr/bin:/bin:/usr/sbin:/sbin",
  "/usr/bin:/bin:/usr/sbin:/sbin",
]
  .filter(Boolean)
  .join(":");

/**
 * A background job must never block on ssh asking a question. BatchMode turns
 * any prompt into an immediate failure instead of a hang, accept-new clears the
 * one-off host-key question, ConnectTimeout bounds a dead network, and
 * IdentitiesOnly pins the key we generated rather than whatever an agent holds.
 */
const SSH_KEY = process.env.HOME ? join(process.env.HOME, ".ssh", "id_ed25519") : "";
if (SSH_KEY && existsSync(SSH_KEY)) {
  process.env.GIT_SSH_COMMAND =
    `ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new` +
    ` -o ConnectTimeout=15 -o IdentitiesOnly=yes -i ${JSON.stringify(SSH_KEY)}`;
}

// ---------------------------------------------------------------- logging --

const say = (line) => console.log(line);
const detail = (line) => console.log(`    ${line}`);

// -------------------------------------------------------------- snapshot --

const isSource = (name) => /\.(pdf|md|json)$/i.test(name);

/** Map of repository-relative source path -> "mtime:size". */
function snapshot() {
  const seen = new Map();
  const walk = (dir) => {
    let entries;
    try {
      entries = readdirSync(dir, { withFileTypes: true });
    } catch {
      return; // folder removed mid-scan, or not readable — nothing to report
    }
    for (const entry of entries) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) {
        walk(full);
      } else if (entry.isFile() && isSource(entry.name)) {
        try {
          const st = statSync(full);
          seen.set(relative(ROOT, full), `${st.mtimeMs}:${st.size}`);
        } catch {
          // still being written, or already gone — the next event re-checks
        }
      }
    }
  };
  for (const dir of SOURCE_ROOTS) walk(dir);
  return seen;
}

function diff(before, after) {
  const changed = [];
  for (const [path, sig] of after) if (before.get(path) !== sig) changed.push(path);
  for (const path of before.keys()) if (!after.has(path)) changed.push(path);
  return changed.sort();
}

// ------------------------------------------------------------ subprocess --

/**
 * Resolves with the exit code instead of rejecting: a failed publish is a
 * normal, survivable outcome for a long-running watcher, not a crash.
 * `echo: false` captures output for controlled reporting (used for git push,
 * whose message is the only interesting part).
 */
function run(cmd, args, { echo = true } = {}) {
  return new Promise((resolveRun) => {
    const child = spawn(cmd, args, {
      cwd: ROOT,
      env: process.env,
      stdio: echo ? "inherit" : ["ignore", "pipe", "pipe"],
    });
    let out = "";
    if (!echo) {
      child.stdout?.on("data", (chunk) => (out += chunk));
      child.stderr?.on("data", (chunk) => (out += chunk));
    }
    child.on("error", (err) => resolveRun({ code: 127, ok: false, out: `${out}${err.message}` }));
    child.on("close", (code) => resolveRun({ code: code ?? 1, ok: code === 0, out }));
  });
}

const sleep = (ms) => new Promise((resolveSleep) => setTimeout(resolveSleep, ms));

// A single dropped connection must not leave a finished build unpublished, so
// the push retries with backoff. Authentication failures are never retried:
// they need a human (README §26), and retrying only delays the diagnosis.
const AUTH_FAILURE = /Permission denied|Host key verification failed|could not read Username/i;
const PUSH_BACKOFF_MS = [5000, 15000];

async function pushWithRetry() {
  let result;
  for (let attempt = 0; ; attempt += 1) {
    result = await run("git", ["push", "origin", "main"], { echo: false });
    if (result.ok || attempt >= PUSH_BACKOFF_MS.length || AUTH_FAILURE.test(result.out)) {
      return result;
    }
    const wait = PUSH_BACKOFF_MS[attempt];
    detail(`push did not go through — retrying in ${wait / 1000}s (attempt ${attempt + 2}/${PUSH_BACKOFF_MS.length + 1})`);
    await sleep(wait);
  }
}

// ----------------------------------------------------------- publish pass --

async function publishCycle() {
  if (batch.size === 0) return;
  running = true;
  const changed = [...batch];
  batch.clear();
  let failed = false;

  try {
    say("✓ Publishing...");
    if (DRY_RUN) {
      detail(`dry run — would publish ${changed.length} source change(s): ${changed.join(", ")}`);
      return;
    }

    // publish.sh builds, runs every gate and commits its own output.
    const build = await run("npm", ["run", "publish"]);
    if (!build.ok) {
      failed = true;
      say(`✗ Publish failed (exit ${build.code}) — nothing was committed, still watching`);
      return;
    }
    say("✓ Build successful");

    // Anything the build itself did not commit (edits made outside it) still
    // has to land before we push.
    await run("git", ["add", "-A"], { echo: false });
    const staged = await run("git", ["diff", "--cached", "--quiet"], { echo: false });
    if (staged.code === 1) {
      const commit = await run("git", ["commit", "-m", "content: auto publish"]);
      if (!commit.ok) {
        failed = true;
        say(`✗ Commit failed (exit ${commit.code}) — not pushing`);
        return;
      }
    } else if (staged.code > 1) {
      failed = true;
      detail(`could not read the index (exit ${staged.code}) — skipping the push`);
      return;
    }

    if (!AUTO_PUSH) {
      say("✓ Build committed locally — use Push origin in GitHub Desktop to update the website");
      return;
    }
    say("✓ Pushing...");
    const push = await pushWithRetry();
    const lines = push.out.trim().split("\n").filter(Boolean);
    if (push.ok) {
      for (const line of lines) detail(line.trim());
      say("✓ Website Live");
    } else {
      failed = true;
      say(`⚠ Push failed (exit ${push.code})`);
      for (const line of lines.slice(-4)) detail(line.trim());
      detail("→ commits are safe locally; push from GitHub Desktop, or add the");
      detail("  SSH key to GitHub (README §26) so the next push is automatic.");
    }
  } catch (err) {
    failed = true;
    say(`✗ Unexpected error: ${err && err.message ? err.message : String(err)}`);
  } finally {
    running = false;
    if (failed) {
      // Keep failed deletions queued. A later retry or source correction must
      // publish them even when fs.watch sends no further event for that file.
      for (const path of changed) batch.add(path);
    }
    if (rerunAfter || batch.size > 0) {
      rerunAfter = false;
      schedule(failed ? RETRY_MS : DEBOUNCE_MS);
    }
  }
}

// --------------------------------------------------------------- schedule --

let known = snapshot();
let batch = new Set();
let timer = null;
let running = false;
let rerunAfter = false;

function schedule(delay = DEBOUNCE_MS) {
  if (timer) clearTimeout(timer);
  timer = setTimeout(() => {
    timer = null;
    if (running) {
      rerunAfter = true; // publish this batch as soon as the current one lands
      return;
    }
    void publishCycle();
  }, delay);
}

function onFsEvent(_event, filename) {
  // Directory renames/removals may report only the folder name, even when
  // they remove many files. Always compare the inventory; unrelated edits
  // produce an empty diff and never trigger a publish.

  const next = snapshot();
  const changed = diff(known, next);
  known = next;
  if (changed.length === 0) return; // duplicate event or unrelated change

  if (batch.size === 0) say("✓ Source change detected");
  for (const path of changed) {
    if (batch.has(path)) continue; // already reported for this batch
    batch.add(path);
    detail(path);
  }
  schedule();
}

// ----------------------------------------------------------- single lock --

const pidAlive = (pid) => {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
};

function takeLock() {
  try {
    const pid = Number(readFileSync(LOCK, "utf8").trim());
    if (pid && pid !== process.pid && pidAlive(pid)) return false;
  } catch {
    // no lock yet
  }
  writeFileSync(LOCK, String(process.pid));
  return true;
}

const releaseLock = () => {
  try {
    if (readFileSync(LOCK, "utf8").trim() === String(process.pid)) unlinkSync(LOCK);
  } catch {
    // already gone
  }
};

// ------------------------------------------------------------------ start --

function fail(message) {
  say(message);
  // Exit 0: this is a configuration problem, not a crash. launchd's KeepAlive
  // is keyed on SuccessfulExit, so a clean exit stops it from restarting into
  // the same failure forever.
  process.exit(0);
}

if (!takeLock()) {
  fail("another content watcher is already running (see `bash scripts/watch_service.sh status`)");
}

say("────────────────────────────────────────");
say(" content watcher");
say(` root:      ${ROOT}`);
say(` watching:  content/ + questions/ (PDF, Markdown, JSON)`);
say(` debounce:  ${DEBOUNCE_MS / 1000}s after the last change`);
say(` mode:      ${DRY_RUN ? "dry run (publishing disabled)" : "live"}`);
say(` push:      ${AUTO_PUSH ? "automatic" : "manual — GitHub Desktop"}`);
say(" stop:      Ctrl+C  |  background: bash scripts/watch_service.sh install");
say("────────────────────────────────────────");

let watchers = [];
try {
  for (const dir of SOURCE_ROOTS) {
    const watcher = watch(dir, { recursive: true }, onFsEvent);
    watcher.on("error", (err) => {
      say(`✗ lost the source watcher: ${err.message}`);
      process.exit(1); // launchd restarts it
    });
    watchers.push(watcher);
  }
} catch (err) {
  releaseLock();
  fail(`✗ cannot watch ${CONTENT}: ${err.message}`);
}

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    try {
      for (const watcher of watchers) watcher.close();
    } catch {
      // already closed
    }
    releaseLock();
    say("watcher stopped");
    process.exit(0);
  });
}

process.on("uncaughtException", (err) => {
  say(`✗ uncaught: ${err && err.stack ? err.stack : err}`);
  releaseLock();
  process.exit(1); // launchd restarts it
});

// Reconcile deletions made while the service was stopped, then periodically
// compare the tree in case macOS coalesces or misses a directory event.
batch.add("startup source reconciliation");
schedule();
setInterval(() => onFsEvent("poll", null), POLL_MS);
