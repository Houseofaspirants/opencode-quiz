// @ts-check
/* ============================================================================
 * pyq.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * pyq.html - every previous year paper, arranged by who conducts the exam.
 *
 * One source: data/pyq-manifest.json (written by scripts/pyq_collection.py).
 * Each exam folder under content/previous-year-questions/<exam>/ is one card,
 * filed under its organisation (Punjab Police, PSSSB, PPSC), with the years on
 * record, a count of papers and answer keys, a link to that exam's year-by-year
 * table (pyq/<slug>/index.html) and a direct download of its newest paper.
 * A new folder or a new PDF shows up here on the next publish - nothing on
 * this page is written by hand.
 * ========================================================================== */
(() => {
  "use strict";
  const grid = document.getElementById("pyqPapers");
  if (!grid) return;
  const search = /** @type {HTMLInputElement|null} */ (document.getElementById("pyqSearch"));
  const chipsBox = document.getElementById("pyqOrgs");
  const stats = document.getElementById("pyqStats");

  /** @param {unknown} s */
  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c));

  const ORDER = ["Punjab Police", "PSSSB", "PPSC"];
  /** @type {Record<string, string>} */
  const ORG_NAME = {
    "Punjab Police": "Punjab Police",
    PSSSB: "PSSSB · Subordinate Services Selection Board, Punjab",
    PPSC: "PPSC · Punjab Public Service Commission",
  };
  /** @type {Record<string, string>} */
  const ORG_PA = {
    "Punjab Police": "ਪੰਜਾਬ ਪੁਲਿਸ",
    PSSSB: "ਅਧੀਨ ਸੇਵਾਵਾਂ ਚੋਣ ਬੋਰਡ",
    PPSC: "ਪੰਜਾਬ ਲੋਕ ਸੇਵਾ ਕਮਿਸ਼ਨ",
  };

  /** @type {any[]} */
  let exams = [];
  let org = "all";
  let query = "";

  const orgRank = (/** @type {string} */ o) => {
    const i = ORDER.indexOf(o);
    return i < 0 ? ORDER.length : i;
  };

  /** @param {any} e */
  function newest(e) {
    for (const row of e.papers || []) {
      if (row.papers && row.papers.length) return { year: row.year, file: row.papers[0] };
    }
    return null;
  }

  /** @param {any} e */
  function card(e) {
    const years = (e.papers || []).map((/** @type {any} */ p) => p.year);
    const keys = e.keyFiles != null ? e.keyFiles : e.keys;
    const latest = newest(e);
    const chips = years.length
      ? years.map((/** @type {string} */ y) => `<span class="pyq-year">${esc(y)}</span>`).join("")
      : `<span class="pyq-year pyq-year-none">Syllabus only</span>`;
    return `<article class="card card-pad pyq-exam">
      <h3><a href="${esc(e.file)}">${esc(e.title.replace(/ (Previous Year Papers|Papers & Syllabus|Papers)$/, ""))}</a></h3>
      <div class="pyq-years" aria-label="Years on record">${chips}</div>
      <p class="text-sm muted">${e.count} paper${e.count === 1 ? "" : "s"} · ${keys} answer key${keys === 1 ? "" : "s"}${
        e.others && e.others.length ? ` · ${e.others.length} more document${e.others.length === 1 ? "" : "s"}` : ""}</p>
      <p class="btn-row" style="margin-bottom:0">
        <a class="btn btn-soft" href="${esc(e.file)}">All papers &rarr;</a>
        ${latest ? `<a class="btn btn-soft" href="${esc(latest.file.path)}" download>${esc(latest.year)} paper ↓</a>` : ""}
      </p>
    </article>`;
  }

  /** @param {any} e */
  const matches = (e) => {
    if (org !== "all" && e.organization !== org) return false;
    if (!query) return true;
    const hay = `${e.title} ${e.organization} ${(e.papers || []).map((/** @type {any} */ p) => p.year).join(" ")}`.toLowerCase();
    return query.split(/\s+/).every((w) => hay.includes(w));
  };

  function render() {
    const shown = exams.filter(matches);
    if (!exams.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">📄</div>
        <h3>No previous year paper published yet</h3>
        <p>Papers appear here on the next publish, filed under their exam and their year.</p></div>`;
      return;
    }
    if (!shown.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div>
        <h3>No exam matches “${esc(query)}”</h3>
        <p>Try a shorter word, such as <em>clerk</em>, <em>patwari</em> or <em>2023</em>.</p></div>`;
      return;
    }
    /** @type {Map<string, any[]>} */
    const groups = new Map();
    shown
      .slice()
      .sort((a, b) => orgRank(a.organization) - orgRank(b.organization) || a.title.localeCompare(b.title))
      .forEach((e) => {
        if (!groups.has(e.organization)) groups.set(e.organization, []);
        /** @type {any[]} */ (groups.get(e.organization)).push(e);
      });
    grid.innerHTML = [...groups.entries()]
      .map(([o, list]) => {
        const n = list.reduce((s, e) => s + e.count, 0);
        return `<section class="pyq-group" style="grid-column:1/-1" aria-label="${esc(o)}">
          <h2 class="pyq-group-title">${esc(ORG_NAME[o] || o)}
            <span class="pyq-group-pa" lang="pa">${esc(ORG_PA[o] || "")}</span>
            <span class="pyq-group-count">${list.length} exam${list.length === 1 ? "" : "s"} · ${n} paper${n === 1 ? "" : "s"}</span></h2>
          <div class="grid grid-3">${list.map(card).join("")}</div>
        </section>`;
      })
      .join("");
  }

  function renderChips() {
    if (!chipsBox) return;
    const orgs = [...new Set(exams.map((e) => e.organization))].sort((a, b) => orgRank(a) - orgRank(b));
    const btn = (/** @type {string} */ id, /** @type {string} */ label) =>
      `<button type="button" class="filter-chip" data-org="${esc(id)}" aria-pressed="${org === id}">${esc(label)}</button>`;
    chipsBox.innerHTML =
      btn("all", "All exams") +
      orgs.map((o) => btn(o, `${o} (${exams.filter((e) => e.organization === o).length})`)).join("");
  }

  chipsBox?.addEventListener("click", (ev) => {
    const b = /** @type {HTMLElement} */ (ev.target).closest("[data-org]");
    if (!b) return;
    org = b.getAttribute("data-org") || "all";
    renderChips();
    render();
  });
  search?.addEventListener("input", () => {
    query = search.value.trim().toLowerCase();
    render();
  });

  fetch("data/pyq-manifest.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .catch(() => null)
    .then((m) => {
      exams = (m && m.exams) || [];
      if (stats && m) {
        const keys = exams.reduce((s, e) => s + (e.keyFiles != null ? e.keyFiles : e.keys), 0);
        stats.textContent = `${exams.length} exams · ${m.papers} question papers · ${keys} answer keys, all free to download`;
      }
      renderChips();
      render();
    });
})();
