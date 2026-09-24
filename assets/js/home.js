/* ============================================================================
 * home.js | Landing page behaviour
 * Live statistics, latest quiz cards, search shortcut.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc, countUp } = HOA;
  const idx = await HOA.loadIndex();
  const stats = idx.stats || {};

  /* ------------------------------------------- 1. Live statistics section */
  const statMap = {
    subjects: stats.subjects ?? 0,
    topics: stats.topics ?? 0,
    quizzes: stats.quizzes ?? 0,
    questions: stats.questions ?? 0,
  };
  document.querySelectorAll("[data-stat]").forEach((el) => {
    const target = statMap[el.dataset.stat] ?? 0;
    if (target === 0) {
      el.textContent = "0";
      return;
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          countUp(el, target);
          io.disconnect();
        }
      },
      { threshold: 0.4 }
    );
    io.observe(el);
  });

  /* ------------------------------------------ 2. Subject cards (auto) ---- */
  const subjectGrid = document.getElementById("subjectGrid");
  if (subjectGrid) {
    const subjects = idx.subjects || [];
    if (!subjects.length) {
      subjectGrid.innerHTML = emptyBox("📭", "No subjects detected yet.",
        `Add a folder such as <code>questions/gk/</code> and it will appear here automatically.`);
    } else {
      subjectGrid.innerHTML = subjects
        .map((s) => {
          const live = s.topics.filter((t) => t.available);
          const qCount = live.reduce((n, t) => n + t.count, 0);
          return `
          <a class="card subject-card" style="--sc:${s.color}" href="subject.html?subject=${encodeURIComponent(s.id)}">
            <span class="subject-icon">${s.icon}</span>
            <h3>${esc(s.name)}</h3>
            <p>${esc(s.description || "Topic-wise MCQ practice.")}</p>
            <div class="subject-meta">
              <span class="badge">${s.topics.length} topic${s.topics.length === 1 ? "" : "s"}</span>
              <span class="badge ${live.length ? "badge-success" : "badge-muted"}">${live.length} quiz${live.length === 1 ? "" : "zes"}</span>
              <span class="badge badge-muted">${qCount} Q</span>
            </div>
          </a>`;
        })
        .join("");
    }
  }

  /* -------------------------------------------- 3. Latest quiz cards ----- */
  const latestWrap = document.getElementById("latestQuizzes");
  if (latestWrap) {
    const live = [];
    (idx.subjects || []).forEach((s) =>
      s.topics
        .filter((t) => t.available)
        .forEach((t) => live.push({ ...t, subject: s }))
    );
    live.sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0));

    if (!live.length) {
      latestWrap.innerHTML = emptyBox("🚧", "No quizzes published yet.",
        `The quiz engine is ready. Add your first JSON file, e.g. <code>questions/gk/polity.json</code>, and the card will appear here instantly.`);
    } else {
      latestWrap.innerHTML = live
        .slice(0, 8)
        .map((t) => `
        <a class="card quiz-card" href="quiz.html?subject=${encodeURIComponent(t.subject.id)}&topic=${encodeURIComponent(t.id)}">
          <span class="qc-icon">${t.subject.icon}</span>
          <span>
            <h4>${esc(t.name)}</h4>
            <span class="qc-sub">${esc(t.subject.name)} · ${t.count} question${t.count === 1 ? "" : "s"}</span>
          </span>
          <span class="qc-go">→</span>
        </a>`)
        .join("");
    }
  }

  /* ------------------------------------------ 4. Shared empty-state HTML - */
  function emptyBox(icon, title, html) {
    return `<div class="empty-state"><div class="es-icon">${icon}</div>
      <h3>${title}</h3><p>${html}</p></div>`;
  }

  /* ---------------------------------- 5. Hero search box → global search - */
  document.getElementById("homeSearch")?.addEventListener("focus", (e) => {
    e.target.blur(); // keep focus in the overlay input instead
    document.querySelector("[data-action='open-search']")?.click();
  });
})();
