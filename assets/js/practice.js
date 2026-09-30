// @ts-check
/* ============================================================================
 * practice.js | The PRACTICE system — the subject tree, ending at a quiz
 * ----------------------------------------------------------------------------
 * Study and Practice share ONE taxonomy and render it twice:
 *   study.html?subject=gk      → chapters + notes + PDFs   (reading)
 *   subject.html?subject=gk    → chapters + Launch Quiz    (questions)
 *
 * Practice therefore does not keep its own copy of the tree: every subject
 * card here hands over to subject.html, which already walks
 * subject > category > topic > quiz.html. Nothing is duplicated and the quiz
 * engine is untouched.
 *
 * The counts on a card are deliberately practice-shaped — chapters, question
 * sets and questions available — because this page exists to get someone to
 * a question paper, not to a reading list.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const idx = await HOA.loadIndex();
  const subjects = idx.subjects || [];

  const grid = document.getElementById("practiceSubjects");
  if (!grid) return;

  grid.innerHTML = subjects
    .slice()
    .sort((a, b) => (a.order || 0) - (b.order || 0))
    .map((s) => {
      const live = (s.topics || []).filter((t) => t.available);
      const chapters = new Set(live.map((t) => String(t.id).replace(/-part\d+(?=-|$)/i, ""))).size;
      const questions = live.reduce((n, t) => n + (t.count || 0), 0);
      return `
        <a class="card subject-card" style="--sc:${s.color}" href="subject.html?subject=${esc(s.id)}">
          <span class="subject-icon">${s.icon}</span>
          <h3>${esc(s.name)}</h3>
          <p>${esc(s.description || "Topic-wise MCQ practice for this subject.")}</p>
          <div class="subject-meta">
            <span class="badge">${chapters} chapter${chapters === 1 ? "" : "s"}</span>
            <span class="badge ${live.length ? "badge-success" : "badge-muted"}">${live.length} set${live.length === 1 ? "" : "s"}</span>
            <span class="badge badge-muted">${questions} Q</span>
          </div>
        </a>`;
    })
    .join("");
})();
