/* ============================================================================
 * mock.js | Mock Test builder
 * Assembles a full-length test from whatever quizzes currently exist.
 * Zero questions live in this file - everything is read from /questions.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const idx = await HOA.loadIndex();
  const wrap = document.getElementById("mockSubjects");
  const startBtn = document.getElementById("mockStart");
  const countSelect = document.getElementById("mockCount");
  const statusEl = document.getElementById("mockStatus");

  const subjects = (idx.subjects || []).map((s) => ({
    ...s,
    qCount: s.topics.filter((t) => t.available).reduce((n, t) => n + t.count, 0),
  }));
  const totalQ = subjects.reduce((n, s) => n + s.qCount, 0);

  /* --------------------------------------------------------- Build UI ---- */
  if (!wrap) return;

  wrap.innerHTML = `
    <label class="mock-option selected">
      <input type="radio" name="mockSubject" value="all" checked>
      <span>📘 All Subjects <span class="muted text-sm">(Mixed mock)</span></span>
      <span class="badge badge-muted" style="margin-left:auto">${totalQ} Q</span>
    </label>` +
    subjects
      .map(
        (s) => `
    <label class="mock-option ${s.qCount ? "" : "disabled"}">
      <input type="radio" name="mockSubject" value="${esc(s.id)}" ${s.qCount ? "" : "disabled"}>
      <span>${s.icon} ${esc(s.name)}</span>
      <span class="badge ${s.qCount ? "badge-muted" : "badge-warn"}" style="margin-left:auto">${
        s.qCount ? s.qCount + " Q" : "Empty"
      }</span>
    </label>`
      )
      .join("");

  statusEl.textContent = totalQ
    ? `${totalQ} questions are available for mock tests right now.`
    : "No questions available yet. Add JSON files under /questions to unlock mock tests.";

  startBtn.disabled = totalQ === 0;

  /* Selection highlight */
  wrap.addEventListener("change", () => {
    wrap.querySelectorAll(".mock-option").forEach((el) => el.classList.remove("selected"));
    wrap.querySelector("input:checked")?.closest(".mock-option")?.classList.add("selected");
  });

  /* --------------------------------------------------------- Start ------- */
  startBtn.addEventListener("click", () => {
    const subject =
      document.querySelector("input[name='mockSubject']:checked")?.value || "all";
    const count = countSelect.value;
    const minutes = document.getElementById("mockMinutes").value;
    location.href = `quiz.html?mode=mock&subject=${encodeURIComponent(subject)}&count=${count}&minutes=${minutes}`;
  });
})();
