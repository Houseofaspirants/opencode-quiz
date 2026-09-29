/* ============================================================================
 * revision.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * The revision queue: every subject and every chapter inside it, each one
 * linking to the SAME quiz engine with the SAME parameters as an Expected MCQ
 * set. Nothing about the engine changes - what changes is when you open it and
 * what you are told to do: attempt it cold, days after you first studied it.
 *
 * Everything is read from data/index.json through HOA.loadIndex(), so a new
 * chapter file appears here the moment the build picks it up. No config edit.
 * ========================================================================== */
(() => {
  "use strict";
  const grid = document.getElementById("revGrid");
  if (!grid) return;

  const searchEl = document.getElementById("revSearch");

  const esc = (s) =>
    String(s).replace(/[&<>"'/]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "/": "&#47;" }[c]));

  /** Same link shape subject.js builds, so revision and practice agree. */
  function topicHref(subject, t) {
    const cat = t.category ? `&category=${encodeURIComponent(t.category)}` : "";
    return `quiz.html?subject=${encodeURIComponent(subject.id)}&topic=${encodeURIComponent(t.id)}${cat}`;
  }

  function subjectCard(s) {
    const topics = (s.topics || []).filter((t) => t.available);
    const total = (s.topics || []).reduce((n, t) => n + (t.count || 0), 0);
    const chips = topics
      .slice(0, 8)
      .map(
        (t) =>
          `<a class="area-chip ilink" href="${topicHref(s, t)}">${esc(t.name)}</a>`
      )
      .join("");

    return `
    <article class="card card-pad rev-card">
      <span class="eyebrow">${topics.length} chapter${topics.length === 1 ? "" : "s"} · ${total} question${total === 1 ? "" : "s"}</span>
      <h3>${esc(s.icon || "📘")} ${esc(s.name)}</h3>
      <p class="text-sm muted">Attempt these cold. Do not reread the notes first.</p>
      ${chips ? `<div class="chip-wrap">${chips}</div>` : `<p class="text-sm muted">No live set yet.</p>`}
      <p class="btn-row" style="margin-bottom:0">
        <a class="btn btn-soft" href="subject.html?subject=${encodeURIComponent(s.id)}">All chapters →</a>
        <a class="btn btn-soft" href="mock.html">Mixed test →</a>
      </p>
    </article>`;
  }

  let subjects = [];
  let term = "";

  function apply() {
    const q = term.trim().toLowerCase();
    const list = q
      ? subjects.filter(
          (s) =>
            s.name.toLowerCase().includes(q) ||
            (s.topics || []).some((t) => t.name.toLowerCase().includes(q))
        )
      : subjects;

    if (!list.length) {
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div>
        <h3>No subject matches “${esc(term)}”</h3>
        <p>Try a different keyword.</p></div>`;
      return;
    }
    grid.innerHTML = list.map(subjectCard).join("");
  }

  searchEl?.addEventListener("input", () => {
    term = /** @type {HTMLInputElement} */ (searchEl).value;
    apply();
  });

  if (typeof HOA !== "undefined" && HOA.loadIndex) {
    HOA.loadIndex()
      .then((idx) => {
        subjects = (idx && idx.subjects) || [];
        if (!subjects.length) {
          grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
            <div class="es-icon">📂</div>
            <h3>No chapters published yet</h3>
            <p>Revision tests appear as soon as the first chapter set is live.</p></div>`;
          return;
        }
        apply();
      })
      .catch(() => {
        grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
          <div class="es-icon">⚠️</div>
          <h3>The revision queue could not load</h3>
          <p>Refresh the page, or open a subject directly from the menu.</p></div>`;
      });
  }
})();
