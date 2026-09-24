/* ============================================================================
 * subject.js | Subject page — auto-detected topic list + instant filter
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const params = new URLSearchParams(location.search);
  const subjectId = params.get("subject") || "";
  const idx = await HOA.loadIndex();
  const subject = (idx.subjects || []).find((s) => s.id === subjectId);

  const wrap = document.getElementById("topicGrid");
  const titleEl = document.getElementById("subjectTitle");
  const crumbEl = document.getElementById("crumbSubject");
  const descEl = document.getElementById("subjectDesc");
  const filterEl = document.getElementById("topicFilter");

  if (!subject) {
    titleEl.textContent = "Subject not found";
    descEl.textContent = "Pick a subject from the home page.";
    if (crumbEl) crumbEl.textContent = "Not found";
    wrap.innerHTML = `<div class="empty-state"><div class="es-icon">🤔</div>
      <h3>Unknown subject</h3>
      <p>This subject is not in your configuration. Check <code>data/subjects.json</code> or the folder name inside <code>questions/</code>.</p>
      <p class="mt-2"><a class="btn btn-primary" href="index.html">Back to Home</a></p></div>`;
    return;
  }

  /* ------------------------------------------------- Page header content - */
  const pageUrl =
    `${String((idx.site && idx.site.url) || "").replace(/\/+$/, "")}` +
    `/subject?subject=${encodeURIComponent(subject.id)}`;
  HOA.seo({
    title: `${subject.name} Quiz - House of Aspirants`,
    canonical: pageUrl,
    robots: "index, follow",
    ogTitle: `${subject.name} Quiz - House of Aspirants`,
    ogDescription:
      subject.description ||
      `Topic-wise ${subject.name} MCQ practice for Punjab Police & competitive exams.`,
  });
  titleEl.textContent = subject.name;
  if (crumbEl) crumbEl.textContent = subject.name;
  descEl.textContent = subject.description || "Topic-wise MCQ practice.";
  document.getElementById("subjectIcon").textContent = subject.icon;
  document.getElementById("countTopics").textContent = subject.topics.length;
  document.getElementById("countQuizzes").textContent =
    subject.topics.filter((t) => t.available).length;
  document.getElementById("countQuestions").textContent =
    subject.topics.reduce((n, t) => n + t.count, 0);

  /* ------------------------------------------------------ Render topics - */
  function render(list) {
    if (!subject.topics.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="es-icon">📂</div>
        <h3>No topics added yet.</h3>
        <p>Create a file like <code>questions/${esc(subject.id)}/your-topic.json</code>
        (copy <code>templates/topic-template.json</code>) and it will appear here automatically — no code changes.</p>
        <p class="mt-2"><a class="btn btn-soft" href="https://t.me/HouseOfAspirants" target="_blank" rel="noopener">Join Telegram for updates</a></p></div>`;
      return;
    }
    if (!list.length) {
      wrap.innerHTML = `<div class="empty-state"><div class="es-icon">🔎</div>
        <h3>No topic matches “${esc(filterEl.value)}”</h3>
        <p>Try a different keyword.</p></div>`;
      return;
    }
    wrap.innerHTML = list
      .map((t) => {
        const clickable = t.available;
        const tag = clickable ? "a" : "div";
        const href = clickable
          ? `quiz.html?subject=${encodeURIComponent(subject.id)}&topic=${encodeURIComponent(t.id)}`
          : "javascript:void(0)";
        return `
        <${tag} class="card quiz-card${clickable ? "" : " disabled"}" href="${href}"
           ${clickable ? "" : 'aria-disabled="true"'}>
          <span class="qc-icon">${subject.icon}</span>
          <span>
            <h4>${esc(t.name)}</h4>
            <span class="qc-sub">${
              clickable
                ? `${t.count} question${t.count === 1 ? "" : "s"} · Start quiz →`
                : `No questions available yet.`
            }</span>
          </span>
          <span class="qc-go">${clickable ? "→" : "⏳"}</span>
        </${tag}>`;
      })
      .join("");
  }

  render(subject.topics);

  /* ---------------------------------------------- Instant topic filter --- */
  filterEl.addEventListener("input", () => {
    const term = filterEl.value.trim().toLowerCase();
    render(
      !term
        ? subject.topics
        : subject.topics.filter(
            (t) =>
              t.name.toLowerCase().includes(term) ||
              (t.description || "").toLowerCase().includes(term)
          )
    );
  });
})();
