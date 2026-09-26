/* ============================================================================
 * gamification.js | XP · Levels · Badges · Seasons  (pure domain logic)
 * ----------------------------------------------------------------------------
 * Shared by the leaderboard, the result page and the dashboard. No DOM access,
 * no storage access — every function takes plain data and returns plain data,
 * so the rules can be unit-checked and reused by a future backend verbatim.
 *
 * The numbers below are the published game rules (README §21):
 *   XP      correct +10 · perfect quiz +100 · daily login +25
 *           7-day streak +150 · 30-day streak +500 · 100 tests +1000
 *   Levels  L1 0 · L2 250 · L3 600 · then the gap grows ~45% per level
 *   Badges  8 milestone badges, all DERIVED from real stats — never seeded
 * ========================================================================== */
(() => {
  "use strict";

  const HOA = (window.HOA = window.HOA || {});

  /* ------------------------------------------------------------- XP ------ */
  const XP_RULES = Object.freeze({
    correct: 10,        // per correct answer
    perfectQuiz: 100,   // every question answered correctly
    dailyLogin: 25,     // first activity of the day
    streak7: 150,       // 7 day streak milestone
    streak30: 500,      // 30 day streak milestone
    tests100: 1000,     // 100 completed tests milestone
  });

  /** Total XP earned by one completed attempt (pure). */
  function xpForAttempt({ correct = 0, total = 0, attempted = 0, perfect = null } = {}) {
    const c = Math.max(0, Math.min(Number(correct) || 0, Number(total) || 0));
    const isPerfect =
      perfect === null ? Number(total) > 0 && c === Number(total) : !!perfect;
    return c * XP_RULES.correct + (isPerfect ? XP_RULES.perfectQuiz : 0);
  }

  /* ----------------------------------------------------------- LEVELS ---- */
  /* MIN_XP[level] = XP required to *reach* that level.
   * L1 0 · L2 250 · L3 600 are fixed; from L4 on the gap grows 45% per level
   * and is rounded to a friendly multiple of 5. */
  const MIN_XP = (() => {
    const req = [null, 0, 250, 600];
    let gap = 350;
    for (let lv = 4; lv <= 400; lv++) {
      gap = Math.round((gap * 1.45) / 5) * 5;
      req.push(req[lv - 1] + gap);
    }
    return req;
  })();

  const MAX_LEVEL = MIN_XP.length - 1;

  /** Level a student currently sits in. */
  function levelFor(xp) {
    let x = Math.max(0, Number(xp) || 0);
    for (let lv = MAX_LEVEL; lv >= 1; lv--) {
      if (x >= MIN_XP[lv]) return lv;
    }
    return 1;
  }

  /** How much XP is needed to reach a given level. */
  function xpForLevel(level) {
    const lv = Math.max(1, Math.min(MAX_LEVEL, Math.round(Number(level) || 1)));
    return MIN_XP[lv];
  }

  /** Progress inside the current level → drives the animated bar. */
  function levelProgress(xp) {
    const x = Math.max(0, Number(xp) || 0);
    const level = levelFor(x);
    const floor = MIN_XP[level];
    const ceil = level >= MAX_LEVEL ? null : MIN_XP[level + 1];
    if (ceil === null) {
      return { level, floor, ceil: null, have: x - floor, need: 0, pct: 100, maxed: true };
    }
    const need = ceil - floor;
    const have = x - floor;
    return {
      level, floor, ceil, have, need,
      pct: need > 0 ? Math.max(0, Math.min(100, (have / need) * 100)) : 0,
      maxed: false,
    };
  }

  /* ----------------------------------------------------------- BADGES ---- */
  const BADGES = Object.freeze([
    { id: "quiz-champion",   icon: "🏆", name: "Quiz Champion",   desc: "Complete 25 quizzes" },
    { id: "streak-master",   icon: "🔥", name: "Streak Master",   desc: "Hold a 7 day streak" },
    { id: "punjab-gk",       icon: "📚", name: "Punjab GK Expert", desc: "80%+ accuracy in Punjab GK" },
    { id: "fast-solver",     icon: "⚡", name: "Fast Solver",     desc: "Average under 20s per question" },
    { id: "accuracy-king",   icon: "🎯", name: "Accuracy King",   desc: "Lifetime accuracy of 90%+" },
    { id: "weekly-winner",   icon: "🥇", name: "Weekly Winner",   desc: "Finish #1 on the weekly board" },
    { id: "monthly-winner",  icon: "🏅", name: "Monthly Winner",  desc: "Finish #1 on the monthly board" },
    { id: "top-100",         icon: "⭐", name: "Top 100",         desc: "Break into the all-time top 100" },
  ]);

  /**
   * Derives which badges a profile has earned.
   * @param {object} p   { quizzes, accuracy, streak, avgSecondsPerQuestion,
   *                       punjabGkAccuracy, punjabGkAnswered }
   * @param {object} r   { weekly, monthly, allTime } — ranks, or null when unknown
   */
  function badgesFor(p = {}, r = {}) {
    const has = (id) => BADGES.find((b) => b.id === id);
    const out = [];
    const push = (id, earned, note) => {
      const def = has(id);
      if (def) out.push({ ...def, earned: !!earned, note: note || def.desc });
    };
    push("quiz-champion", (Number(p.quizzes) || 0) >= 25);
    push("streak-master", (Number(p.streak) || 0) >= 7);
    push(
      "punjab-gk",
      (Number(p.punjabGkAnswered) || 0) >= 10 && (Number(p.punjabGkAccuracy) || 0) >= 80
    );
    push(
      "fast-solver",
      (Number(p.quizzes) || 0) >= 5 &&
        Number(p.avgSecondsPerQuestion) > 0 &&
        Number(p.avgSecondsPerQuestion) < 20
    );
    push("accuracy-king", (Number(p.accuracy) || 0) >= 90 && (Number(p.quizzes) || 0) >= 10);
    push("weekly-winner", r.weekly === 1);
    push("monthly-winner", r.monthly === 1);
    push("top-100", Number.isFinite(r.allTime) && r.allTime > 0 && r.allTime <= 100);
    return out;
  }

  const earnedIds = (badges) =>
    (Array.isArray(badges) ? badges : []).filter((b) => b && b.earned).map((b) => b.id);

  /* ---------------------------------------------------------- SEASON ----- */
  /** Season = the current calendar month. Returns label + "ends in" days. */
  function season(now) {
    const d = now ? new Date(now) : new Date();
    const label =
      "Season " +
      d.toLocaleDateString("en-IN", { month: "long", year: "numeric" });
    const start = new Date(d.getFullYear(), d.getMonth(), 1);
    const end = new Date(d.getFullYear(), d.getMonth() + 1, 1);
    const total = end - start;
    const done = Math.max(0, Math.min(total, d - start));
    const msLeft = Math.max(0, end - d);
    return {
      label,
      endsInDays: Math.max(0, Math.ceil(msLeft / 864e5)),
      endsOn: end.toLocaleDateString("en-IN", { day: "numeric", month: "long" }),
      startedOn: start.toLocaleDateString("en-IN", { day: "numeric", month: "long" }),
      progressPct: Math.round((done / total) * 100),
      monthKey: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`,
    };
  }

  /* --------------------------------------------------------- PERCENTILE -- */
  /** "Top X%" for a 1-based rank inside `total` students. */
  function percentile(rank, total) {
    const r = Number(rank) || 0;
    const t = Number(total) || 0;
    if (!r || !t || t <= 1) return 100;
    return Math.max(1, Math.min(100, Math.round(((t - r) / t) * 100)));
  }

  /* ---------------------------------------------------------- HELPERS ---- */
  function initials(name) {
    const parts = String(name || "?")
      .trim()
      .split(/\s+/)
      .filter(Boolean);
    if (!parts.length) return "?";
    const a = parts[0][0] || "";
    const b = parts.length > 1 ? parts[parts.length - 1][0] : "";
    return (a + b).toUpperCase();
  }

  /** Stable hue so an avatar keeps its colour on every render. */
  function hueFor(seed) {
    const s = String(seed || "");
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h % 360;
  }

  function fmtInt(n) {
    const v = Number(n) || 0;
    return v.toLocaleString("en-IN");
  }

  HOA.game = Object.freeze({
    XP_RULES, BADGES, MAX_LEVEL,
    xpForAttempt, levelFor, xpForLevel, levelProgress,
    badgesFor, earnedIds, season, percentile,
    initials, hueFor, fmtInt,
  });
})();
