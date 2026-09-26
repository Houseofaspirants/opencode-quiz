/* ============================================================================
 * leaderboard-api.js | Backend-ready data layer for the Global Leaderboard
 * ----------------------------------------------------------------------------
 * Everything the leaderboard UI renders comes through HOA.lbApi. The UI never
 * knows which database is behind it — it only ever sees the normalised
 * `Entry` shape documented below.
 *
 * ─── PROVIDER CONTRACT ─────────────────────────────────────────────────────
 *   provider.list(q)      q: {period, exam, category, sort, search, page, limit}
 *                         → {entries: Entry[], total, hasMore}
 *   provider.stats(q)     → {students, attempts, highestToday, accuracy, activeToday}
 *   provider.quizBoards() → [{quizId, quizName, total, entries:[Entry]}]
 *   provider.submit(e)    → void            (HTTP provider — see TODO below)
 *
 * ─── ENTRY SHAPE (one normalised row) ──────────────────────────────────────
 *   userId, name, username, profilePhoto, verified, isMe, quizName,
 *   score, totalQuestions, accuracy, timeTaken, xp, level, streak,
 *   badges[], attemptDate, subjectId, categoryId, examIds[], rank, profile
 *
 * ─── PROVIDERS ─────────────────────────────────────────────────────────────
 *   http      REST backend. Selected when `site.leaderboard.apiBase` is set.
 *   firebase  Firestore, via HOA.auth — the single Firebase swap-point (§20).
 *   sample    Deterministic demo board, used while NO backend exists so the
 *             page is never dead. Always disclosed in the UI (see notice).
 *   local     Device-only attempts. Used when `site.leaderboard.sample:false`.
 *
 * Ranking, filtering, search and pagination live in this layer so every
 * provider behaves identically; a real backend only has to return rows.
 * ========================================================================== */
