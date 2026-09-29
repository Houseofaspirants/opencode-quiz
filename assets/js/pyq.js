/* ============================================================================
 * pyq.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Two lists, both read from config:
 *
 *   1. EXAMS  — data/exams.json. Every registered exam becomes an exam card
 *               linking to its own generated landing page. Add an exam to that
 *               file, rerun the build, and it appears here automatically.
 *
 *   2. PAPERS — data/content-manifest.json. The PDF scanner writes one `drops`
 *               record per file under content/, so a paper dropped into
 *               content/previous-year-questions/<exam>/<year>.pdf is picked up
 *               on the next publish with no page, no markup and no code
 *               written for it. `folder` is the collection, `category` the exam
 *               sub-folder, the filename carries the year.
 * ========================================================================== */
(() => {
  "use strict";
  const examGrid = document.getElementById("pyqExams");
  const paperGrid = document.getElementById("pyqPapers");
  const searchEl = document.getElementById("pyqSearch");
  if (!examGrid || !paperGrid) return;

  const esc = (s) =>
    String(s).replace(/[&<>"'/]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "/": "&#47;" }[c]));

  const fetchJSON = (url) =>
    fetch(url, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);

  /* Papers live in this collection folder under content/. */
  const PAPER_FOLDERS = ["previous-year-questions", "previous-year-papers"];
  const isPaper = (d) => PAPER_FOLDERS.includes(String(d.folder || ""));

  /** State exams first — that is who a Punjab aspirant is actually writing. */
  const CENTRAL = new Set(["ssc", "railways", "banking", "upsc", "capf"]);
  const band = (id) => (CENTRAL.has(id) ? "central" : "state");

  const SUBJECT_LABEL = {
    gk: "General Knowledge", quant: "Quantitative Aptitude", reasoning: "Reasoning",
    punjabi: "Punjabi", english: "English", computer: "Computer",
    "current-affairs": "Current Affairs",
  };

  /* ------------------------------------------------------------ exams ----- */
  let exams = [];
  let term = "";

  function examCard(e) {
    const subs = (e.subjects || [])
      .map((id) => SUBJECT_LABEL[id] || id)
      .join(" · ");
    const published = papers.filter((p) => p.exam === e.id).length;
    return `
    <a class="card card-pad" href="exam-${encodeURIComponent(e.id)}.html">
      <span class="eyebrow">${band(e.id) === "central" ? "Central exam" : "Punjab exam"}${subs ? " · " + esc(subs) : ""}</span>
      <h3>${esc(e.name)}</h3>
      <p class="text-sm muted">${esc(e.summary || "")}</p>
      <p class="text-sm">${published ? `${published} paper${published === 1 ? "" : "s"} published` : "Syllabus, subjects and practice sets"}</p>
      <p class="ilink">Open exam &rarr;</p>
    </a>`;
  }

  function renderExams() {
    const q = term.trim().toLowerCase();
    const list = q
      ? exams.filter(
          (e) => e.name.toLowerCase().includes(q) || String(e.summary || "").toLowerCase().includes(q)
        )
      : exams;
    if (!list.length) {
      examGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div><h3>No exam matches “${esc(term)}”</h3>
        <p>Try another keyword.</p></div>`;
      return;
    }
    const groups = [
      ["Punjab state exams", list.filter((e) => band(e.id) === "state")],
      ["Central exams", list.filter((e) => band(e.id) === "central")],
    ];
    examGrid.innerHTML = groups
      .filter(([, g]) => g.length)
      .map(
        ([label, g]) => `
      <div class="pyq-group" style="grid-column:1/-1">
        <h2 class="pyq-group-title">${label}</h2>
        <div class="grid grid-3">${g.map(examCard).join("")}</div>
      </div>`
      )
      .join("");
  }

  /* ---------------------------------------------------------- papers ------ */
  let papers = [];

  const yearOf = (d) => {
    const m = String(d.filename || "").match(/(19|20)\d{2}/);
    return m ? m[0] : "";
  };

  function paperCard(d) {
    const exam = exams.find((e) => e.id === d.category);
    const year = yearOf(d);
    return `
    <article class="card card-pad">
      <span class="eyebrow">${esc(exam ? exam.name : d.category || "Paper")} · ${esc(year || "Year on file")}</span>
      <h3>${esc(d.title || d.slug)}</h3>
      <p class="text-sm muted">${esc(d.sizeLabel || "")}${d.pages ? ` · ${d.pages} pages` : ""} · ${d.language === "pa" ? "Punjabi" : "English"}</p>
      <p class="btn-row" style="margin-bottom:0">
        <a class="btn btn-soft" href="${esc(d.path)}" target="_blank" rel="noopener">Download PDF ↓</a>
        ${exam ? `<a class="btn btn-soft" href="exam-${encodeURIComponent(exam.id)}.html">Exam page →</a>` : ""}
      </p>
    </article>`;
  }

  function renderPapers() {
    if (!papers.length) {
      paperGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">📄</div>
        <h3>No previous year paper published yet</h3>
        <p>Papers are added as PDFs to the previous-year-papers collection and appear
           here on the very next publish, filed under their exam and their year — the
           page never needs editing. Until then, the exam cards above carry the syllabus,
           the subjects and the practice sets for each paper.</p>
        <p class="btn-row" style="justify-content:center">
          <a class="btn btn-soft" href="expected-mcqs.html">Practise by chapter instead</a>
          <a class="btn btn-soft" href="mock.html">Attempt a timed mock</a>
        </p></div>`;
      return;
    }
    const byExam = new Map();
    papers.forEach((p) => {
      const key = p.category || "other";
      if (!byExam.has(key)) byExam.set(key, []);
      byExam.get(key).push(p);
    });
    paperGrid.innerHTML = [...byExam.entries()]
      .map(([key, list]) => {
        const exam = exams.find((e) => e.id === key);
        return `<div class="pyq-group" style="grid-column:1/-1">
          <h2 class="pyq-group-title">${esc(exam ? exam.name : key)}</h2>
          <div class="grid grid-3">${list.map(paperCard).join("")}</div>
        </div>`;
      })
      .join("");
  }

  searchEl?.addEventListener("input", () => {
    term = /** @type {HTMLInputElement} */ (searchEl).value;
    renderExams();
  });

  Promise.all([fetchJSON("data/exams.json"), fetchJSON("data/content-manifest.json")]).then(
    ([ex, cm]) => {
      exams = (ex && ex.exams) || [];
      papers = ((cm && cm.drops) || []).filter(isPaper);
      if (!exams.length) {
        examGrid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
          <div class="es-icon">📂</div><h3>No exam registered yet</h3>
          <p>Exams are registered in configuration, not in markup.</p></div>`;
      } else {
        renderExams();
      }
      renderPapers();
    }
  );
})();
