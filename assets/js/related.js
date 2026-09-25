/* ============================================================================
 * related.js | House of Aspirants Quiz Portal
 * ----------------------------------------------------------------------------
 * Intelligent internal-linking modules rendered on subject pages:
 *
 *   1. Related Subjects  — sibling subjects ranked by an affinity map
 *                           (Punjab-exam study pairs first, config order rest)
 *   2. Related Quizzes   — live quizzes from data/index.json, current subject
 *                           and category floated to the top, current quiz excluded
 *   3. Related Articles  — study guides from data/articles.json (registry),
 *                           matched by subject/category; falls back to all
 *
 * Everything is config-driven: subjects come from data/subjects.json (via the
 * index), articles from data/articles.json. Drop a placeholder on any page:
 *
 *   <section class="section" id="relatedSection"> ... <div id="relatedGrid">
 *
 * and load this file after core.js. Cards with no matches are omitted and the
 * whole section hides when nothing renders.
 * ========================================================================== */
(() => {
  "use strict";

  const esc = (s) =>
    String(s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  /* Subjects that naturally study together — ranks Related Subjects. */
  const AFFINITY = {
    "gk": ["current-affairs", "punjabi"],
    "current-affairs": ["gk", "punjabi"],
    "quant": ["reasoning", "english"],
    "reasoning": ["quant", "computer"],
    "punjabi": ["english", "gk"],
    "english": ["punjabi", "reasoning"],
    "computer": ["reasoning", "quant"],
  };

  const fetchJSON = (url) =>
    fetch(url, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);

  /* --------------------------------------------------------- subjects ----- */
  /** All subjects except the one being viewed; affinity pairs first. */
  function relatedSubjects(index, subjectId) {
    const subs = (index.subjects || []).filter((s) => s.id !== subjectId);
    const pref = AFFINITY[subjectId] || [];
    return subs.sort((a, b) => {
      const pa = pref.indexOf(a.id), pb = pref.indexOf(b.id);
      const ra = pa === -1 ? 99 : pa, rb = pb === -1 ? 99 : pb;
      return ra - rb || (a.order || 0) - (b.order || 0);
    });
  }

  /* ---------------------------------------------------------- quizzes ----- */
  /** Every available quiz; same-subject (same-category first) floated up. */
  function relatedQuizzes(index, cur) {
    const out = [];
    (index.subjects || []).forEach((s, sIdx) => {
      const add = (t, cat) => {
        if (!t || !t.available) return;
        if (cur.topicId && s.id === cur.subjectId && t.id === cur.topicId &&
            (cat || "") === (cur.categoryId || "")) return; // it's the quiz you're on
        const href = cat
          ? `quiz.html?subject=${encodeURIComponent(s.id)}&topic=${encodeURIComponent(t.id)}&category=${encodeURIComponent(cat)}`
          : `quiz.html?subject=${encodeURIComponent(s.id)}&topic=${encodeURIComponent(t.id)}`;
        let rank;
        if (s.id !== cur.subjectId) rank = 2 + sIdx * 0.01;
        else if (cur.categoryId && cat && cat !== cur.categoryId) rank = 1;
        else rank = 0;
        out.push({ href, name: t.name, count: t.count || 0,
                   icon: s.icon, subjectName: s.name, rank });
      };
      (s.topics || []).forEach((t) => add(t, t.category || ""));
      (s.categories || []).forEach((c) => (c.topics || []).forEach((t) => add(t, c.id)));
    });
    return out.sort((a, b) => a.rank - b.rank); // Array#sort is stable
  }

  /* --------------------------------------------------------- articles ----- */
  /** Guides matching the current subject/category; falls back to all. */
  function relatedArticles(arts, subjectId, categoryId) {
    const scored = (arts.articles || []).map((a, i) => ({
      ...a,
      rank: (a.categories || []).includes(categoryId) ? 0
          : (a.subjects || []).includes(subjectId) ? 1
          : 2,
      spec: (a.subjects || []).length || 99, // narrower guide = more specific
      i,
    })).sort((a, b) => a.rank - b.rank || a.spec - b.spec || a.i - b.i);
    const matched = scored.filter((a) => a.rank < 2);
    return (matched.length ? matched : scored).slice(0, 4);
  }

  /* ---------------------------------------------------------- render ------ */
  const card = (eyebrow, heading, items) =>
    items.length
      ? `<div class="card card-pad">
           <span class="eyebrow">${esc(eyebrow)}</span>
           <h3 style="font-size:clamp(1.05rem,2vw,1.25rem);margin-bottom:12px">${esc(heading)}</h3>
           <ul class="muted" style="display:grid;gap:9px">${items.join("")}</ul>
         </div>`
      : "";

  async function boot() {
    const section = document.getElementById("relatedSection");
    const grid = document.getElementById("relatedGrid");
    if (!section || !grid) return;

    const p = new URLSearchParams(location.search);
    const cur = {
      subjectId: (p.get("subject") || "").trim(),
      categoryId: (p.get("category") || "").trim(),
      topicId: (p.get("topic") || "").trim(),
    };

    const [index, arts] = await Promise.all([
      fetchJSON("data/index.json"),
      fetchJSON("data/articles.json"),
    ]);
    if (!index && !arts) { section.classList.add("hidden"); return; }

    const cards = [];

    if (index) {
      cards.push(card("Neighbourhood", "Related subjects",
        relatedSubjects(index, cur.subjectId).map((s) =>
          `<li><a class="ilink" href="subject.html?subject=${encodeURIComponent(s.id)}">${esc(s.icon)} ${esc(s.name)}</a></li>`)));

      cards.push(card("Keep practising", "Related quizzes",
        relatedQuizzes(index, cur).slice(0, 6).map((q) =>
          `<li><a class="ilink" href="${q.href}">${esc(q.icon)} ${esc(q.name)}</a>
             <span class="text-sm"> · ${esc(q.subjectName)}${q.count ? ` · ${q.count} Q` : ""}</span></li>`)));
    }

    if (arts) {
      cards.push(card("Read next", "Related study guides",
        relatedArticles(arts, cur.subjectId, cur.categoryId).map((a) =>
          `<li><a class="ilink" href="${esc(a.url)}">📖 ${esc(a.title)}</a></li>`)));
    }

    const html = cards.join("");
    if (!html) { section.classList.add("hidden"); return; }
    grid.innerHTML = html;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
