/* ============================================================================
 * home.js | Landing page behaviour
 * Live statistics, latest quiz cards, search shortcut.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc, countUp } = HOA;
  const idx = await HOA.loadIndex();
  const stats = idx.stats || {};

  /* ------------------------------------------- 1. Live statistics section
     Rule: never show a placeholder zero. A block is revealed only once
     index.json reports a real number, and any metric that is still 0 drops
     its whole card instead of printing "0". */
  const statMap = {
    subjects: stats.subjects ?? 0,
    topics: stats.topics ?? 0,
    quizzes: stats.quizzes ?? 0,
    questions: stats.questions ?? 0,
  };
  const hasData = Object.values(statMap).some((v) => v > 0);

  if (hasData) {
    document.querySelectorAll("[data-stats-section], .hero-visual").forEach((el) => {
      el.hidden = false;
    });
  }

  document.querySelectorAll("[data-stat]").forEach((el) => {
    const target = statMap[el.dataset.stat] ?? 0;
    if (target === 0) {
      const card = el.closest(".stat-card, .float-card");
      if (card) card.hidden = true;
      else el.textContent = "";
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
        `The quiz engine is ready. Add your first JSON file, e.g. <code>questions/gk/polity/your-topic.json</code>, and the card will appear here instantly.`);
    } else {
      latestWrap.innerHTML = live
        .slice(0, 8)
        .map((t) => `
        <a class="card quiz-card" href="quiz.html?subject=${encodeURIComponent(t.subject.id)}&topic=${encodeURIComponent(t.id)}${t.category ? `&category=${encodeURIComponent(t.category)}` : ""}">
          <span class="qc-icon">${t.subject.icon}</span>
          <span>
            <h3>${esc(t.name)}${HOA.langBadge(t.variants)}</h3>
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

  /* ---------------------------- 5. Content engine: personalised feed -----
     Two cards that can only exist on the reader's side: "Continue learning"
     (the subject they last practised) and "Recommended for you" (the same
     facet scoring the builder uses, run here over the embedded candidate
     list in #engineData - no extra request, so the homepage stays fast).
     Rule, same as everywhere else: no signal, no card. With nothing real to
     show, the whole #foryou section stays hidden. */
  function engineFeed() {
    const section = document.getElementById("foryou");
    const recs = document.getElementById("engineRecs");
    if (!section || !recs) return;

    let data = [];
    try {
      // The builder writes the payload between the HOA-HOME markers, so the
      // marker comments themselves arrive as text - strip them before parsing.
      const raw = (document.getElementById("engineData")?.textContent || "")
        .replace(/<!--[\s\S]*?-->/g, "")
        .trim();
      data = raw ? JSON.parse(raw) : [];
    } catch { data = []; }
    if (!Array.isArray(data)) data = [];

    const prog = HOA.progress.get();
    const bookmarks = HOA.bookmarks.all() || [];
    const last = String(prog.lastSubject || "").trim();
    const affinity = new Set(
      [last, ...bookmarks.map((b) => b.subject || String(b.key || "").split(":")[0])]
        .map((s) => String(s || "").trim())
        .filter((s) => s && s !== "mixed")
    );

    // No `reveal` class here: those elements are injected after the reveal
    // observer has already run, so they must be visible as-is.
    const card = (c) => `<a class="card card-pad" href="${esc(c.href)}">
        <span class="eyebrow">${esc(c.eyebrow)}</span>
        <h3>${esc(c.title)}</h3>
        ${c.sub ? `<p class="muted">${esc(c.sub)}</p>` : ""}
        <p class="ilink">${esc(c.meta)}</p></a>`;

    const cards = [];

    if (last && last !== "mixed") {
      const subject = (idx.subjects || []).find((s) => s.id === last);
      cards.push(card({
        href: `subject.html?subject=${encodeURIComponent(last)}`,
        eyebrow: "Continue learning",
        title: subject ? subject.name : last,
        sub: prog.quizzes
          ? `${prog.quizzes} quiz${prog.quizzes === 1 ? "" : "zes"} attempted in this subject.`
          : "Pick up where you left off.",
        meta: "Resume →",
      }));
    }

    if (affinity.size && data.length) {
      const scored = data
        .map((row, i) => ({
          row, i,
          score: (row.s || []).reduce(
            (total, id) => total + (affinity.has(String(id)) ? 6 : 0), 0),
        }))
        .filter((x) => x.score > 0)
        .sort((a, b) => b.score - a.score || a.i - b.i)
        .slice(0, 3);
      scored.forEach(({ row }) => cards.push(card({
        href: row.u,
        eyebrow: "Recommended for you",
        title: row.t,
        sub: [`${row.m} min read`, row.d].filter(Boolean).join(" · "),
        meta: "Read it →",
      })));
    }

    if (!cards.length) return;
    recs.innerHTML = cards.join("");
    recs.hidden = false;
    section.hidden = false;
  }
  engineFeed();

  /* ---------------------------------- 6. Hero search box → global search - */
  document.getElementById("homeSearch")?.addEventListener("focus", (e) => {
    e.target.blur(); // keep focus in the overlay input instead
    document.querySelector("[data-action='open-search']")?.click();
  });
})();
