/* ============================================================================
 * result.js | Result page + full answer review
 * Reads HOA.db "lastResult" written by quiz.js.
 * ========================================================================== */
(() => {
  "use strict";
  const { esc, fmtTime } = HOA;
  const r = HOA.db.get("lastResult");

  const $ = (id) => document.getElementById(id);

  if (!r) {
    $("resultBody").innerHTML = `
      <div class="empty-state">
        <div class="es-icon">🧾</div>
        <h3>No result to show yet.</h3>
        <p>Finish a quiz and your result — with a full answer review — will appear here.</p>
        <p class="mt-2"><a class="btn btn-primary" href="index.html">Start a quiz</a></p>
      </div>`;
    $("resultHero").classList.add("hidden");
    return;
  }

  /* ---------------------------------------------------- 1. HERO SUMMARY - */
  document.title = `Result: ${r.title} - House of Aspirants`;
  $("resTitle").textContent = r.title;
  $("resSub").textContent = `${r.subjectName || "Quiz"}${
    r.at ? " · " + new Date(r.at).toLocaleString("en-IN") : ""
  }`;

  const ring = $("scoreRing");
  ring.style.setProperty("--pct", r.percent);
  $("scoreVal").textContent = r.percent + "%";

  const verdict = $("verdict");
  verdict.textContent = r.passed ? "🎉 Passed" : "💪 Keep Practicing";
  verdict.className = "verdict " + (r.passed ? "pass" : "fail");

  $("perfMsg").innerHTML = performanceMessage(r);

  /* -------------------------------------------------- 2. STAT CARD GRID - */
  const cards = [
    { v: r.total, l: "Total Questions", c: "" },
    { v: r.attempted, l: "Attempted", c: "" },
    { v: r.correct, l: "Correct", c: "ok" },
    { v: r.wrong, l: "Wrong", c: "bad" },
    { v: r.skipped, l: "Skipped", c: "warn" },
    { v: r.accuracy + "%", l: "Accuracy", c: r.accuracy >= 60 ? "ok" : "bad" },
    { v: r.percent + "%", l: "Percentage", c: r.percent >= 40 ? "ok" : "bad" },
    { v: `${r.score}/${r.total}`, l: "Final Score", c: "" },
    { v: fmtTime(r.seconds), l: "Time Taken", c: "" },
    { v: r.passed ? "PASS" : "FAIL", l: `Pass ≥ ${r.passLine}%`, c: r.passed ? "ok" : "bad" },
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
  }
  const rows = HOA.leaderboard.get("all");
  const myIndex = rows.findIndex((x) => x.at === r.at && x.me);
  $("rankVal").textContent = myIndex >= 0 ? `#${myIndex + 1}` : "—";
  $("rankLab").textContent = `of ${rows.length} attempts`;

  /* -------------------------------------- 4. SUBJECT-WISE PERFORMANCE ---- */
  const bySubject = groupBy(r.review, (x) => x.subject || r.subjectName || "Mixed");
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
    ? weak.map((t) => `<span class="area-chip weak">Weak: ${esc(t)}</span>`).join("")
    : `<span class="muted text-sm">No weak areas detected — solid work! 🎯</span>`;
  $("strongWrap").innerHTML = strong.length
    ? strong.map((t) => `<span class="area-chip strong">Strong: ${esc(t)}</span>`).join("")
    : `<span class="muted text-sm">Attempt more tagged questions to reveal strong areas.</span>`;

  /* ---------------------------------------------------- 6. ANSWER REVIEW - */
  const reviewWrap = $("reviewList");
  let filter = "all";

  function renderReview() {
    const items = r.review.filter((x) => filter === "all" || x.status === filter);
    if (!items.length) {
      reviewWrap.innerHTML = `<div class="empty-state"><div class="es-icon">🔍</div>
        <h3>Nothing in this filter</h3><p>Pick another filter above.</p></div>`;
      return;
    }
    reviewWrap.innerHTML = items
      .map((x) => {
        const userText =
          x.answer === null || x.answer === undefined
            ? "Not answered (skipped)"
            : x.options[x.answer] ?? "—";
        const correctText = x.options[x.correct] ?? "—";
        const badge =
          x.status === "correct"
            ? '<span class="badge badge-success">Correct</span>'
            : x.status === "wrong"
            ? '<span class="badge badge-danger">Wrong</span>'
            : '<span class="badge badge-muted">Skipped</span>';

        return `
        <article class="review-item ${x.status}">
          <div class="review-head">
            <span class="q-number">${x.id}</span>
            <span class="review-q">${esc(x.q)}</span>
            ${badge}
          </div>
          <div class="review-ans">
            <div class="ans-line ok">
              <span class="tag">Correct</span><span>${esc(correctText)}</span>
            </div>
            ${
              x.answer !== null && x.answer !== undefined
                ? `<div class="ans-line ${x.status === "correct" ? "ok" : "bad"}">
                    <span class="tag">Your answer</span><span>${esc(userText)}</span>
                   </div>`
                : ""
            }
          </div>
          ${
            x.explanation
              ? `<div class="review-note"><b>Explanation:</b> ${esc(x.explanation)}</div>`
              : ""
          }
          ${
            x.reference
              ? `<p class="review-ref"><b>Reference:</b> ${esc(x.reference)}</p>`
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
    const map = {
      gk: "General Knowledge", quant: "Quantitative Aptitude",
      reasoning: "Reasoning", punjabi: "Punjabi", english: "English",
      computer: "Computer", "current-affairs": "Current Affairs", mixed: "Mixed Subjects",
    };
    return map[id] || id;
  }
  function performanceMessage(res) {
    const p = res.percent;
    if (p >= 90) return "Outstanding! You are exam-ready for this topic. 🏆";
    if (p >= 75) return "Excellent work — a little more revision and you'll ace it. 🌟";
    if (p >= 60) return "Good attempt. Focus on the weak areas listed below. 👍";
    if (p >= 40) return "Average — revise the explanations and try again. 📚";
    return "Don't give up. Read each explanation carefully and retry. 💪";
  }

  /* ------------------------------------------- 8. TELEGRAM CTA (post quiz) */
  const tgLink = (HOA.db.get("indexCache")?.site?.telegram) ||
    "https://t.me/HouseOfAspirant";
  document.querySelectorAll("[data-telegram]").forEach((a) => (a.href = tgLink));

  /* -------------------------------------------------- 9. RETAKE BUTTON --
   * Opens the same quiz again with a clean session (fresh attempt). */
  document.getElementById("retryBtn")?.addEventListener("click", () => {
    HOA.db.remove("session:" + (r.href || "").split("topic=")[1]); // clear autosave
    location.href = r.href || "index.html";
  });
})();
