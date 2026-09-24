/* ============================================================================
 * quiz.js | QUIZ ENGINE
 * ----------------------------------------------------------------------------
 * Modes (via query string):
 *   quiz.html?subject=gk&topic=polity   → one topic quiz
 *   quiz.html?mode=daily                → Daily Challenge (random, new daily)
 *   quiz.html?mode=mock&subject=all&count=50&minutes=60 → full-length mock
 *
 * Features: per-question timer, overall timer, auto-next, answer lock on
 * timeout, palette, progress bar, mark-for-review, skip, keyboard nav,
 * autosave/resume, bookmarking, submit.
 *
 * Contains ZERO questions - every item is loaded from /questions/**.json
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc, toast, fmtTime, uid, bookmarks } = HOA;

  /* ------------------------------------------------------- 0. BOOT ------ */
  const params = new URLSearchParams(location.search);
  const mode = params.get("mode") || "topic"; // topic | daily | mock
  const idx = await HOA.loadIndex();
  const site = idx.site || {};

  /* ------------------------------------------------------- Dynamic SEO -
   * Topic quizzes are indexable and get their own canonical URL.
   * Daily / mock sessions are personal → kept out of the search index. */
  const siteBase = String(site.url || "").replace(/\/+$/, "");
  if (mode === "topic") {
    const sParam = params.get("subject") || "";
    const tParam = params.get("topic") || "";
    if (sParam && tParam) {
      HOA.seo({
        canonical: `${siteBase}/quiz?subject=${encodeURIComponent(sParam)}&topic=${encodeURIComponent(tParam)}`,
        robots: "index, follow",
      });
    }
  } else {
    HOA.seo({ robots: "noindex, nofollow" });
    const canon = document.querySelector('link[rel="canonical"]');
    if (canon) canon.remove();
  }
  const SUBJECTS = idx.subjects || [];

  const els = {
    title: document.getElementById("quizTitle"),
    sub: document.getElementById("quizSub"),
    qCount: document.getElementById("qCount"),
    qNum: document.getElementById("qNum"),
    qDifficulty: document.getElementById("qDifficulty"),
    qTopicTag: document.getElementById("qTopic"),
    qText: document.getElementById("qText"),
    options: document.getElementById("options"),
    palette: document.getElementById("palette"),
    fill: document.getElementById("progressFill"),
    progressText: document.getElementById("progressText"),
    qTimer: document.getElementById("qTimer"),
    oTimer: document.getElementById("oTimer"),
    prev: document.getElementById("btnPrev"),
    next: document.getElementById("btnNext"),
    skip: document.getElementById("btnSkip"),
    mark: document.getElementById("btnMark"),
    bookmark: document.getElementById("btnBookmark"),
    submit: document.getElementById("btnSubmit"),
    main: document.getElementById("quizMain"),
    empty: document.getElementById("quizEmpty"),
    resumeBar: document.getElementById("resumeBar"),
  };

  let QUIZ = null; // { title, subject, topic, questions[], key, defaults }

  /* ============================================ 1. RESOLVE QUIZ CONTENT = */
  async function resolveQuiz() {
    /* ----------------------------- DAILY: seeded random from ALL quizzes - */
    if (mode === "daily") {
      const today = new Date().toISOString().slice(0, 10);
      const pool = [];
      SUBJECTS.forEach((s) =>
        s.topics
          .filter((t) => t.available)
          .forEach((t) => pool.push({ s, t }))
      );
      if (!pool.length) return null;

      // Deterministic per day: same challenge for everyone all day.
      let seed = 0;
      for (const ch of today) seed = (seed * 31 + ch.charCodeAt(0)) >>> 0;
      const rand = mulberry32(seed);

      const picked = shuffleWith(pool, rand).slice(0, Math.min(pool.length, 6));
      const questions = [];
      for (const { s, t } of picked) {
        try {
          const data = await HOA.loadQuestions(t.file);
          shuffleWith(data.questions, rand).slice(0, 5).forEach((q) =>
            questions.push({ ...q, subject: q.subject || s.id, topic: q.topic || t.name })
          );
        } catch { /* file may have been deleted mid-session */ }
        if (questions.length >= (Number(site.dailyQuizSize) || 20)) break;
      }
      return {
        title: "Daily Challenge",
        subject: null, subjectName: "Mixed", topicName: today,
        key: `daily:${today}`,
        questions: shuffleWith(questions, rand).slice(0, Number(site.dailyQuizSize) || 20),
        defaultSeconds: Number(site.questionSeconds) || 30,
        overall: (Number(site.dailyQuizSize) || 20) * (Number(site.questionSeconds) || 30),
      };
    }

    /* ----------------------------------------- MOCK: pull across subjects */
    if (mode === "mock") {
      const wantSubject = params.get("subject") || "all";
      const count = Math.max(5, Number(params.get("count")) || 20);
      const minutes = Math.max(1, Number(params.get("minutes")) || 15);
      const src = wantSubject === "all"
        ? SUBJECTS
        : SUBJECTS.filter((s) => s.id === wantSubject);
      const pool = [];
      src.forEach((s) =>
        s.topics.filter((t) => t.available).forEach((t) => pool.push({ s, t }))
      );
      if (!pool.length) return null;

      const rand = mulberry32(Date.now() >>> 0); // fresh every attempt
      const questions = [];
      const order = shuffleWith([...pool], rand);
      let i = 0;
      while (questions.length < count && i < order.length * 3) {
        const { s, t } = order[i % order.length];
        i++;
        try {
          const data = await HOA.loadQuestions(t.file);
          shuffleWith(data.questions, rand).forEach((q) => {
            if (questions.length < count)
              questions.push({ ...q, subject: q.subject || s.id, topic: q.topic || t.name });
          });
        } catch { /* ignore missing file */ }
      }
      const name = wantSubject === "all"
        ? "Full Length Mock Test"
        : `${(src[0] || {}).name || ""} Mock Test`;
      return {
        title: name, subject: wantSubject,
        subjectName: name, topicName: `${count} Q · ${minutes} min`,
        key: `mock:${wantSubject}:${count}:${uid()}`,
        questions, defaultSeconds: Number(site.questionSeconds) || 30,
        overall: minutes * 60,
      };
    }

    /* ------------------------------------------------- TOPIC: single file - */
    const subjectId = params.get("subject") || "";
    const topicId = params.get("topic") || "";
    const subject = SUBJECTS.find((s) => s.id === subjectId);
    const topic = subject?.topics.find((t) => t.id === topicId);

    if (!subject || !topic) return null;

    let questions = [];
    let meta = {};
    if (topic.available) {
      try {
        const data = await HOA.loadQuestions(topic.file);
        questions = data.questions;
        meta = data.meta;
      } catch (e) {
        console.warn("[HOA] topic load failed", e.message);
      }
    }
    const perQ = Number(meta.questionSeconds) || Number(site.questionSeconds) || 30;
    return {
      title: topic.name,
      subject: subject.id, subjectName: subject.name,
      subjectIcon: subject.icon,
      topicName: topic.name, topicId: topic.id,
      key: `topic:${subject.id}:${topic.id}`,
      questions,
      defaultSeconds: perQ,
      // Configurable overall timer: file "timeLimit" (sec) wins, else Q × per-Q.
      overall: Number(meta.timeLimit) || questions.length * perQ,
      href: `quiz.html?subject=${subject.id}&topic=${topic.id}`,
    };
  }

  /* --------------------------------------------- tiny seeded RNG helpers - */
  function mulberry32(a) {
    return function () {
      a |= 0; a = (a + 0x6d2b79f5) | 0;
      let t = Math.imul(a ^ (a >>> 15), 1 | a);
      t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }
  function shuffleWith(arr, rand) {
    const a = [...arr];
    for (let i = a.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [a[i], a[j]] = [a[j], a[i]];
    }
    return a;
  }

  /* ================================================ 2. SESSION STATE ==== */
  const S = {
    i: 0,                       // current question index
    answers: [],                // chosen option index | null
    marks: [],                  // mark for review flags
    visited: [],                // palette "seen" flags
    qLeft: 0,                   // per-question countdown (seconds)
    overallLeft: 0,             // overall countdown (seconds)
    startedAt: 0,
    locked: false,
    tick: null,
  };

  const save = () =>
    HOA.db.set("session:" + QUIZ.key, {
      i: S.i, answers: S.answers, marks: S.marks, visited: S.visited,
      qLeft: S.qLeft, overallLeft: S.overallLeft,
      startedAt: S.startedAt, locked: S.locked,
    });

  const attempted = () => S.answers.filter((a) => a !== null).length;

  /* ==================================================== 3. RENDERING ==== */
  function renderQuestion() {
    const q = QUIZ.questions[S.i];
    if (!q) return;
    S.visited[S.i] = true;

    els.qCount.textContent = `Question ${S.i + 1} of ${QUIZ.questions.length}`;
    els.qText.innerHTML = esc(q.q);

    // Header badges: number, difficulty & topic tag (only if JSON provides them)
    if (els.qNum) els.qNum.textContent = `#${S.i + 1}`;
    if (els.qDifficulty) {
      els.qDifficulty.textContent = q.difficulty || "";
      els.qDifficulty.classList.toggle("hidden", !q.difficulty);
    }
    if (els.qTopicTag) {
      const tag = q.topic || QUIZ.title || "";
      els.qTopicTag.textContent = tag;
      els.qTopicTag.classList.toggle("hidden", !tag);
    }

    els.options.innerHTML = q.options
      .map((opt, i) => {
        const sel = S.answers[S.i] === i;
        return `<button class="option${sel ? " selected" : ""}" data-opt="${i}"
          ${S.locked ? "disabled" : ""} aria-pressed="${sel}">
          <span class="opt-key">${String.fromCharCode(65 + i)}</span>
          <span>${esc(opt)}</span>
        </button>`;
      })
      .join("");

    // Controls state
    els.prev.disabled = S.i === 0 || S.locked;
    els.next.disabled = S.i === QUIZ.questions.length - 1 || S.locked;
    els.skip.disabled = S.locked;
    els.mark.disabled = S.locked;
    els.mark.className = `btn ${S.marks[S.i] ? "btn-soft" : ""}`;
    els.mark.innerHTML = S.marks[S.i]
      ? "✔ Marked for Review" : "📌 Mark for Review";
    els.bookmark.innerHTML = bookmarks.has(bmKey())
      ? "★ Bookmarked" : "☆ Bookmark";

    // Per-question timer resets on navigation
    S.qLeft = QUIZ.defaultSeconds;
    updateTimers();

    renderPalette();
    updateProgress();
    save();
  }

  const bmKey = () =>
    `${QUIZ.key}:${S.i}:${(QUIZ.questions[S.i]?.q || "").slice(0, 40)}`;

  function renderPalette() {
    els.palette.innerHTML = QUIZ.questions
      .map((_, i) => {
        const cls = [
          "pal-btn",
          S.answers[i] !== null ? "answered" : "",
          S.marks[i] ? "marked" : "",
          S.visited[i] ? "visited" : "",
          i === S.i ? "current" : "",
        ].filter(Boolean).join(" ");
        return `<button class="${cls}" data-goto="${i}" aria-label="Question ${i + 1}">${
          i + 1
        }</button>`;
      })
      .join("");
  }

  function updateProgress() {
    const done = attempted();
    const pct = QUIZ.questions.length
      ? Math.round((done / QUIZ.questions.length) * 100) : 0;
    els.fill.style.width = pct + "%";
    els.progressText.textContent =
      `${done} of ${QUIZ.questions.length} answered (${pct}%)`;
  }

  function updateTimers() {
    els.qTimer.innerHTML = `⏱ ${fmtTime(S.qLeft)} <small>Q</small>`;
    els.oTimer.innerHTML = `⌛ ${fmtTime(S.overallLeft)} <small>Total</small>`;
    els.qTimer.className = "timer-pill" +
      (S.qLeft <= 5 ? " danger" : S.qLeft <= 10 ? " warn" : "");
    els.oTimer.className = "timer-pill" +
      (S.overallLeft <= 30 ? " danger" : S.overallLeft <= 60 ? " warn" : "");
  }

  /* ================================================== 4. NAVIGATION ===== */
  function go(i) {
    if (S.locked) return;
    if (i < 0 || i >= QUIZ.questions.length) return;
    S.i = i;
    renderQuestion();
    els.main.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function choose(optIndex) {
    if (S.locked) return;
    S.answers[S.i] = optIndex;
    renderQuestion();
    // Auto-advance is deliberate: tap answer → next question.
    if (S.i < QUIZ.questions.length - 1) {
      setTimeout(() => go(S.i + 1), 260);
    }
  }

  /* ===================================================== 5. TIMERS ======= */
  function startTimers() {
    clearInterval(S.tick);
    S.tick = setInterval(() => {
      if (S.locked) return;

      // Overall timer
      S.overallLeft--;
      // Per-question timer
      if (S.qLeft > 0) S.qLeft--;
      updateTimers();

      // Time over for this question → auto next (spec requirement)
      if (S.qLeft === 0 && S.i < QUIZ.questions.length - 1) {
        toast("Time up! Moving to the next question ⏭️", 1500);
        go(S.i + 1);
      }

      // Overall time over → lock answers and submit
      if (S.overallLeft <= 0) {
        lockAndSubmit("⏰ Time over! Your answers were locked and the quiz was submitted.");
      }

      // Save once every 5 seconds (autosave)
      if (S.overallLeft % 5 === 0) save();
    }, 1000);
  }

  function lockAndSubmit(reason) {
    if (S.locked) return;
    S.locked = true;
    clearInterval(S.tick);
    save();
    showOverlay(reason);
  }

  function showOverlay(reason) {
    const ov = document.createElement("div");
    ov.className = "lock-overlay";
    ov.innerHTML = `
      <div class="lock-box">
        <div class="lk-icon">🔐</div>
        <h3>Answers locked</h3>
        <p class="muted mt-1">${esc(reason)}</p>
        <p class="mt-2"><b>${attempted()}</b> attempted ·
           <b>${QUIZ.questions.length - attempted()}</b> skipped</p>
        <div class="btn-row mt-3" style="justify-content:center">
          <button class="btn btn-primary" id="goResult">See Result →</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector("#goResult").addEventListener("click", finish);
    // Auto-continue shortly (but keep the button for control)
    setTimeout(finish, 2600);
  }

  /* ====================================================== 6. FINISH ====== */
  function finish() {
    clearInterval(S.tick);
    const secs = Math.round((Date.now() - S.startedAt) / 1000);

    let correct = 0, wrong = 0, skipped = 0;
    const review = QUIZ.questions.map((q, i) => {
      const ans = S.answers[i];
      let status;
      if (ans === null || ans === undefined) { status = "skipped"; skipped++; }
      else if (ans === q.correct) { status = "correct"; correct++; }
      else { status = "wrong"; wrong++; }
      return {
        id: i + 1, q: q.q, options: q.options,
        correct: q.correct, answer: ans, status,
        explanation: q.explanation, reference: q.reference,
        topic: q.topic, subject: q.subject, difficulty: q.difficulty,
      };
    });

    const attemptedN = correct + wrong;
    const total = QUIZ.questions.length;
    const accuracy = attemptedN ? Math.round((correct / attemptedN) * 100) : 0;
    const percent = total ? Math.round((correct / total) * 100) : 0;
    const passLine = Number(site.passPercent) || 40;
    const passed = percent >= passLine;

    const result = {
      id: uid(),
      title: QUIZ.title,
      mode,
      href: QUIZ.href || "quiz.html?mode=" + mode,   // used by "Retake"
      subjectName: QUIZ.subjectName || "",
      total, attempted: attemptedN, correct, wrong, skipped,
      accuracy, percent,
      score: correct,
      passLine, passed,
      seconds: secs,
      at: Date.now(),
      review,
    };

    // ---- persist everywhere the other pages read from --------------------
    HOA.db.set("lastResult", result);
    HOA.db.remove("session:" + QUIZ.key);          // clear autosave
    HOA.progress.record({
      correct, total, attempted: attemptedN,
      seconds: secs, subject: QUIZ.subject || "mixed",
    });
    // Score is submitted to the leaderboard exactly once, by result.js
    // (keeps a single write path and prevents duplicate entries).
    location.href = "result.html";
  }

  /* =============================================== 7. EVENT WIRING ======= */
  function wire() {
    els.options.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-opt]");
      if (btn) choose(Number(btn.dataset.opt));
    });
    els.palette.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-goto]");
      if (btn) go(Number(btn.dataset.goto));
    });
    els.prev.addEventListener("click", () => go(S.i - 1));
    els.next.addEventListener("click", () => go(S.i + 1));
    els.skip.addEventListener("click", () => {
      if (S.i < QUIZ.questions.length - 1) go(S.i + 1);
      else toast("This is the last question.");
    });
    els.mark.addEventListener("click", () => {
      S.marks[S.i] = !S.marks[S.i];
      renderQuestion();
      toast(S.marks[S.i] ? "Marked for review 📌" : "Unmarked");
    });
    els.bookmark.addEventListener("click", () => {
      const q = QUIZ.questions[S.i];
      const subjectMeta = SUBJECTS.find((s) => s.id === (q.subject || QUIZ.subject));
      const added = bookmarks.toggle({
        key: bmKey(),
        id: S.i + 1,
        q: q.q,
        correctText: q.options[q.correct] ?? "",
        explanation: q.explanation,
        reference: q.reference,
        subjectName: subjectMeta?.name || QUIZ.subjectName || "Quiz",
        topicName: q.topic || QUIZ.title,
        href: QUIZ.href || location.href,
      });
      els.bookmark.innerHTML = added ? "★ Bookmarked" : "☆ Bookmark";
      toast(added ? "Saved to bookmarks ★" : "Bookmark removed");
    });
    els.submit.addEventListener("click", confirmSubmit);

    // Restart: wipe the autosaved session and reload a fresh attempt.
    document.getElementById("resumeReset")?.addEventListener("click", () => {
      if (!confirm("Restart this quiz? Your saved answers for it will be cleared.")) return;
      HOA.db.remove("session:" + QUIZ.key);
      location.reload();
    });

    // ---- Keyboard navigation --------------------------------------------
    document.addEventListener("keydown", (e) => {
      if (e.target.matches("input, textarea, select")) return;
      if (e.key === "ArrowRight") go(S.i + 1);
      else if (e.key === "ArrowLeft") go(S.i - 1);
      else if (["1", "2", "3", "4"].includes(e.key)) {
        const idxNum = Number(e.key) - 1;
        if (idxNum < QUIZ.questions[S.i].options.length) choose(idxNum);
      } else if (e.key.toLowerCase() === "m") els.mark.click();
      else if (e.key.toLowerCase() === "s") els.skip.click();
      else if (e.key === "Enter") confirmSubmit();
    });
  }

  function confirmSubmit() {
    if (S.locked) { finish(); return; }
    const un = QUIZ.questions.length - attempted();
    const ov = document.createElement("div");
    ov.className = "lock-overlay";
    ov.innerHTML = `
      <div class="lock-box">
        <div class="lk-icon">📤</div>
        <h3>Submit quiz?</h3>
        <p class="muted mt-1">
          ${attempted()} answered${un ? `, <b>${un}</b> not answered` : ""}.
          You can still review before submitting.
        </p>
        <div class="btn-row mt-3" style="justify-content:center">
          <button class="btn" data-close>Keep working</button>
          <button class="btn btn-primary" data-confirm>Submit now</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector("[data-close]").onclick = () => ov.remove();
    ov.querySelector("[data-confirm]").onclick = () => { ov.remove(); S.locked = true; finish(); };
  }

  /* ============================================= 8. EMPTY / START ======= */
  function showEmpty(message, hint) {
    const top = document.getElementById("quizTop"); // no title / timers when empty
    if (top) top.classList.add("hidden");
    els.main.classList.add("hidden");
    els.empty.classList.remove("hidden");
    els.empty.innerHTML = `
      <div class="empty-state">
        <div class="es-icon">🗂️</div>
        <h3>${esc(message)}</h3>
        <p>${hint}</p>
        <div class="btn-row mt-3" style="justify-content:center">
          <a class="btn btn-primary" href="index.html">Browse subjects</a>
          <a class="btn btn-telegram" href="${site.telegram || "https://t.me/HouseOfAspirants"}"
             target="_blank" rel="noopener">Join Telegram</a>
        </div>
      </div>`;
  }

  QUIZ = await resolveQuiz();

  if (!QUIZ || !QUIZ.questions.length) {
    const hint =
      mode === "daily"
        ? `The Daily Challenge builds itself from your quiz files. Add questions under <code>questions/</code> to activate it.`
        : `Create a file like <code>questions/${QUIZ?.subject || "gk"}/your-topic.json</code>
           (start from <code>templates/topic-template.json</code>) and this page will load it instantly.`;
    showEmpty("No questions available yet.", hint);
    document.title = "No questions yet - House of Aspirants";
    return;
  }

  /* ---------------------------------------------------- Header contents - */
  els.title.textContent = QUIZ.title;
  els.sub.textContent = mode === "daily"
    ? "Daily Challenge"
    : `${QUIZ.subjectName || ""}${QUIZ.topicName && QUIZ.topicName !== QUIZ.title ? " · " + QUIZ.topicName : ""}`;
  HOA.seo({
    title: `${QUIZ.title} Quiz - House of Aspirants`,
    ogTitle: `${QUIZ.title} Quiz - House of Aspirants`,
    ogDescription: `${QUIZ.subjectName ? QUIZ.subjectName + " · " : ""}${QUIZ.questions.length} MCQs with instant results & answer review.`,
  });

  /* ------------------------------------------------- Resume saved session */
  const saved = HOA.db.get("session:" + QUIZ.key);
  const n = QUIZ.questions.length;
  S.answers = Array(n).fill(null);
  S.marks = Array(n).fill(false);
  S.visited = Array(n).fill(false);
  S.startedAt = Date.now();
  S.overallLeft = QUIZ.overall || n * QUIZ.defaultSeconds;

  if (saved && !saved.locked && Array.isArray(saved.answers) && saved.answers.length === n) {
    S.i = saved.i || 0;
    S.answers = saved.answers;
    S.marks = saved.marks;
    S.visited = saved.visited;
    S.startedAt = saved.startedAt || S.startedAt;
    S.overallLeft = saved.overallLeft ?? S.overallLeft;
    toast("Resumed your saved progress ✓");
  }

  wire();
  renderQuestion();
  startTimers();

  // Warn before losing an in-progress quiz.
  window.addEventListener("beforeunload", save);
})();
