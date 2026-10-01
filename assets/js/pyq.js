/* ============================================================================
 * pyq.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Three lists, all read from config:
 *
 *   1. EXAMS  — data/exams.json. Names the exam a paper belongs to and links
 *               its landing page. Add an exam to that file, rerun the build,
 *               and every paper filed under it picks the name up here.
 *
 *   2. PAPERS — data/content-manifest.json. The PDF scanner writes one `drops`
 *               record per file under content/, so a paper dropped into
 *               content/previous-year-questions/<exam>/<year>-question-paper.pdf
 *               is picked up on the next publish with no page, no markup and no
 *               code written for it. `folder` is the collection, `category` the
 *               exam sub-folder, the filename carries the year.
 *
 *   3. FOLDERS — data/pyq-manifest.json. One entry per exam folder, with the
 *               file name of that exam's own page (pyq/<slug>/index.html) and
 *               how many papers and answer keys it holds. A paper whose exam
 *               has a folder gains the "All years" link to that table.
 * ========================================================================== */
(() => {
  "use strict";
  const paperGrid = document.getElementById("pyqPapers");
  if (!paperGrid) return;

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

  /* ------------------------------------------------------------ exams ----- */
  let exams = [];

  /* The folder-per-exam collection (data/pyq-manifest.json): which exams hold
     a folder of their own under content/previous-year-questions/, and the file
     name of each folder's year-by-year table. */
  let folders = [];
  let folderById = new Map();

  /* ---------------------------------------------------------- papers ------ */
  let papers = [];

  const yearOf = (d) => {
    const m = String(d.filename || "").match(/(19|20)\d{2}/);
    return m ? m[0] : "";
  };

  function paperCard(d) {
    const exam = exams.find((e) => e.id === d.category);
    const folder = folderById.get(d.category);
    const year = yearOf(d);
    return `
    <article class="card card-pad">
      <span class="eyebrow">${esc(exam ? exam.name : d.category || "Paper")} · ${esc(year || "Year on file")}</span>
      <h3>${esc(d.title || d.slug)}</h3>
      <p class="text-sm muted">${esc(d.sizeLabel || "")}${d.pages ? ` · ${d.pages} pages` : ""} · ${d.language === "pa" ? "Punjabi" : "English"}</p>
      <p class="btn-row" style="margin-bottom:0">
        <a class="btn btn-soft" href="${esc(d.path)}" target="_blank" rel="noopener">Download PDF ↓</a>
        ${folder ? `<a class="btn btn-soft" href="${esc(folder.file)}">All years &rarr;</a>` : ""}
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

  Promise.all([
    fetchJSON("data/exams.json"),
    fetchJSON("data/content-manifest.json"),
    fetchJSON("data/pyq-manifest.json"),
  ]).then(
    ([ex, cm, pyq]) => {
      exams = (ex && ex.exams) || [];
      papers = ((cm && cm.drops) || []).filter(isPaper);
      folders = (pyq && pyq.exams) || [];
      folderById = new Map(folders.map((f) => [f.id, f]));
      renderPapers();
    }
  );
})();
