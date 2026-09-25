/* ============================================================================
 * dashboard.js | Progress tracking + achievements
 * All values are derived from quizzes the student actually attempted.
 * Renders after HOA.auth.ready so signed-in students see their Google-account
 * stats once any cloud merge has landed (instant when signed out).
 * ========================================================================== */
(() => {
  "use strict";
  const whenReady = HOA.auth ? HOA.auth.ready : Promise.resolve();

  whenReady.then(() => {
    const p = HOA.progress.get();
    const acc = p.answered ? Math.round((p.correct / p.answered) * 100) : 0;

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    set("dashQuizzes", p.quizzes);
    // Average score = mean of the last 100 quiz percentages.
    const hist = p.history || [];
    set(
      "dashAvg",
      hist.length
        ? Math.round(hist.reduce((a, b) => a + b, 0) / hist.length) + "%"
        : "—"
    );
    set("dashAccuracy", p.answered ? acc + "%" : "—");
    set("dashTime", p.studySeconds ? HOA.fmtTime(p.studySeconds) : "—");
    set("dashStreak", HOA.progress.streak() + " day" + (HOA.progress.streak() === 1 ? "" : "s"));
    set("dashWeekly", HOA.progress.weeklyStreak() + " week" + (HOA.progress.weeklyStreak() === 1 ? "" : "s"));
    set("dashBest", p.best ? p.best + "%" : "—");

    const badges = HOA.achievements();
    const grid = document.getElementById("badgeGrid");
    if (grid) {
      grid.innerHTML = badges
        .map(
          (b) => `
      <div class="badge-card ${b.got ? "earned" : ""}">
        <div class="bd-emoji">${b.icon}</div>
        <h3>${b.name}</h3>
        <p>${b.desc}</p>
        ${b.got ? '<span class="badge badge-success mt-1">Earned</span>' : ""}
      </div>`
        )
        .join("");
    }

    /* --------------------------------------------- extra page controls ---- */
    // NOTE: lives here (deferred) rather than an inline <script>, because inline
    // scripts execute before core.js has defined HOA.
    const bmStat = document.getElementById("bmStat");
    if (bmStat) bmStat.textContent = String(HOA.bookmarks.all().length);

    document.getElementById("resetProgress")?.addEventListener("click", () => {
      if (confirm("Reset all progress, streaks and badges on this device?")) {
        HOA.db.remove("progress");
        HOA.db.remove("scores");
        HOA.db.remove("submittedResults");
        location.reload();
      }
    });
  });
})();
