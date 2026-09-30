// @ts-check
/* ============================================================================
 * study.js | The STUDY system — root view + subject view
 * ----------------------------------------------------------------------------
 * Study is the reading half of the platform and it is deliberately closed:
 * NOTHING this file renders links to a quiz, a mock, an Expected-MCQ set or a
 * practice page. Questions belong to Practice; if you want them, use the
 * Practice door in the header. Keeping that boundary in one file makes it
 * impossible to leak a test into a notes page.
 *
 *   study.html                       → the seven subjects
 *   study.html?subject=gk            → that subject's CATEGORIES
 *   study.html?subject=gk&category=x → that category's CHAPTERS and PARTS
 *
 * Everything is read from data, never hardcoded:
 *   • subjects, categories and chapters → data/index.json (the build detects
 *     the folders and JSON files; add one and a card appears, delete one and
 *     it goes away).
 *   • chapters and parts                → derived from chapter/topic ids, so a
 *     topic named `sikhism-part2-…` folds under the `Sikhism` chapter without
 *     anyone maintaining a list.
 *   • study notes, PDFs and revision sheets → data/content-manifest.json,
 *     joined on the item's own `subjects`/`category` front matter. Author a
 *     .md in content/notes/ and it shows up here with no code change; today
 *     most shelves are empty and say so plainly instead of pretending.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const params = new URLSearchParams(location.search);
  const subjectId = params.get("subject") || "";
  const categoryId = params.get("category") || "";

  const idx = await HOA.loadIndex();
  const siteBase = String((idx.site && idx.site.url) || "").replace(/\/+$/, "");
  const subjects = idx.subjects || [];

  /** Manifest may legitimately be absent while the content build has not run. */
  let items = [];
  try {
    const res = await fetch("data/content-manifest.json", { cache: "no-cache" });
    if (res.ok) items = (await res.json()).items || [];
  } catch {
    items = [];
  }

  const rootEl = document.getElementById("studyRoot");
  const subjEl = document.getElementById("studySubject");

  const setCanonical = (href) => {
    let link = document.querySelector('link[rel="canonical"]');
    if (!link) {
      link = document.createElement("link");
      link.setAttribute("rel", "canonical");
      document.head.appendChild(link);
    }
    link.setAttribute("href", href);
  };

  /* --------------------------------------------------------------- helpers */
  /** "Sikhism (Sikh Dharam) - Part 3" → "Sikhism (Sikh Dharam)" (chapter). */
  const chapterName = (name) =>
    String(name || "").replace(/\s*[-–—]\s*Part\s*\d+\s*$/i, "").trim() || String(name || "");
  /** `sikhism-part3-20-mcqs` → `sikhism` (chapter key). */
  const chapterKey = (id) =>
    String(id || "").replace(/-part\d+(?=-|$)/i, "").trim() || String(id || "");

  /** Does this manifest item belong to this subject/category? Data, not taste. */
  const materialMatches = (it, s, catId) => {
    const subs = Array.isArray(it.subjects) ? it.subjects : it.subjects ? [it.subjects] : [];
    const sOk = subs.some(
      (v) => String(v).toLowerCase() === s.id.toLowerCase() ||
             String(v).toLowerCase() === String(s.name).toLowerCase()
    );
    if (!sOk) return false;
    if (!catId) return true;
    const c = String(it.category || "").toLowerCase();
    return c === catId.toLowerCase() || c === String(s.name).toLowerCase();
  };

  const materialList = (s, catId) =>
    items.filter((it) => materialMatches(it, s, catId));

  /** One material row — notes, PDF and revision shelves all render the same. */
  const materialRow = (it) => `
    <a class="card card-pad" href="${esc(it.file)}">
      <span class="eyebrow">${esc(it.collection === "pdfs" ? "PDF" : "Study notes")}</span>
      <h3>${esc(it.title)}</h3>
      <p class="ilink">Read →</p>
    </a>`;

  /* ============================================================== SUBJECT == */
  if (subjectId) {
    const subject = subjects.find((s) => s.id === subjectId);

    if (!subject) {
      if (rootEl) rootEl.hidden = false;
      if (subjEl) subjEl.hidden = true;
      const t = document.getElementById("studyTitle");
      if (t) t.textContent = "Subject not found";
      const l = document.getElementById("studyLead");
      if (l) l.textContent = "That subject is not in the index yet. Pick one from the list below.";
      return;
    }

    if (rootEl) rootEl.hidden = true;
    if (subjEl) subjEl.hidden = false;

    const crumb = document.getElementById("studyBreadcrumb");
    if (crumb) {
      crumb.innerHTML =
        `<a href="index.html">Home</a><span>/</span><a href="study.html">Study</a>` +
        `<span>/</span><span>${esc(subject.name)}</span>`;
    }
    const title = document.getElementById("studyTitle");
    if (title) title.textContent = `${subject.name} — Study Material`;
    const lead = document.getElementById("studyLead");
    if (lead) {
      lead.textContent =
        `${subject.description || `Everything written for ${subject.name}, `}` +
        `arranged by category, chapter and part. Reading only — the questions for this subject live on the Practice door.`;
    }
    document.title = `${subject.name} Study Notes, Chapters & PDFs | House of Aspirants`;
    setCanonical(`${siteBase}/study?subject=${encodeURIComponent(subject.id)}`);

    const head = document.getElementById("studySubjectHead");
    if (head) head.textContent = `Chapters in ${subject.name}`;
    const eyebrow = document.getElementById("studySubjectEyebrow");
    if (eyebrow) eyebrow.textContent = `${subject.categories.length} categories`;
    const desc = document.getElementById("studySubjectDesc");
    if (desc) {
      const chapters = new Set(subject.topics.map((t) => chapterKey(t.id)));
      desc.textContent =
        `${chapters.size} chapter${chapters.size === 1 ? "" : "s"} across ` +
        `${subject.categories.length} categor${subject.categories.length === 1 ? "y" : "ies"} — open a category, ` +
        `then a chapter, then a part. Each one carries its notes, a PDF and its revision sheet.`;
    }
    const back = document.getElementById("studySubjectBack");
    if (back instanceof HTMLAnchorElement) {
      back.href = categoryId ? `study.html?subject=${encodeURIComponent(subject.id)}` : "study.html";
      back.textContent = categoryId ? `All ${subject.name} categories →` : "All subjects →";
    }

    const body = document.getElementById("studySubjectBody");
    if (!body) return;

    /* Filter to one category when the URL asks for it. */
    const cats = categoryId
      ? subject.categories.filter((c) => c.id === categoryId)
      : subject.categories;

    if (!cats.length) {
      body.innerHTML = `
        <div class="empty-state">
          <div class="es-icon">📖</div>
          <h3>Nothing filed here yet</h3>
          <p>That category has no chapters in the index. Try another one.</p>
          <p class="mt-2"><a class="btn btn-primary" href="study.html?subject=${esc(subject.id)}">All categories</a></p>
        </div>`;
      return;
    }

    const allMaterial = materialList(subject, "");

    body.innerHTML = cats
      .map((cat) => {
        /* Group this category's topics into chapters, then chapters into parts. */
        const groups = new Map();
        subject.topics
          .filter((t) => t.category === cat.id)
          .forEach((t) => {
            const key = chapterKey(t.id);
            if (!groups.has(key)) {
              groups.set(key, { key, name: chapterName(t.name), parts: [], notes: [] });
            }
            groups.get(key).parts.push(t);
          });

        const chapterCards = [...groups.values()]
          .map((g) => {
            const material = allMaterial.filter(
              (it) => materialMatches(it, subject, cat.id)
            );
            const parts = g.parts
              .map((p) => {
                const lang = (p.availableLanguages || []).length;
                const qCount = p.count || 0;
                return `<li>
                  <span class="part-name">${esc(p.name)}</span>
                  <span class="part-meta">${lang} language${lang === 1 ? "" : "s"}</span>
                </li>`;
              })
              .join("");

            /* NOTES for this chapter — filtered to what actually exists. */
            const notes = material
              .filter((it) => chapterName(it.title).toLowerCase().includes(g.name.toLowerCase()))
              .map(materialRow)
              .join("");

            return `
              <article class="card card-pad" style="--sc:${subject.color}">
                <span class="eyebrow">Chapter</span>
                <h3>${esc(g.name)}</h3>
                <p class="part-count">${g.parts.length} part${g.parts.length === 1 ? "" : "s"}</p>
                <ul class="part-list">${parts}</ul>
                ${
                  notes
                    ? `<div class="material-grid">${notes}</div>`
                    : `<p class="material-empty">No published note for this chapter yet — the
                         <a href="study-notes.html">Study notes shelf</a>,
                         <a href="pdfs.html">PDF shelf</a> and
                         <a href="topic-guides.html">topic guides</a> carry what exists today.</p>`
                }
              </article>`;
          })
          .join("");

        const catMaterial = materialList(subject, cat.id);
        const shelf = catMaterial.length
          ? `<div class="material-grid">${catMaterial.map(materialRow).join("")}</div>`
          : "";

        return `
          <section class="study-cat">
            <div class="section-head">
              <div>
                <span class="eyebrow">Category</span>
                <h3>${cat.icon || "📁"} ${esc(cat.name)}</h3>
                <p>${groups.size} chapter${groups.size === 1 ? "" : "s"} · ${
                  shelf ? `${catMaterial.length} published note${catMaterial.length === 1 ? "" : "s"}` : "no published notes yet"
                }</p>
              </div>
            </div>
            ${shelf}
            <div class="grid grid-2">${chapterCards}</div>
          </section>`;
      })
      .join("");
    return;
  }

  /* ================================================================ ROOT === */
  const grid = document.getElementById("studySubjects");
  if (!grid) return;

  const notesFor = (s) => items.filter((it) => materialMatches(it, s, "")).length;

  grid.innerHTML = subjects
    .slice()
    .sort((a, b) => (a.order || 0) - (b.order || 0))
    .map((s) => {
      const chapters = new Set(s.topics.map((t) => chapterKey(t.id))).size;
      const notes = notesFor(s);
      return `
        <a class="card subject-card" style="--sc:${s.color}" href="study.html?subject=${esc(s.id)}">
          <span class="subject-icon">${s.icon}</span>
          <h3>${esc(s.name)}</h3>
          <p>${esc(s.description || "Notes, PDFs and revision sheets for this subject.")}</p>
          <div class="subject-meta">
            <span class="badge">${s.categories.length} categor${s.categories.length === 1 ? "y" : "ies"}</span>
            <span class="badge badge-muted">${chapters} chapter${chapters === 1 ? "" : "s"}</span>
            <span class="badge ${notes ? "badge-success" : "badge-muted"}">${notes} note${notes === 1 ? "" : "s"}</span>
          </div>
        </a>`;
    })
    .join("");
})();
