/* ============================================================================
 * leaderboard.js | Leaderboard page
 * Reads through HOA.leaderboard, which is the single swap-point for a future
 * backend API (Firebase / Supabase / Node+Express).
 * ========================================================================== */
(() => {
  "use strict";
  const { esc } = HOA;
  const tbody = document.getElementById("leadBody");
  const empty = document.getElementById("leadEmpty");
  const tabs = document.querySelectorAll("[data-period]");
  let period = "today";

  /* A brand-new engine has no scores - never seed fake entries. */
  function render() {
    const rows = HOA.leaderboard.get(period);
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

  tabs.forEach((tab) =>
    tab.addEventListener("click", () => {
      tabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");
      period = tab.dataset.period;
      render();
    })
  );

  render();
  window.addEventListener("storage", render); // live update across tabs
})();
