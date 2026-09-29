/* ============================================================================
 * books.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Renders the Books shelf from data/books.json: search, exam filter, and one
 * card per book carrying cover block, author, publisher, edition, language,
 * exam tags, difficulty, rating, the honest "buy if / skip if" pair and the
 * purchase button.
 *
 * Config, not code: add an object to data/books.json and the shelf grows. No
 * build step, no markup edit. Purchase links live in each entry's `url`, so
 * pasting an affiliate URL there is the whole affiliate setup - the anchor
 * already carries rel="sponsored".
 *
 * Loading books.html runs this; every other page ignores it.
 * ========================================================================== */
(() => {
  "use strict";
  const grid = document.getElementById("bookGrid");
  if (!grid) return;

  const searchEl = document.getElementById("bookSearch");
  const filterEl = document.getElementById("bookFilters");

  const esc = (s) =>
    String(s).replace(/[&<>"'/]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "/": "&#47;" }[c]));

  const SUBJECT_LABEL = {
    gk: "General Knowledge",
    quant: "Quantitative Aptitude",
    reasoning: "Reasoning",
    punjabi: "Punjabi",
    english: "English",
    computer: "Computer",
    "current-affairs": "Current Affairs",
  };

  const EXAM_LABEL = {
    "punjab-police": "Punjab Police",
    pcs: "Punjab PCS",
    psssb: "PSSSB",
    pspcl: "PSPCL",
    ssc: "SSC",
    banking: "Banking",
    railways: "Railways",
    upsc: "UPSC",
    capf: "CAPF",
    general: "General competitive",
    patwari: "Patwari",
  };

  /** ★ full, a dimmed ★ for a half, ☆ for the rest - no library, no images. */
  function stars(rating) {
    const r = Number(rating) || 0;
    const full = Math.floor(r);
    const half = r - full >= 0.5;
    const rest = Math.max(0, 5 - full - (half ? 1 : 0));
    return "★".repeat(full) + (half ? '<span class="star-half">★</span>' : "")
      + "☆".repeat(rest);
  }

  function card(b) {
    const subject = SUBJECT_LABEL[b.subject] || b.subject;
    const tags = (b.exams || []).map((e) => EXAM_LABEL[e] || e);
    const related = (b.related || [])
      .map((r) => `<a class="ilink" href="${esc(r.href)}">${esc(r.label)}</a>`)
      .join(" · ");
    const external = String(b.url || "").startsWith("http");
    const href = esc(b.url || "#");
    const languages = (b.language || []).join(" · ");

    return `
    <article class="card card-pad book-card">
      <div class="book-cover" aria-hidden="true"><span>${esc((b.title || "").slice(0, 2))}</span></div>
      <span class="eyebrow">${esc(subject)} · ${esc(b.difficulty || "")}</span>
      <h3>${esc(b.title)}</h3>
      <p class="text-sm muted">${esc(b.author)} · ${esc(b.publisher)}</p>
      <p class="book-rating text-sm" aria-label="Rated ${esc(b.rating)} out of 5">
        <span aria-hidden="true">${stars(b.rating)}</span> <strong>${esc(b.rating)}</strong>
      </p>
      <p class="text-sm">${esc(b.why)}</p>
      <ul class="book-meta text-sm muted">
        <li><span>Edition</span> ${esc(b.edition)}</li>
        <li><span>Language</span> ${esc(languages)}</li>
        <li><span>Best for</span> ${esc(b.bestFor)}</li>
      </ul>
      <p class="text-sm"><strong>Buy it if:</strong> ${esc(b.buyIf)}</p>
      <p class="text-sm"><strong>Skip it if:</strong> ${esc(b.skipIf)}</p>
      <p class="text-sm muted"><strong>How to use it:</strong> ${esc(b.reread)}</p>
      ${related ? `<p class="text-sm"><strong>Study beside it:</strong> ${related}</p>` : ""}
      <p class="btn-row mt-2" style="margin-bottom:0">
        <a class="btn btn-soft" href="${href}"
           ${external ? 'target="_blank" rel="sponsored noopener nofollow"' : ""}>Get this book →</a>
        <a class="btn btn-soft" href="subject.html?subject=${encodeURIComponent(b.subject)}">Free ${esc(subject)} sets</a>
      </p>
    </article>`;
  }

  let books = [];
  let exam = "all";
  let term = "";

  function apply() {
    const q = term.trim().toLowerCase();
    const list = books.filter((b) => {
      const inExam = exam === "all" || (b.exams || []).includes(exam);
      if (!inExam) return false;
      if (!q) return true;
      return [b.title, b.author, b.publisher, b.subject, b.why, b.bestFor]
        .join(" ")
        .toLowerCase()
        .includes(q);
    });

    if (!list.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div>
        <h3>No book matches ${q ? `“${esc(term)}”` : "this exam"}</h3>
        <p>Try another keyword, or clear the exam filter.</p></div>`;
      return;
    }
    grid.innerHTML = list.map(card).join("");
  }

  filterEl?.addEventListener("click", (e) => {
    const btn = /** @type {HTMLElement | null} */ (e.target).closest?.("[data-filter]");
    if (!btn) return;
    exam = btn.getAttribute("data-filter") || "all";
    filterEl.querySelectorAll("[data-filter]").forEach((b) =>
      b.setAttribute("aria-pressed", String(b === btn))
    );
    apply();
  });

  searchEl?.addEventListener("input", () => {
    term = /** @type {HTMLInputElement} */ (searchEl).value;
    apply();
  });

  fetch("data/books.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      books = (data && data.books) || [];
      if (!books.length) {
        grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
          <div class="es-icon">📚</div>
          <h3>The shelf is being stocked</h3>
          <p>Books are added one at a time, with a note on who each one suits.
             Until the first note lands, the free study material covers the syllabus.</p></div>`;
        return;
      }
      apply();
    })
    .catch(() => {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">⚠️</div>
        <h3>The shelf could not load</h3>
        <p>Refresh the page, or start with the free study material.</p></div>`;
    });
})();
