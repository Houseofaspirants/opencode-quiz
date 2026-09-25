/* ============================================================================
 * leaderboard.js | Leaderboard page
 * Local attempts always work offline; signed-in students additionally see the
 * global Google-account board (Firestore, fetched through HOA.auth — the
 * single swap-point for the backend, see README §20).
 * ========================================================================== */
(() => {
  "use strict";
  const { esc } = HOA;
  const tbody = document.getElementById("leadBody");
  const empty = document.getElementById("leadEmpty");
  const tabs = document.querySelectorAll("[data-period]");
  let period = "today";
  let seq = 0; // stale-response guard for async cloud renders

  const DAY = 864e5;
  const periodStart = (p) =>
    p === "today" ? Date.now() - DAY : p === "week" ? Date.now() - 7 * DAY : 0;

  /* A brand-new engine has no scores - never seed fake entries. */
  function paint(rows) {
    if (!rows.length) {
      tbody.innerHTML = "";
      empty.classList.remove("hidden");
      return;
    }
    empty.classList.add("hidden");
    tbody.innerHTML = rows
      .slice(0, 50)
      .map((r, i) => `
        <tr>
          <td><span class="rank-badge ${i < 3 ? `r${i + 1}` : ""}">${i + 1}</span></td>
          <td>${esc(r.name || "Anonymous")} ${r.me ? '<span class="badge badge-muted">You</span>' : ""}</td>
          <td>${esc(r.quiz || "Quiz")}</td>
          <td><b>${r.correct}/${r.total}</b></td>
          <td>${r.percent}%</td>
          <td class="muted text-sm">${new Date(r.at).toLocaleDateString("en-IN")}</td>
        </tr>`)
      .join("");
  }

  async function render() {
    const me = ++seq;
    let rows = null;
    if (HOA.auth && HOA.auth.cloudEnabled()) {
      try {
        const all = await HOA.auth.fetchScores();
        if (me !== seq) return; // a newer render won the race
        const start = periodStart(period);
        rows = all
          .filter((r) => !start || (r.at || 0) >= start)
          .slice(0, 50)
          .map((r) => ({ ...r, me: HOA.auth.isMe(r.uid) }));
      } catch (e) {
        console.warn("[leaderboard] global board unavailable, using local:", e && e.message);
        if (me !== seq) return;
      }
    }
    if (!rows) rows = HOA.leaderboard.get(period);
    paint(rows);
  }

  tabs.forEach((tab) =>
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      period = tab.dataset.period;
      render();
    })
  );

  (HOA.auth ? HOA.auth.ready : Promise.resolve()).then(render);
  window.addEventListener("storage", render); // live update across tabs
})();
