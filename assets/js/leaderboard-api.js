/* ============================================================================
 * leaderboard-api.js | Data layer for the live leaderboard (HOA.lbApi)
 * ----------------------------------------------------------------------------
 * Every row comes from Firestore `scores/{uid}` through HOA.auth — the one
 * place that talks to Firebase. There is NO demo or sample data: when the
 * database is not connected the page says so instead of inventing students.
 *
 *   board(period)  → { rows: Row[], fetchedAt }       top 50, highest first
 *   mine(period)   → { row, rank, ranked } | null     the signed-in student
 *   status()       → "live" | "offline" | "unconfigured"
 *
 *   period: "day" | "week" | "month" | "all"   (IST calendar — see auth.js)
 *
 * Reads are cached for 60 s per period (sessionStorage) so switching tabs and
 * reloading does not spend the free Firestore read quota.
 * ========================================================================== */
(() => {
  "use strict";

  const HOA = (window.HOA = window.HOA || {});
  const LIMIT = 50;
  const TTL = 60 * 1000;

  const num = (v) => (Number.isFinite(Number(v)) ? Number(v) : 0);

  function cacheGet(key) {
    try {
      const raw = sessionStorage.getItem(key);
      if (!raw) return null;
      const v = JSON.parse(raw);
      return Date.now() - v.at < TTL ? v : null;
    } catch (_) { return null; }
  }
  function cacheSet(key, value) {
    try { sessionStorage.setItem(key, JSON.stringify({ ...value, at: Date.now() })); } catch (_) {}
  }
  function cacheDrop() {
    try {
      Object.keys(sessionStorage).filter((k) => k.startsWith("lb2:")).forEach((k) => sessionStorage.removeItem(k));
    } catch (_) {}
  }

  async function ready() {
    if (!HOA.auth) return "unconfigured";
    await HOA.auth.ready;
    return HOA.auth.mode === "firebase" ? "live" : "unconfigured";
  }

  /** Normalised row for one student on one board. */
  function toRow(doc, period, me) {
    const per = doc.per || {};
    const p = period === "day" ? per.d : period === "week" ? per.w : period === "month" ? per.m : null;
    const key = HOA.auth.boardField(period);
    const fresh = p && (period === "all" || p.k === key);
    const answered = fresh ? num(p.answered) : num(doc.answered);
    const correct = fresh ? num(p.correct) : num(doc.correct);
    return {
      uid: doc.uid || doc.id,
      name: String(doc.name || "Aspirant"),
      photo: doc.photo || null,
      points: num(doc.score != null ? doc.score : doc[key]),
      quizzes: fresh ? num(p.quizzes) : num(doc.quizzes),
      accuracy: answered ? Math.round((correct / answered) * 100) : 0,
      streak: num(doc.streak),
      lastQuiz: doc.last && doc.last.quiz ? String(doc.last.quiz) : "",
      isMe: !!me && (doc.uid || doc.id) === me.uid,
    };
  }

  async function board(period, opts = {}) {
    const st = await ready();
    if (st !== "live") return { status: st, rows: [], fetchedAt: 0 };
    const ck = `lb2:${period}:${HOA.auth.boardField(period)}`;
    if (!opts.force) {
      const hit = cacheGet(ck);
      if (hit) return { status: "live", rows: markMe(hit.rows), fetchedAt: hit.at };
    }
    try {
      const raw = await HOA.auth.fetchBoard(period, LIMIT);
      const rows = raw.map((d) => toRow(d, period, null));
      cacheSet(ck, { rows });
      return { status: "live", rows: markMe(rows), fetchedAt: Date.now() };
    } catch (err) {
      console.warn("[HOA.lbApi] board failed:", err && err.message);
      return { status: "offline", rows: [], fetchedAt: 0, error: err };
    }
  }

  function markMe(rows) {
    const me = HOA.auth && HOA.auth.cloudEnabled() ? HOA.auth.user() : null;
    return rows.map((r) => ({ ...r, isMe: !!me && r.uid === me.uid }));
  }

  /** Signed-in student's standing on `period`, given the rows already shown. */
  async function mine(period, rows) {
    if (!HOA.auth || !HOA.auth.cloudEnabled()) return null;
    const me = HOA.auth.user();
    const idx = (rows || []).findIndex((r) => r.uid === me.uid);
    let doc = null;
    try { doc = await HOA.auth.fetchMine(); } catch (_) {}
    if (!doc) return { row: null, rank: null, ranked: null };
    const row = toRow(doc, period, me);
    const key = HOA.auth.boardField(period);
    row.points = num(doc[key]);
    if (!row.points) return { row, rank: null, ranked: null };
    if (idx >= 0) return { row, rank: idx + 1, ranked: null };
    const above = await HOA.auth.countAbove(period, row.points);
    return { row, rank: above == null ? null : above + 1, ranked: null, beyond: LIMIT };
  }

  /** How many students are on a board (null when the SDK cannot count). */
  async function ranked(period) {
    if ((await ready()) !== "live") return null;
    const ck = `lb2:n:${period}:${HOA.auth.boardField(period)}`;
    const hit = cacheGet(ck);
    if (hit) return hit.n;
    const n = await HOA.auth.countAbove(period, 0);
    if (n != null) cacheSet(ck, { n });
    return n;
  }

  HOA.lbApi = Object.freeze({ board, mine, ranked, ready, clearCache: cacheDrop, LIMIT });
})();