(() => {
  "use strict";

  const HOA = (window.HOA = window.HOA || {});

  /* ---------------------------------------------------------- CONFIG ----- */
  const DEFAULTS = {
    enabled: true,
    provider: "auto",   // auto | http | firebase | sample | local
    apiBase: "",        // e.g. "https://api.houseofaspirants.in"
    sample: true,       // demo board until a backend answers
    pageSize: 20,
  };

  /* TODO(backend): these four endpoints make the board database-backed with
   * no front-end change. Shapes are already normalised by fromApi()/paginate():
   *   GET  /leaderboard?period=&exam=&category=&sort=&q=&page=&limit=
   *        → {entries: Entry[], total: number, hasMore: boolean}
   *   GET  /leaderboard/stats?period=
   *        → {students, attempts, accuracy, activeToday, highestToday}
   *   GET  /leaderboard/quizzes?period=
   *        → {quizzes: [{quizId, quizName, total, entries: Entry[]}]}
   *   POST /leaderboard/attempts   body = Entry   → 204
   * Set site.leaderboard.apiBase in data/site.json and the http provider
   * takes over automatically. Server-side aggregation should replace the
   * client-side ranking for >100k students. */
  const ENDPOINTS = {
    list: "/leaderboard",
    stats: "/leaderboard/stats",
    quiz: "/leaderboard/quizzes",
    submit: "/leaderboard/attempts",
  };

  let cfg = { ...DEFAULTS };
  let source = "local";
  let notice = { kind: "local", text: "" };
  let taxonomy = null;
  let quizPool = null;
  let sampleSet = null;
  let bootP = null;

  const num = (v, d = 0) => (Number.isFinite(Number(v)) ? Number(v) : d);
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
  const norm = (s) => String(s || "").toLowerCase().trim();

  /* ===================================================== BOOT / CONFIG === */
  function init() {
    if (bootP) return bootP;
    bootP = (async () => {
      const index = await HOA.loadIndex();
      const site = (index && index.site) || {};
      cfg = { ...DEFAULTS, ...(site.leaderboard || {}) };
      taxonomy = buildTaxonomy(index, await loadExams());
      quizPool = buildQuizPool(index);

      if (!cfg.enabled) source = "local";
      else if (cfg.provider !== "auto") source = cfg.provider;
      else if (cfg.apiBase) source = "http";
      else if (HOA.auth && HOA.auth.mode === "firebase") source = "firebase";
      else if (cfg.sample) source = "sample";
      else source = "local";

      notice = buildNotice();
      return true;
    })();
    return bootP;
  }

  function buildNotice() {
    switch (source) {
      case "http":
        return { kind: "live", text: "Live global rankings from the House of Aspirants API." };
      case "firebase":
        return { kind: "live", text: "Live global rankings — every signed-in aspirant, in real time." };
      case "sample":
        return {
          kind: "sample",
          text:
            "Sample rankings are shown while the leaderboard database is being " +
            "connected. Your own XP, level, streak and rank are real.",
        };
      default:
        return {
          kind: "local",
          text: "Showing this device's attempts. Connect the leaderboard API to publish global rankings.",
        };
    }
  }

  /* ===================================================== TAXONOMY ======== */
  async function loadExams() {
    try {
      const r = await fetch("data/exams.json", { cache: "no-cache" });
      if (!r.ok) return [];
      const j = await r.json();
      return (j && j.exams) || [];
    } catch {
      return []; // exam filter degrades to "All Exams" — never blocks the board
    }
  }

  /**
   * Exam filter groups. Every id is matched against a REAL exam id from
   * data/exams.json, so a chip can never reference a phantom exam.
   *
   *   punjab-police — derived from exam ids that literally start with it.
   *   patwari       — the `patwari` exam id.
   *   psssb         — mirrors the site's own published grouping on
   *                   punjab-exams.html: "PSSSB Patwari, Forest Guard, Clerk
   *                   and more." Editorial grouping only; the site disclaims
   *                   any commission affiliation elsewhere.
   */
  const EXAM_GROUPS = [
    { id: "punjab-police", label: "Punjab Police", test: (e) => e.id.startsWith("punjab-police-") },
    { id: "psssb", label: "PSSSB", test: (e) => ["patwari", "forest-guard", "clerk"].includes(e.id) },
    { id: "patwari", label: "Patwari", test: (e) => e.id === "patwari" },
  ];
  /* exams already represented by a group chip → not repeated as single chips */
  const GROUP_MEMBERS = new Set([
    "patwari", "forest-guard", "clerk",
    "punjab-police-constable", "punjab-police-asi", "punjab-police-sub-inspector",
    "punjab-police-intelligence-assistant", "punjab-police-jail-warder",
  ]);

  function buildTaxonomy(index, exams) {
    const subjects = (index && index.subjects) || [];
    const categories = [];
    subjects.forEach((s) => {
      (s.categories || []).forEach((c) =>
        categories.push({ id: c.id, name: c.name, subjectId: s.id, key: `${s.id}:${c.id}` })
      );
    });

    const examList = exams.map((e) => ({
      id: e.id, name: e.name, subjects: e.subjects || [], categories: e.categories || [],
    }));

    const examFilters = [
      { id: "all", label: "All Exams" },
      ...EXAM_GROUPS.map((g) => ({ id: g.id, label: g.label, group: true })),
      ...examList.filter((e) => !GROUP_MEMBERS.has(e.id)).map((e) => ({ id: e.id, label: e.name })),
    ];

    return {
      subjects: subjects.map((s) => ({ id: s.id, name: s.name, icon: s.icon })),
      categories,
      exams: examList,
      examFilters,
      /* Category chips = every real GK category + every real subject, so the
       * filter can only ever offer content that exists on the site. */
      categoryFilters: [
        { id: "all", label: "All Categories" },
        ...categories.map((c) => ({ id: c.key, label: c.name })),
        ...subjects.map((s) => ({ id: `subject:${s.id}`, label: s.name })),
      ],
    };
  }

  function examsFor(subjectId, categoryId) {
    if (!taxonomy) return [];
    return taxonomy.exams
      .filter((e) => (subjectId && e.subjects.includes(subjectId)) ||
        (categoryId && e.categories.includes(categoryId)))
      .map((e) => e.id);
  }

  function examMatcher(id) {
    const group = EXAM_GROUPS.find((g) => g.id === id);
    if (!group) return null;
    const ids = taxonomy ? taxonomy.exams.filter(group.test).map((e) => e.id) : [];
    return (r) => r.examIds.some((x) => ids.includes(x));
  }

  /* ===================================================== QUIZ POOL ======= */
  /** Real quizzes published by the site — index.json is the only source. */
  function buildQuizPool(index) {
    const pool = [];
    ((index && index.subjects) || []).forEach((s) => {
      (s.categories || []).forEach((c) =>
        pool.push({ id: `${s.id}:${c.id}`, name: `${c.name} Quiz`,
          subjectId: s.id, subjectName: s.name, categoryId: c.id, categoryName: c.name })
      );
      (s.topics || []).forEach((t) =>
        pool.push({ id: `${s.id}:${t.id}`, name: t.name || `${s.name} Quiz`,
          subjectId: s.id, subjectName: s.name,
          categoryId: (s.categories[0] && s.categories[0].id) || null,
          categoryName: (s.categories[0] && s.categories[0].name) || null })
      );
      pool.push({ id: `subject:${s.id}`, name: `${s.name} Quiz`,
        subjectId: s.id, subjectName: s.name,
        categoryId: (s.categories[0] && s.categories[0].id) || null,
        categoryName: (s.categories[0] && s.categories[0].name) || null });
    });
    pool.push({ id: "daily", name: "Daily Quiz", subjectId: "gk",
      subjectName: "General Knowledge", categoryId: "punjab-gk", categoryName: "Punjab GK" });
    return pool;
  }

  /* ===================================================== SAMPLE DATA ===== */
  /* Deterministic (fixed seed): the board looks identical on every reload, so
   * nothing on screen ever "moves on its own" between visits.               */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const FIRST = ["Gurpreet","Harpreet","Jaspreet","Amrit","Simran","Navjot","Ramandeep","Sukhmeet",
    "Prabhjot","Manpreet","Aman","Jashan","Karan","Neha","Preeti","Ravneet","Satnam","Inderpreet",
    "Baljinder","Harmandeep","Gursewak","Amandeep","Daljeet","Gurleen","Harmeet","Jagdeep","Kuldeep",
    "Mandeep","Naman","Pardeep","Raman","Sukhbir","Tanvi","Arshdeep","Fateh","Gagandeep","Harjot",
    "Ekam","Lovepreet","Mehak","Rupinder","Shivani","Varun","Yashika","Jasleen","Kamalpreet","Nikki",
    "Paramveer","Ritika","Sahil","Taranveer","Uday","Vandana","Ekta","Divya","Harleen"];
  const LAST = ["Singh","Kaur","Sharma","Gupta","Verma","Kumar","Gill","Sidhu","Brar","Dhillon",
    "Bhatti","Randhawa","Sekhon","Mann","Chahal","Grewal","Bajwa","Sandhu","Sohal","Luthra","Arora",
    "Mehta","Joshi","Nair","Reddy","Iyer","Patel","Das","Mandal","Thakur","Chauhan","Kapoor","Sethi",
    "Bhatia","Khosla","Grover","Saini","Rana","Dutta","Mukherjee"];

  const DAY = 864e5;
  const iso = (t) => new Date(t).toISOString().slice(0, 10);

  function streakFromDays(days) {
    if (!days.length) return 0;
    const set = new Set(days);
    const d = new Date();
    if (!set.has(iso(d.getTime()))) d.setDate(d.getDate() - 1);
    let n = 0;
    while (set.has(iso(d.getTime()))) { n++; d.setDate(d.getDate() - 1); }
    return n;
  }

  function longestRun(days) {
    if (!days.length) return 0;
    const sorted = [...new Set(days)].sort();
    let best = 1, run = 1;
    for (let i = 1; i < sorted.length; i++) {
      const prev = new Date(sorted[i - 1] + "T00:00:00");
      const cur = new Date(sorted[i] + "T00:00:00");
      const gap = Math.round((cur - prev) / DAY);
      run = gap === 1 ? run + 1 : 1;
      best = Math.max(best, run);
    }
    return best;
  }

  function buildSample() {
    if (sampleSet) return sampleSet;
    const g = HOA.game;
    const rnd = mulberry32(0x484f4131); // "HOA1"
    const N = 186;
    const now = Date.now();
    const students = [];

    for (let i = 0; i < N; i++) {
      const first = FIRST[Math.floor(rnd() * FIRST.length)];
      const last = LAST[Math.floor(rnd() * LAST.length)];
      const name = `${first} ${last}`;
      const userId = `sample-${String(i + 1).padStart(3, "0")}`;
      const username = norm(first).slice(0, 8) + norm(last).slice(0, 8) + (i % 97 || "");
      const skill = 0.34 + rnd() * 0.62;            // 34..96% ability
      const speed = 9 + rnd() * 26;                 // 9..35 s per question
      const attemptCount = 3 + Math.floor(rnd() * 14);
      const attempts = [];
      const days = [];
      let totalXp = 0;

      for (let a = 0; a < attemptCount; a++) {
        const quiz = quizPool[Math.floor(rnd() * quizPool.length)];
        const total = 10 + Math.floor(rnd() * 16);          // 10..25 questions
        const acc = clamp(Math.round((skill + (rnd() - 0.5) * 0.16) * 100), 5, 100);
        const correct = clamp(Math.round((acc / 100) * total), 0, total);
        // ~42% of students attempt "today" so the Daily tab always has life.
        const age = rnd() < 0.42 ? Math.floor(rnd() * DAY)
          : DAY + Math.floor(rnd() * 58 * DAY);
        const at = now - age;
        days.push(iso(at));
        const seconds = Math.round(total * speed * (0.75 + rnd() * 0.6));
        const gain = g.xpForAttempt({ correct, total }) + (a === 0 ? 25 : 0);
        totalXp += gain;
        attempts.push({
          userId, name, username, quizId: quiz.id, quizName: quiz.name,
          subjectId: quiz.subjectId, categoryId: quiz.categoryId,
          correct, total, percent: total ? Math.round((correct / total) * 100) : 0,
          seconds, at, xp: gain,
        });
      }

      const answered = attempts.reduce((s, x) => s + x.total, 0);
      const right = attempts.reduce((s, x) => s + x.correct, 0);
      const seconds = attempts.reduce((s, x) => s + x.seconds, 0);
      const punjab = attempts.filter((x) => x.categoryId === "punjab-gk");
      const punjabAnswered = punjab.reduce((s, x) => s + x.total, 0);
      const streak = streakFromDays(days);

      const profile = {
        userId, name, username, photo: null,
        quizzes: attempts.length,
        accuracy: answered ? Math.round((right / answered) * 100) : 0,
        xp: totalXp,
        streak,
        longestStreak: longestRun(days),
        avgSecondsPerQuestion: answered ? seconds / answered : 0,
        punjabGkAnswered: punjabAnswered,
        punjabGkAccuracy: punjabAnswered
          ? Math.round((punjab.reduce((s, x) => s + x.correct, 0) / punjabAnswered) * 100)
          : 0,
        correct: right, wrong: answered - right,
        tests: attempts.length,
        avgTime: answered ? Math.round(seconds / answered) : 0,
        lastActive: Math.max.apply(null, attempts.map((x) => x.at)),
        ranks: { allTime: null, weekly: null, monthly: null },
      };
      students.push({ profile, attempts });
    }

    /* Ranks for all three boards are computed once, at build time, so badge
     * membership never flickers while the visitor changes tabs. */
    ["allTime", "weekly", "monthly"].forEach((key) => {
      const period = key === "allTime" ? "all" : key === "weekly" ? "week" : "month";
      rankRows(students, period).forEach((profile, i) => {
        profile.ranks[key] = i + 1;
      });
    });

    students.forEach((s) => {
      const p = s.profile;
      p.badges = g.badgesFor(p, p.ranks);
      p.level = g.levelFor(p.xp);
      p.percentile = g.percentile(p.ranks.allTime, students.length);
    });

    sampleSet = { students, stats: sampleStats(students) };
    return sampleSet;
  }

  /** Students active in `period`, best attempt first → ordered profile list. */
  function rankRows(students, period) {
    const start = PERIOD_START[period] ? PERIOD_START[period]() : 0;
    return students
      .filter((s) => s.attempts.some((a) => a.at >= start))
      .map((s) => ({ p: s.profile, best: bestIn(s.attempts, start) }))
      .sort((a, b) => b.best.percent - a.best.percent ||
        b.best.correct - a.best.correct || b.best.at - a.best.at)
      .map((x) => x.p);
  }

  function bestIn(attempts, start) {
    return attempts
      .filter((a) => a.at >= start)
      .sort((a, b) => b.percent - a.percent || b.correct - a.correct || b.at - a.at)[0];
  }

  function sampleStats(students) {
    let attempts = 0, answered = 0, right = 0, activeToday = 0, highestToday = 0;
    const now = Date.now();
    students.forEach((s) => {
      let today = false;
      s.attempts.forEach((x) => {
        attempts++; answered += x.total; right += x.correct;
        if (now - x.at < DAY) { today = true; highestToday = Math.max(highestToday, x.percent); }
      });
      if (today) activeToday++;
    });
    return {
      students: students.length,
      attempts,
      accuracy: answered ? Math.round((right / answered) * 100) : 0,
      activeToday, highestToday,
    };
  }

  /* ===================================================== RANKING ========= */
  const PERIOD_START = {
    day: () => { const d = new Date(); d.setHours(0, 0, 0, 0); return d.getTime(); },
    week: () => Date.now() - 7 * DAY,
    month: () => Date.now() - 30 * DAY,
    all: () => 0,
  };

  /** One row per student active in `period` (their best attempt). */
  function buildRows(period) {
    const set = buildSample();
    const start = PERIOD_START[period] ? PERIOD_START[period]() : 0;
    const rows = [];
    set.students.forEach((s) => {
      const win = s.attempts.filter((a) => a.at >= start);
      if (!win.length) return;
      const best = bestIn(s.attempts, start);
      const p = s.profile;
      rows.push({
        userId: p.userId, name: p.name, username: p.username, profilePhoto: p.photo,
        verified: false, isMe: false,
        quizName: best.quizName,
        score: best.correct, totalQuestions: best.total,
        accuracy: best.percent, timeTaken: best.seconds,
        xp: p.xp, level: p.level, streak: p.streak, badges: p.badges,
        attemptDate: best.at,
        subjectId: best.subjectId, categoryId: best.categoryId,
        examIds: examsFor(best.subjectId, best.categoryId),
        profile: p,
      });
    });
    return rows;
  }

  /* ===================================================== FILTERS/SORT ==== */
  const SORTS = {
    score: (a, b) => b.score - a.score || b.accuracy - a.accuracy || b.attemptDate - a.attemptDate,
    xp: (a, b) => b.xp - a.xp || b.score - a.score,
    accuracy: (a, b) => b.accuracy - a.accuracy || b.score - a.score,
    time: (a, b) => (a.timeTaken || Infinity) - (b.timeTaken || Infinity) || b.accuracy - a.accuracy,
    newest: (a, b) => b.attemptDate - a.attemptDate,
  };
  const bySort = (k) => SORTS[k] || SORTS.score;

  function applyFilters(rows, q) {
    let out = rows;
    if (q.exam && q.exam !== "all") {
      const match = examMatcher(q.exam);
      const ids = taxonomy && !match ? [q.exam] : null;
      out = match ? out.filter(match)
        : ids ? out.filter((r) => r.examIds.includes(ids[0]))
        : out;
    }
    if (q.category && q.category !== "all") {
      if (q.category.startsWith("subject:")) {
        const sid = q.category.slice(8);
        out = out.filter((r) => r.subjectId === sid);
      } else {
        const cid = q.category.split(":").pop();
        out = out.filter((r) => r.categoryId === cid);
      }
    }
    if (q.search) {
      const s = norm(q.search);
      out = out.filter((r) => norm(r.name).includes(s) || norm(r.username).includes(s));
    }
    return out;
  }

  function paginate(rows, q) {
    const sorted = rows.slice().sort(bySort(q.sort));
    const page = Math.max(1, num(q.page, 1));
    const limit = Math.max(5, num(q.limit, DEFAULTS.pageSize));
    const start = (page - 1) * limit;
    const entries = sorted
      .slice(start, start + limit)
      .map((e, i) => ({ ...e, rank: start + i + 1 }));
    return { entries, total: sorted.length, hasMore: start + limit < sorted.length };
  }

  /* ===================================================== NORMALISING ===== */
  function fromApi(r) {
    const total = num(r.totalQuestions ?? r.total);
    const correct = num(r.score ?? r.correct);
    const accuracy = r.accuracy != null ? num(r.accuracy)
      : r.percent != null ? num(r.percent)
      : total ? Math.round((correct / total) * 100) : 0;
    const xp = num(r.xp ?? r.XP);
    return {
      userId: String(r.userId ?? r.uid ?? r.id ?? "anon"),
      name: r.name || r.username || "Aspirant",
      username: r.username || norm(r.name || "aspirant").replace(/\s+/g, ""),
      profilePhoto: r.profilePhoto || r.photo || null,
      verified: !!r.verified,
      isMe: !!r.isMe || !!r.me,
      quizName: r.quizName || r.quiz || "Quiz",
      score: correct, totalQuestions: total, accuracy,
      timeTaken: num(r.timeTaken ?? r.seconds),
      xp, level: num(r.level) || HOA.game.levelFor(xp),
      streak: num(r.streak),
      badges: Array.isArray(r.badges) ? r.badges : [],
      attemptDate: num(r.attemptDate ?? r.at ?? Date.now()),
      subjectId: r.subjectId || null,
      categoryId: r.categoryId || null,
      examIds: Array.isArray(r.examIds) ? r.examIds : [],
      profile: r.profile || null,
    };
  }

  /* ===================================================== PROVIDERS ======= */

  /* ---- HTTP — TODO(backend): the real REST implementation ---------------- */
  async function httpList(q) {
    const p = new URLSearchParams();
    p.set("period", q.period); p.set("sort", q.sort);
    if (q.exam && q.exam !== "all") p.set("exam", q.exam);
    if (q.category && q.category !== "all") p.set("category", q.category);
    if (q.search) p.set("q", q.search);
    p.set("page", String(q.page)); p.set("limit", String(q.limit));
    const res = await fetch(`${cfg.apiBase}${ENDPOINTS.list}?${p}`, {
      headers: { Accept: "application/json" }, cache: "no-store",
    });
    if (!res.ok) throw new Error("leaderboard API " + res.status);
    const j = await res.json();
    const entries = (j.entries || j.data || []).map(fromApi);
    return { entries, total: num(j.total, entries.length), hasMore: !!j.hasMore };
  }

  async function httpStats() {
    const res = await fetch(`${cfg.apiBase}${ENDPOINTS.stats}`, { cache: "no-store" });
    if (!res.ok) throw new Error("leaderboard stats " + res.status);
    const j = await res.json();
    return {
      students: num(j.students), attempts: num(j.attempts), accuracy: num(j.accuracy),
      activeToday: num(j.activeToday), highestToday: num(j.highestToday),
    };
  }

  async function httpQuizBoards(q) {
    const res = await fetch(`${cfg.apiBase}${ENDPOINTS.quiz}?period=${q.period}`, { cache: "no-store" });
    if (!res.ok) throw new Error("leaderboard quizzes " + res.status);
    const j = await res.json();
    return (j.quizzes || []).map((x) => ({
      quizId: x.quizId, quizName: x.quizName, total: num(x.total),
      entries: (x.entries || []).map(fromApi),
    }));
  }

  async function httpSubmit(entry) {
    const res = await fetch(`${cfg.apiBase}${ENDPOINTS.submit}`, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(entry),
    });
    if (!res.ok) throw new Error("leaderboard submit " + res.status);
  }

  /* ---- Firebase — HOA.auth owns every Firestore call (README §20) -------- */
  async function firebaseRows(q) {
    const since = PERIOD_START[q.period] ? PERIOD_START[q.period]() : 0;
    const raw = await HOA.auth.fetchLeaderboard({ since, limit: 500 });
    const me = HOA.auth.user && HOA.auth.user();
    const rows = raw.map((r) => {
      const e = fromApi({ ...r, userId: r.uid, quizName: r.quiz });
      if (me && r.uid === me.uid) e.isMe = true;
      return e;
    });
    return rows;
  }

  async function firebaseList(q) {
    return paginate(applyFilters(await firebaseRows(q), q), q);
  }

  async function firebaseStats() {
    const rows = (await firebaseRows({ period: "day" })).map(fromApi);
    const today = rows.length ? rows : await firebaseRows({ period: "all" }).then((r) => r.map(fromApi));
    const students = new Set(today.map((e) => e.userId)).size;
    return {
      students,
      attempts: today.length,
      accuracy: today.length ? Math.round(today.reduce((s, e) => s + e.accuracy, 0) / today.length) : 0,
      activeToday: students,
      highestToday: today.reduce((m, e) => Math.max(m, e.accuracy), 0),
    };
  }

  /* ---- sample (deterministic demo board, disclosed to the visitor) ------- */
  /* The visitor's own row is always merged in: their XP, level, streak and
   * rank are real even while the other rows are sample data.               */
  function sampleList(q) {
    return paginate(applyFilters(buildRows(q.period).concat(deviceRows(q.period)), q), q);
  }

  /* ---- local / device --------------------------------------------------- */
  function scoresFor(period) {
    if (!HOA.leaderboard) return [];
    const key = period === "day" ? "today" : period === "week" ? "week" : "all";
    const raw = HOA.leaderboard.get(key);
    const start = PERIOD_START[period] ? PERIOD_START[period]() : 0;
    return start ? raw.filter((r) => r.at >= start) : raw;
  }

  /** The visitor's own profile, derived from real stored progress. */
  function deviceProfile() {
    if (!HOA.progress) return null;
    const g = HOA.game;
    const p = HOA.progress.get();
    const answered = num(p.answered);
    const session = HOA.auth && HOA.auth.user ? HOA.auth.user() : null;
    const xp = HOA.leaderboard
      ? HOA.leaderboard.get("all")
          .reduce((s, r) => s + g.xpForAttempt({ correct: num(r.correct), total: num(r.total) }), 0)
      : 0;
    const profile = {
      userId: (session && session.uid) || "device",
      name: (session && session.name) || "You",
      username: norm((session && session.name) || "you").replace(/\s+/g, "") || "you",
      photo: (session && session.photo) || null,
      quizzes: num(p.quizzes),
      accuracy: answered ? Math.round((num(p.correct) / answered) * 100) : 0,
      xp,
      streak: HOA.progress.streak ? HOA.progress.streak() : 0,
      longestStreak: 0,
      avgSecondsPerQuestion: answered ? num(p.studySeconds) / answered : 0,
      punjabGkAnswered: 0, punjabGkAccuracy: 0,
      correct: num(p.correct), wrong: answered - num(p.correct),
      tests: num(p.quizzes),
      avgTime: answered ? Math.round(num(p.studySeconds) / answered) : 0,
      lastActive: Date.now(),
      ranks: { allTime: null, weekly: null, monthly: null },
    };
    profile.badges = g.badgesFor(profile, profile.ranks);
    profile.level = g.levelFor(profile.xp);
    return profile;
  }

  /**
   * ONE row for the visitor (a leaderboard ranks students, not attempts).
   * Null when this device has never completed a quiz.
   */
  function deviceRow(period) {
    const win = scoresFor(period);
    if (!win.length) return null;
    const p = deviceProfile();
    if (!p) return null;
    const best = win.slice()
      .sort((a, b) => num(b.percent) - num(a.percent) ||
        num(b.correct) - num(a.correct) || num(b.at) - num(a.at))[0];
    return {
      userId: p.userId, name: p.name, username: p.username,
      profilePhoto: p.photo,
      verified: !!(HOA.auth && HOA.auth.user && HOA.auth.user() &&
        HOA.auth.user().provider === "google"),
      isMe: true,
      quizName: best.quiz || "Quiz",
      score: num(best.correct), totalQuestions: num(best.total),
      accuracy: num(best.percent), timeTaken: 0,
      xp: p.xp, level: p.level, streak: p.streak,
      badges: p.badges, attemptDate: num(best.at),
      subjectId: null, categoryId: null, examIds: [], profile: p,
    };
  }

  function deviceRows(period) {
    const r = deviceRow(period);
    return r ? [r] : [];
  }

  /* ===================================================== PUBLIC API ====== */
  async function list(q = {}) {
    await init();
    const query = { period: "day", exam: "all", category: "all", sort: "score",
      search: "", page: 1, limit: cfg.pageSize, ...q };
    if (!cfg.enabled) return { entries: [], total: 0, hasMore: false };
    try {
      if (source === "http") return await httpList(query);
      if (source === "firebase") return await firebaseList(query);
      if (source === "sample") return sampleList(query);
      return paginate(deviceRows(query.period), query);
    } catch (err) {
      console.warn("[HOA.lbApi] list failed:", err && err.message);
      if (source !== "sample" && source !== "local") {
        // backend unreachable → degrade to the sample board rather than dying
        return sampleList(query);
      }
      return { entries: [], total: 0, hasMore: false };
    }
  }

  async function stats(q = {}) {
    await init();
    const period = q.period || "day";
    try {
      if (source === "http") return await httpStats();
      if (source === "firebase") return await firebaseStats();
      if (source === "sample") {
        const s = buildSample().stats;
        const rows = buildRows(period);
        return {
          students: s.students, attempts: s.attempts, accuracy: s.accuracy,
          activeToday: s.activeToday,
          highestToday: rows.length ? Math.max.apply(null, rows.map((r) => r.accuracy)) : 0,
        };
      }
      const p = HOA.progress ? HOA.progress.get() : {};
      const answered = num(p.answered);
      return {
        students: 1, attempts: num(p.quizzes),
        accuracy: answered ? Math.round((num(p.correct) / answered) * 100) : 0,
        activeToday: num(p.quizzes) ? 1 : 0, highestToday: num(p.best),
      };
    } catch (err) {
      console.warn("[HOA.lbApi] stats failed:", err && err.message);
      return { students: 0, attempts: 0, accuracy: 0, activeToday: 0, highestToday: 0 };
    }
  }

  async function quizBoards(q = {}) {
    await init();
    const period = q.period || "all";
    try {
      if (source === "http") return await httpQuizBoards(q);
      if (source === "firebase") return paginateQuiz(await firebaseRows({ period }), period);
      if (source === "sample") return paginateQuiz(buildRows(period).concat(deviceRows(period)), period);
      return paginateQuiz(deviceRows(period), period);
    } catch (err) {
      console.warn("[HOA.lbApi] quiz boards failed:", err && err.message);
      return [];
    }
  }

  function paginateQuiz(rows) {
    const byQuiz = new Map();
    rows.forEach((r) => {
      const k = r.quizName || "Quiz";
      if (!byQuiz.has(k)) byQuiz.set(k, { quizId: norm(k).replace(/\s+/g, "-"), quizName: k, total: 0, entries: [] });
      const b = byQuiz.get(k);
      b.total++; b.entries.push(r);
    });
    return [...byQuiz.values()]
      .map((b) => ({ ...b, entries: b.entries.slice().sort(bySort("score")).slice(0, 3) }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 6);
  }

  /** The visitor's own standing — always global, never narrowed by filters. */
  async function myRank(q = {}) {
    await init();
    const res = await list({ period: q.period || "day", sort: q.sort || "score",
      page: 1, limit: 1000 });
    const me = res.entries.find((e) => e.isMe) || myEntryFromDevice();
    if (!me) return null;
    const ranked = res.entries.slice().sort(bySort(q.sort || "score"));
    const idx = ranked.findIndex((e) => e.userId === me.userId && e.isMe);
    const rank = idx >= 0 ? idx + 1 : null;
    const g = HOA.game;
    const above = idx > 0 ? ranked[idx - 1] : null;
    return {
      ...me, rank, total: res.total,
      percentile: rank ? g.percentile(rank, res.total) : 100,
      progress: g.levelProgress(me.xp),
      nextRank: above ? { rank: idx, gap: Math.max(0, num(above.xp) - num(me.xp)) } : null,
    };
  }

  /** The visitor's own profile, independent of which provider is active. */
  function myEntryFromDevice() {
    const r = deviceRow("all");
    if (r) return r;
    const p = deviceProfile();
    if (!p) return null;
    return {
      userId: p.userId, name: p.name, username: p.username, profilePhoto: p.photo,
      verified: false, isMe: true, quizName: "—",
      score: 0, totalQuestions: 0, accuracy: p.accuracy, timeTaken: 0,
      xp: p.xp, level: p.level, streak: p.streak,
      badges: p.badges, attemptDate: p.lastActive,
      subjectId: null, categoryId: null, examIds: [], profile: p,
    };
  }

  /** Enriches one row with the full profile-modal dataset. */
  async function profile(entry) {
    await init();
    const g = HOA.game;
    const p = (entry && entry.profile) || {};
    const lp = g.levelProgress(num(entry.xp));
    const badges = (entry.badges && entry.badges.length)
      ? entry.badges : g.badgesFor(p, p.ranks || {});
    return {
      userId: entry.userId, name: entry.name, username: entry.username,
      photo: entry.profilePhoto, verified: entry.verified,
      level: lp.level, xp: num(entry.xp), progress: lp,
      rank: entry.rank || null, accuracy: num(entry.accuracy),
      totalTests: num(p.tests ?? p.quizzes),
      correct: num(p.correct), wrong: num(p.wrong),
      avgTime: num(p.avgTime),
      streak: num(entry.streak), longestStreak: num(p.longestStreak),
      badges, recent: await recentFor(entry),
      quizName: entry.quizName, attemptDate: entry.attemptDate,
      percentile: num(p.percentile),
      isMe: entry.isMe,
    };
  }

  async function recentFor(entry) {
    if (source === "sample" && entry.profile && entry.profile.userId) {
      const s = buildSample().students.find((x) => x.profile.userId === entry.profile.userId);
      if (!s) return [];
      return s.attempts.slice().sort((a, b) => b.at - a.at).slice(0, 6).map((a) => ({
        quizName: a.quizName, correct: a.correct, total: a.total,
        accuracy: a.percent, seconds: a.seconds, at: a.at,
      }));
    }
    if (entry.isMe && HOA.progress) {
      const p = HOA.progress.get();
      const hist = p.history || [];
      return hist.slice(-6).reverse().map((pct, i) => ({
        quizName: `Attempt ${hist.length - i}`,
        correct: Math.round((pct / 100) * 10), total: 10,
        accuracy: pct, seconds: 0, at: 0,
      }));
    }
    return [];
  }

  /** Backend write path. Local + Firebase writes stay where they already are
   *  (core.js leaderboard.submit / auth.js syncResult) — this only pushes to
   *  the HTTP backend once one exists. */
  async function submit(entry) {
    await init();
    if (source !== "http") return { queued: false };
    try { await httpSubmit(entry); return { queued: true }; }
    catch (err) {
      console.warn("[HOA.lbApi] submit failed:", err && err.message);
      return { queued: false, error: err };
    }
  }

  HOA.lbApi = Object.freeze({
    init, list, stats, quizBoards, myRank, profile, submit,
    ENDPOINTS, EXAM_GROUPS,
    get source() { return source; },
    get notice() { return notice; },
    get config() { return { ...cfg }; },
    get taxonomy() { return taxonomy; },
  });
})();
