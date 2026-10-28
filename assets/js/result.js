/* ============================================================================
 * result.js | Result page + full answer review
 * Reads HOA.db "lastResult" written by quiz.js.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc, fmtTime } = HOA;
  const r = HOA.db.get("lastResult");

  const $ = (id) => document.getElementById(id);
  /* The results page has two editions: result.html (English) and
     pa/result.html (Punjabi, data-page-lang="pa"). Every word on it follows
     the edition being viewed, whichever language the quiz was taken in. */
  const lang = HOA.lang && HOA.lang.get() === "pa" ? "pa" : "en";
  const say = (pa, en) => (lang === "pa" ? pa : en);
  const SUBJECT_PA = {
    gk: "ਜਨਰਲ ਨਾਲੇਜ", quant: "ਗਣਿਤ", reasoning: "ਰੀਜ਼ਨਿੰਗ", punjabi: "ਪੰਜਾਬੀ",
    english: "ਅੰਗਰੇਜ਼ੀ", computer: "ਕੰਪਿਊਟਰ", "current-affairs": "ਕਰੰਟ ਅਫੇਅਰਜ਼",
    mixed: "ਮਿਲੇ-ਜੁਲੇ ਵਿਸ਼ੇ",
  };

  if (!r) {
    $("resultBody").innerHTML = `
      <div class="empty-state">
        <div class="es-icon">🧾</div>
        <h2 style="font-size:clamp(1.1rem,2.2vw,1.35rem);margin-bottom:8px">${say("ਹਾਲੇ ਕੋਈ ਨਤੀਜਾ ਨਹੀਂ।", "No result to show yet.")}</h2>
        <p>${say("ਕੋਈ ਕੁਇਜ਼ ਪੂਰਾ ਕਰੋ — ਨਤੀਜਾ ਅਤੇ ਹਰ ਉੱਤਰ ਦਾ ਰਿਵਿਊ ਇੱਥੇ ਦਿਸੇਗਾ।",
          "Finish a quiz and your result — with a full answer review — will appear here.")}</p>
        <p class="mt-2"><a class="btn btn-primary" href="./">${say("ਕੁਇਜ਼ ਸ਼ੁਰੂ ਕਰੋ", "Start a quiz")}</a></p>
      </div>`;
    $("resultHero").classList.add("hidden");
    return;
  }

  /* ------------------------------------- 0. TEXT IN THIS PAGE'S LANGUAGE -
     A topic result stores its set (subject + topicId) and the answers as
     indices. Reload the question file of this edition and rebuild the title
     and review text from it. Only when it lines up question for question
     (same count, same correct option): otherwise, or offline, the text
     stored at submit time stays. */
  await (async () => {
    if (!r.topicId || !r.subject || !Array.isArray(r.review)) return;
    try {
      const idx = await HOA.loadIndex();
      const subj = (idx.subjects || []).find((x) => x.id === r.subject);
      const t = subj && subj.topics.find((x) => x.id === r.topicId);
      if (!t) return;
      const v = t.variants || {};
      const file = v[lang] || v.en || t.file;
      const data = await HOA.loadQuestions(file);
      const qs = data.questions;
      const meta = data.meta || {};
      const fits = qs.length === r.review.length &&
        qs.every((q, i) => q.correct === r.review[i].correct &&
                           q.options.length === r.review[i].options.length);
      if (!fits) return;
      r.review = r.review.map((x, i) => ({
        ...x, q: qs[i].q, options: qs[i].options,
        explanation: qs[i].explanation, reference: qs[i].reference,
      }));
      // Named the way the edition's quiz page names it (see quiz.js).
      r.title = lang !== "pa" ? t.name
        : meta.chapter && meta.chapter.title && meta.part
          ? `${meta.chapter.title} - ਭਾਗ ${meta.part}`
          : String((t.titles || {}).pa || t.name).replace(/\bPart\s*(\d+)\s*$/, "ਭਾਗ $1");
      r.subjectName = lang === "pa" ? SUBJECT_PA[subj.id] || subj.name : subj.name;
    } catch { /* keep the stored text */ }
  })();

  /* ---------------------------------------------------- 1. HERO SUMMARY - */
  document.title = say(`ਨਤੀਜਾ: ${r.title} - House of Aspirants`, `Result: ${r.title} - House of Aspirants`);
  $("resTitle").textContent = r.title;
  $("resSub").textContent = `${r.subjectName || say("ਕੁਇਜ਼", "Quiz")}${
    r.at ? " · " + new Date(r.at).toLocaleString(say("pa-IN", "en-IN")) : ""
  }`;

  const ring = $("scoreRing");
  ring.style.setProperty("--pct", r.percent);
  $("scoreVal").textContent = r.percent + "%";

  const verdict = $("verdict");
  verdict.textContent = r.passed ? say("🎉 ਪਾਸ", "🎉 Passed") : say("💪 ਅਭਿਆਸ ਜਾਰੀ ਰੱਖੋ", "💪 Keep Practicing");
  verdict.className = "verdict " + (r.passed ? "pass" : "fail");

  $("perfMsg").innerHTML = performanceMessage(r);

  /* -------------------------------------------------- 2. STAT CARD GRID - */
  const cards = [
    { v: r.total, l: say("ਕੁੱਲ ਸਵਾਲ", "Total Questions"), c: "" },
    { v: r.attempted, l: say("ਹੱਲ ਕੀਤੇ", "Attempted"), c: "" },
    { v: r.correct, l: say("ਸਹੀ", "Correct"), c: "ok" },
    { v: r.wrong, l: say("ਗਲਤ", "Wrong"), c: "bad" },
    { v: r.skipped, l: say("ਛੱਡੇ", "Skipped"), c: "warn" },
    { v: r.accuracy + "%", l: say("ਸ਼ੁੱਧਤਾ", "Accuracy"), c: r.accuracy >= 60 ? "ok" : "bad" },
    { v: r.percent + "%", l: say("ਪ੍ਰਤੀਸ਼ਤ", "Percentage"), c: r.percent >= 40 ? "ok" : "bad" },
    { v: `${r.score}/${r.total}`, l: say("ਅੰਤਿਮ ਸਕੋਰ", "Final Score"), c: "" },
    { v: fmtTime(r.seconds), l: say("ਲੱਗਿਆ ਸਮਾਂ", "Time Taken"), c: "" },
    { v: r.passed ? say("ਪਾਸ", "PASS") : say("ਫੇਲ੍ਹ", "FAIL"), l: say(`ਪਾਸ ≥ ${r.passLine}%`, `Pass ≥ ${r.passLine}%`), c: r.passed ? "ok" : "bad" },
  ];
  $("statGrid").innerHTML = cards
    .map(
      (c) => `<div class="rs-card ${c.c}">
        <div class="rs-val">${esc(String(c.v))}</div>
        <div class="rs-lab">${c.l}</div>
      </div>`
    )
    .join("");

  /* -------------------------------------------------- 3. RANK (local) ---- */
  // Submit this attempt exactly once (guarded by unique result id).
  const submitted = HOA.db.get("submittedResults", []);
  if (!submitted.includes(r.id)) {
    HOA.leaderboard.submit({
      name: "You", me: true, quiz: r.title,
      correct: r.correct, total: r.total, percent: r.percent, at: r.at,
    });
    HOA.db.set("submittedResults", [...submitted, r.id].slice(-50));
    // Cloud sync — saves the attempt and updates the student's public
    // leaderboard row. No-op (null) unless signed in with Google.
    if (HOA.auth) {
      Promise.resolve(HOA.auth.ready)
        .then(() => HOA.auth.syncResult(r))
        .then(showBoardResult)
        .catch(() => {});
    }
  }
  showJoinPrompt();
  const rows = HOA.leaderboard.get("all");
  const myIndex = rows.findIndex((x) => x.at === r.at && x.me);
  $("rankVal").textContent = myIndex >= 0 ? `#${myIndex + 1}` : "—";
  $("rankLab").textContent = say(`${rows.length} ਕੋਸ਼ਿਸ਼ਾਂ ਵਿੱਚੋਂ`, `of ${rows.length} attempts`);

  /** Signed-in: replace the device-only rank with live leaderboard points. */
  function showBoardResult(res) {
    if (!res) return;
    $("rankVal").textContent = res.gained > 0 ? `+${res.gained}` : `${res.today || 0}`;
    $("rankLab").innerHTML = res.gained > 0
      ? say(`ਅੰਕ ਜੁੜੇ · <a href="leaderboard">ਅੱਜ ਲੀਡਰਬੋਰਡ ਉੱਤੇ ${res.today} →</a>`,
            `points added · <a href="leaderboard">${res.today} today on the leaderboard →</a>`)
      : say(`ਅੱਜ ਦੇ ਅੰਕ · <a href="leaderboard">ਇਸ ਸੈੱਟ ਦਾ ਵਧੀਆ ਸਕੋਰ ਪਹਿਲਾਂ ਗਿਣਿਆ ਜਾ ਚੁੱਕਾ ਹੈ →</a>`,
            `points today · <a href="leaderboard">best score on this set already counted →</a>`);
  }

  /** Signed-out: one quiet line inviting the student onto the live board. */
  function showJoinPrompt() {
    if (!HOA.auth) return;
    Promise.resolve(HOA.auth.ready).then(() => {
      if (HOA.auth.mode !== "firebase" || HOA.auth.cloudEnabled()) return;
      const lab = $("rankLab");
      lab.innerHTML = say(`ਇਸ ਡਿਵਾਈਸ ਉੱਤੇ · <a href="#" id="joinBoard">ਲਾਈਵ ਲੀਡਰਬੋਰਡ ਲਈ ਸਾਈਨ ਇਨ ਕਰੋ</a>`,
        `on this device · <a href="#" id="joinBoard">Sign in to join the live leaderboard</a>`);
      $("joinBoard").addEventListener("click", (e) => {
        e.preventDefault();
        HOA.auth.signIn().then((ok) => {
          if (!ok) return;
          // The attempt just finished counts too.
          HOA.auth.syncResult(r).then(showBoardResult);
        });
      });
    });
  }

  /* -------------------------------------- 4. SUBJECT-WISE PERFORMANCE ---- */
  const bySubject = groupBy(r.review, (x) => x.subject || r.subject || "mixed");
  $("perfList").innerHTML = Object.entries(bySubject)
    .map(([name, items]) => {
      const ok = items.filter((i) => i.status === "correct").length;
      const pct = Math.round((ok / items.length) * 100);
      return `<div class="perf-row">
        <div class="pr-head"><span>${esc(prettySubject(name))}</span>
          <span>${ok}/${items.length} · ${pct}%</span></div>
        <div class="pr-track"><div class="pr-fill" style="width:0%" data-w="${pct}"></div></div>
      </div>`;
    })
    .join("");
  requestAnimationFrame(() =>
    $("perfList").querySelectorAll("[data-w]").forEach(
      (el) => (el.style.width = el.dataset.w + "%")
    )
  );

  /* -------------------------------------------- 5. WEAK / STRONG AREAS --- */
  const byTopic = groupBy(
    r.review.filter((x) => x.topic),
    (x) => x.topic
  );
  const weak = [], strong = [];
  Object.entries(byTopic).forEach(([t, items]) => {
    const pct = (items.filter((i) => i.status === "correct").length / items.length) * 100;
    if (pct < 50) weak.push(t);
    else if (pct >= 80) strong.push(t);
  });
  $("weakWrap").innerHTML = weak.length
    ? weak.map((t) => `<span class="area-chip weak">${say("ਕਮਜ਼ੋਰ", "Weak")}: ${esc(t)}</span>`).join("")
    : `<span class="muted text-sm">${say("ਕੋਈ ਕਮਜ਼ੋਰ ਹਿੱਸਾ ਨਹੀਂ — ਸ਼ਾਬਾਸ਼! 🎯", "No weak areas detected — solid work! 🎯")}</span>`;
  $("strongWrap").innerHTML = strong.length
    ? strong.map((t) => `<span class="area-chip strong">${say("ਮਜ਼ਬੂਤ", "Strong")}: ${esc(t)}</span>`).join("")
    : `<span class="muted text-sm">${say("ਮਜ਼ਬੂਤ ਹਿੱਸੇ ਵੇਖਣ ਲਈ ਹੋਰ ਟੈਗ ਵਾਲੇ ਸਵਾਲ ਹੱਲ ਕਰੋ।", "Attempt more tagged questions to reveal strong areas.")}</span>`;

  /* ---------------------------------------------------- 6. ANSWER REVIEW - */
  const reviewWrap = $("reviewList");
  let filter = "all";

  function renderReview() {
    const items = r.review.filter((x) => filter === "all" || x.status === filter);
    if (!items.length) {
      reviewWrap.innerHTML = `<div class="empty-state"><div class="es-icon">🔍</div>
        <h3>${say("ਇਸ ਫ਼ਿਲਟਰ ਵਿੱਚ ਕੁਝ ਨਹੀਂ", "Nothing in this filter")}</h3><p>${say("ਉੱਪਰੋਂ ਹੋਰ ਫ਼ਿਲਟਰ ਚੁਣੋ।", "Pick another filter above.")}</p></div>`;
      return;
    }
    reviewWrap.innerHTML = items
      .map((x) => {
        const userText =
          x.answer === null || x.answer === undefined
            ? say("ਉੱਤਰ ਨਹੀਂ ਦਿੱਤਾ (ਛੱਡਿਆ)", "Not answered (skipped)")
            : x.options[x.answer] ?? "—";
        const correctText = x.options[x.correct] ?? "—";
        const badge =
          x.status === "correct"
            ? `<span class="badge badge-success">${say("ਸਹੀ", "Correct")}</span>`
            : x.status === "wrong"
            ? `<span class="badge badge-danger">${say("ਗਲਤ", "Wrong")}</span>`
            : `<span class="badge badge-muted">${say("ਛੱਡਿਆ", "Skipped")}</span>`;

        return `
        <article class="review-item ${x.status}">
          <div class="review-head">
            <span class="q-number">${x.id}</span>
            <span class="review-q">${esc(x.q)}</span>
            ${badge}
          </div>
          ${x.data && window.HOA_DI && window.HOA_DI.has(x.data)
            ? `<div class="q-data">${window.HOA_DI.html(x.data, reviewWrap.clientWidth - 40)}</div>` : ""}
          <div class="review-ans">
            <div class="ans-line ok">
              <span class="tag">${say("ਸਹੀ ਉੱਤਰ", "Correct")}</span><span>${esc(correctText)}</span>
            </div>
            ${
              x.answer !== null && x.answer !== undefined
                ? `<div class="ans-line ${x.status === "correct" ? "ok" : "bad"}">
                    <span class="tag">${say("ਤੁਹਾਡਾ ਉੱਤਰ", "Your answer")}</span><span>${esc(userText)}</span>
                   </div>`
                : ""
            }
          </div>
          ${
            x.explanation
              ? `<div class="review-note"><b>${say("ਵਿਆਖਿਆ", "Explanation")}:</b> ${esc(x.explanation)}</div>`
              : ""
          }
          ${
            x.reference
              ? `<p class="review-ref"><b>${say("ਹਵਾਲਾ", "Reference")}:</b> ${esc(x.reference)}</p>`
              : ""
          }
        </article>`;
      })
      .join("");
  }

  document.querySelectorAll("[data-filter]").forEach((chip) =>
    chip.addEventListener("click", () => {
      document.querySelectorAll("[data-filter]").forEach((c) => c.classList.remove("active"));
      chip.classList.add("active");
      filter = chip.dataset.filter;
      renderReview();
    })
  );
  renderReview();

  /* ------------------------------------------------------- 7. UTILITIES - */
  function groupBy(arr, fn) {
    return arr.reduce((acc, item) => {
      const k = fn(item) || "General";
      (acc[k] = acc[k] || []).push(item);
      return acc;
    }, {});
  }
  function prettySubject(id) {
    if (lang === "pa" && SUBJECT_PA[id]) return SUBJECT_PA[id];
    const map = {
      gk: "General Knowledge", quant: "Quantitative Aptitude",
      reasoning: "Reasoning", punjabi: "Punjabi", english: "English",
      computer: "Computer", "current-affairs": "Current Affairs", mixed: "Mixed Subjects",
    };
    return map[id] || id;
  }
  function performanceMessage(res) {
    const p = res.percent;
    if (p >= 90) return say("ਸ਼ਾਨਦਾਰ! ਇਸ ਵਿਸ਼ੇ ਲਈ ਤੁਸੀਂ ਪ੍ਰੀਖਿਆ ਲਈ ਤਿਆਰ ਹੋ। 🏆", "Outstanding! You are exam-ready for this topic. 🏆");
    if (p >= 75) return say("ਬਹੁਤ ਵਧੀਆ — ਥੋੜ੍ਹੀ ਹੋਰ ਦੁਹਰਾਈ ਨਾਲ ਪੂਰੇ ਅੰਕ। 🌟", "Excellent work — a little more revision and you'll ace it. 🌟");
    if (p >= 60) return say("ਚੰਗੀ ਕੋਸ਼ਿਸ਼। ਹੇਠਾਂ ਦਿੱਤੇ ਕਮਜ਼ੋਰ ਹਿੱਸਿਆਂ ਉੱਤੇ ਧਿਆਨ ਦਿਓ। 👍", "Good attempt. Focus on the weak areas listed below. 👍");
    if (p >= 40) return say("ਠੀਕ-ਠਾਕ — ਵਿਆਖਿਆਵਾਂ ਦੁਹਰਾ ਕੇ ਫਿਰ ਕੋਸ਼ਿਸ਼ ਕਰੋ। 📚", "Average — revise the explanations and try again. 📚");
    return say("ਹਿੰਮਤ ਨਾ ਹਾਰੋ। ਹਰ ਵਿਆਖਿਆ ਧਿਆਨ ਨਾਲ ਪੜ੍ਹ ਕੇ ਫਿਰ ਕੋਸ਼ਿਸ਼ ਕਰੋ। 💪", "Don't give up. Read each explanation carefully and retry. 💪");
  }

  /* ------------------------------------------- 8. TELEGRAM CTA (post quiz) */
  const tgLink = (HOA.db.get("indexCache")?.site?.telegram) ||
    "https://t.me/HouseOfAspirant";
  document.querySelectorAll("[data-telegram]").forEach((a) => (a.href = tgLink));

  /* ------------------------------------------- 10. SHARE MY SCORE ------
   * A 1080x1080 card drawn on a canvas in the site's navy-and-gold style:
   * the quiz, the score and the link. Phones get the native share sheet
   * (WhatsApp, Instagram, Telegram) with the image attached; a browser that
   * cannot share files gets a preview with Download + WhatsApp buttons.
   * Every share brings a new student to the quiz and the name to search. */
  const shareBtn = $("shareScore");
  const quizUrl = (() => {
    try {
      const ed = r.editions && (r.lang === "pa" ? r.editions.pa : r.editions.en);
      const u = new URL("/" + String(ed || r.href || "index.html").replace(/^\//, ""), location.origin);
      u.searchParams.set("utm_source", "score_card");
      return u.toString();
    } catch { return location.origin; }
  })();
  const shareText = say(
    `ਮੈਂ House of Aspirants ਉੱਤੇ "${r.title}" ਵਿੱਚ ${r.score}/${r.total} (${r.percent}%) ਅੰਕ ਲਏ। ` +
    `ਕੀ ਤੁਸੀਂ ਇਸ ਤੋਂ ਵੱਧ ਲੈ ਸਕਦੇ ਹੋ? ${quizUrl}`,
    `I scored ${r.score}/${r.total} (${r.percent}%) in "${r.title}" on House of Aspirants. ` +
    `Can you beat me? ${quizUrl}`);

  function wrapLines(ctx, text, maxW, maxLines) {
    const words = String(text).split(/\s+/);
    const lines = [];
    let cur = "";
    for (const w of words) {
      const t = cur ? cur + " " + w : w;
      if (ctx.measureText(t).width <= maxW || !cur) cur = t;
      else { lines.push(cur); cur = w; }
    }
    if (cur) lines.push(cur);
    if (lines.length > maxLines) {
      lines.length = maxLines;
      lines[maxLines - 1] = lines[maxLines - 1].replace(/\s*\S*$/, "") + "…";
    }
    return lines;
  }

  function loadImg(src) {
    return new Promise((res) => {
      const im = new Image();
      im.onload = () => res(im);
      im.onerror = () => res(null);
      im.src = src;
    });
  }

  async function drawScoreCard() {
    const S = 1080;
    const c = document.createElement("canvas");
    c.width = S; c.height = S;
    const x = c.getContext("2d");
    const FONT = 'system-ui, -apple-system, "Segoe UI", "Noto Sans Gurmukhi", "Noto Sans", sans-serif';
    // background + glow
    x.fillStyle = "#0b0f19"; x.fillRect(0, 0, S, S);
    const g = x.createRadialGradient(820, 180, 40, 820, 180, 720);
    g.addColorStop(0, "rgba(37,74,170,.85)"); g.addColorStop(1, "rgba(11,15,25,0)");
    x.fillStyle = g; x.fillRect(0, 0, S, S);
    // brand line
    x.fillStyle = "#f5c040"; x.fillRect(80, 106, 52, 4);
    x.font = `700 30px ${FONT}`; x.textBaseline = "alphabetic";
    x.fillText("HOUSE OF ASPIRANTS", 150, 118);
    // logo tile
    const logo = await loadImg("assets/img/logo-mark.png");
    if (logo) {
      x.save();
      const lx = S - 80 - 170, ly = 64, ls = 170, rr = 26;
      x.beginPath();
      x.roundRect ? x.roundRect(lx, ly, ls, ls, rr) : x.rect(lx, ly, ls, ls);
      x.clip(); x.drawImage(logo, lx, ly, ls, ls); x.restore();
    }
    // subject + quiz title
    x.fillStyle = "#a8b2cc"; x.font = `600 32px ${FONT}`;
    x.fillText(String(r.subjectName || "Quiz").toUpperCase().slice(0, 40), 80, 300);
    x.fillStyle = "#ffffff"; x.font = `800 58px ${FONT}`;
    let y = 380;
    for (const line of wrapLines(x, r.title || "Quiz", S - 160, 3)) {
      x.fillText(line, 80, y); y += 72;
    }
    // score
    y += 40;
    x.fillStyle = "#f5c040";
    const big = `${r.score}/${r.total}`;
    let bigSize = 200;                       // 100/100 must still leave room for the %
    do { x.font = `800 ${bigSize}px ${FONT}`; bigSize -= 10; }
    while (x.measureText(big).width > 560 && bigSize > 90);
    x.fillText(big, 72, y + 160);
    const bw = x.measureText(big).width;
    x.fillStyle = "#ffffff"; x.font = `800 64px ${FONT}`;
    x.fillText(`${r.percent}%`, 72 + bw + 36, y + 90);
    x.fillStyle = r.passed ? "#4ade80" : "#fbbf24"; x.font = `700 36px ${FONT}`;
    x.fillText(r.passed ? "PASSED ✓" : "KEEP GOING", 72 + bw + 36, y + 150);
    // challenge + footer
    x.fillStyle = "#ffffff"; x.font = `700 44px ${FONT}`;
    x.fillText("Can you beat my score?", 80, 900);
    x.fillStyle = "#344060"; x.fillRect(80, 950, S - 160, 2);
    x.fillStyle = "#f5c040"; x.font = `700 36px ${FONT}`;
    x.fillText("houseofaspirants.in", 80, 1010);
    x.fillStyle = "#a8b2cc"; x.font = `600 30px ${FONT}`;
    const tail = "Free MCQs · Punjab exams";
    x.fillText(tail, S - 80 - x.measureText(tail).width, 1010);
    return new Promise((res) => c.toBlob((b) => res(b), "image/png"));
  }

  function showSharePreview(blob) {
    const url = URL.createObjectURL(blob);
    const ov = document.createElement("div");
    ov.className = "lock-overlay";
    ov.innerHTML = `
      <div class="lock-box" style="max-width:420px">
        <img src="${url}" alt="Your score card" width="360" height="360"
             style="width:100%;height:auto;border-radius:14px;display:block">
        <div class="btn-row mt-3" style="justify-content:center">
          <a class="btn btn-primary" download="house-of-aspirants-score.png" href="${url}">⬇ Download</a>
          <a class="btn" target="_blank" rel="noopener"
             href="https://wa.me/?text=${encodeURIComponent(shareText)}">WhatsApp</a>
          <button class="btn" data-close>Close</button>
        </div>
      </div>`;
    document.body.appendChild(ov);
    ov.querySelector("[data-close]").addEventListener("click", () => {
      ov.remove(); URL.revokeObjectURL(url);
    });
  }

  if (shareBtn) {
    shareBtn.hidden = false;
    shareBtn.addEventListener("click", async () => {
      shareBtn.disabled = true;
      try {
        const blob = await drawScoreCard();
        if (!blob) throw new Error("no image");
        const file = new File([blob], "house-of-aspirants-score.png", { type: "image/png" });
        if (navigator.canShare && navigator.canShare({ files: [file] })) {
          HOA.analytics?.track?.("share", { method: "score_card_native", page: "result" });
          await navigator.share({ files: [file], text: shareText, title: "My score" });
        } else {
          HOA.analytics?.track?.("share", { method: "score_card_preview", page: "result" });
          showSharePreview(blob);
        }
      } catch (err) {
        if (!(err && err.name === "AbortError")) {
          try { await navigator.clipboard.writeText(shareText); HOA.toast?.("Score text copied - paste it anywhere"); }
          catch { /* nothing else to try */ }
        }
      } finally {
        shareBtn.disabled = false;
      }
    });
  }

  /* -------------------------------------------------- 9. RETAKE BUTTON --
   * Opens the same quiz again with a clean session (fresh attempt), in the
   * edition it was taken in. Results saved before editions existed carry
   * only the classic quiz.html?subject=… href, which still works. */
  const retakeHref =
    (r.editions && (r.lang === "pa" ? r.editions.pa : r.editions.en)) ||
    r.href || "index.html";
  document.getElementById("retryBtn")?.addEventListener("click", () => {
    if (r.key) HOA.db.remove("session:" + r.key); // clear autosave
    location.href = retakeHref;
  });
})();
