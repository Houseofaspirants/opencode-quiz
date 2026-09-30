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
 *   study.html                          → every subject folder, one grid
 *   study.html?subject=computer         → ONE section: that subject's Study Material
 *   study.html?subject=computer&view=chapters
 *                                       → the category → chapter → part browser
 *   study.html?subject=gk&category=x    → the same browser, filtered (old links
 *                                         keep working: a category URL has
 *                                         always meant "walk the syllabus")
 *
 * Everything is read from data, never hardcoded — no subject, chapter, card,
 * filter or count below is a literal:
 *   • subject folders, names, colours, order, file counts → data/study-manifest.json
 *     (the content build reads content/study-material/<subject>/ and writes it)
 *   • the material itself, its language, dates, size, badges and search
 *     haystack → data/content-manifest.json, filtered to collection
 *     `study-material`
 *   • categories, chapters and parts → data/index.json, derived from the
 *     question folders
 *
 * STEP 5 is enforced here: a subject page shows exactly ONE section headed
 * "Study Material". There is no separate PDFs list, no separate Notes list and
 * no separate Guides list — the reader never chose a file type, so the page
 * never asks them to.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const params = new URLSearchParams(location.search);
  const subjectId = params.get("subject") || "";
  const categoryId = params.get("category") || "";
  const view = params.get("view") || "";
  const wantsChapters = view === "chapters" || !!categoryId;

  const idx = await HOA.loadIndex();
  const siteBase = String((idx.site && idx.site.url) || "").replace(/\/+$/, "");
  const indexSubjects = idx.subjects || [];

  /* The shelf's subject list. Missing is not fatal: an older cached core.js
     simply falls back to the subjects the question tree already knows. */
  let shelf = [];
  if (typeof HOA.loadStudySubjects === "function") {
    try {
      shelf = await HOA.loadStudySubjects();
    } catch {
      shelf = [];
    }
  }

  /* The manifest may legitimately be absent while the content build has not
     run. Only study-material rows are read: everything else in that file
     belongs to another system and must never render on a Study page. */
  let items = [];
  try {
    const res = await fetch("data/content-manifest.json", { cache: "no-cache" });
    if (res.ok) items = (await res.json()).items || [];
  } catch {
    items = [];
  }
  const material = items.filter((it) => it && it.collection === "study-material");

  const rootEl = document.getElementById("studyRoot");
  const subjEl = document.getElementById("studySubject");
  const answerEl = document.getElementById("studyAnswer");

  /* ------------------------------------------------------------- helpers - */
  const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  /** `2026-09-30` → `30 Sep 2026`; anything else is left unstated. */
  const fmtDate = (iso) => {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(iso || ""));
    if (!m) return "";
    return `${Number(m[3])} ${MONTHS[Number(m[2]) - 1]} ${m[1]}`;
  };

  /** Bytes → `2.0 MB` / `412 KB`, the same shape the build prints. */
  const fmtSize = (n) => {
    const bytes = Number(n) || 0;
    if (!bytes) return "";
    return bytes < 1024 * 1024
      ? `${Math.max(1, Math.round(bytes / 1024))} KB`
      : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  /** The one string search matches against — build-produced, already lowercase. */
  const haystack = (it) =>
    String(it.search ||
      [it.title, it.description, it.file, it.category, it.subjectName,
       (it.keywords || []).join(" ")].join(" ")).toLowerCase();

  /* STEP 7: Featured → Newest → Alphabetical. Recomputed here rather than
     trusted from the file so the shelf, the hub page and this renderer can
     never drift apart — and so a cache serving an older manifest still lists
     in the order the brief asks for. */
  const byShelfOrder = (a, b) => {
    const fa = a.featured ? 0 : 1;
    const fb = b.featured ? 0 : 1;
    if (fa !== fb) return fa - fb;
    const da = String(a.updated || a.published || "");
    const db = String(b.updated || b.published || "");
    if (da !== db) return da < db ? 1 : -1;
    return String(a.title || "").toLowerCase()
      .localeCompare(String(b.title || "").toLowerCase());
  };

  const BADGE = {
    featured: ["badge-success", "Featured"],
    new: ["badge-warn", "New"],
    popular: ["badge-muted", "Popular"],
  };

  /* STEP 6 in one markup block — identical to the card the build prints on
     study-material.html, so a reader sees the same six fields whichever door
     they came through. */
  const materialCard = (it) => {
    const badges = (Array.isArray(it.badges) ? it.badges : [])
      .map((b) => BADGE[String(b)])
      .filter(Boolean)
      .map(([cls, label]) => `<span class="badge ${cls}">${label}</span>`)
      .join("");
    const lang = it.language === "pa" ? "ਪੰਜਾਬੀ" : "English";
    const meta = [lang];
    const when = fmtDate(it.updated || it.published);
    if (when) meta.push(`Updated ${when}`);
    if (it.readingMinutes) meta.push(`${it.readingMinutes} min read`);
    if (it.sizeLabel) meta.push(String(it.sizeLabel));
    // The path, not an absolute URL: every other file link on the site is
    // relative, so this works from a preview build and from production.
    const src = String(it.path || it.source || "");
    const btn = src && it.type === "pdf"
      ? `<a class="btn btn-primary" href="${esc(src)}" download>⬇ Download</a>`
      : src ? `<a class="btn btn-soft" href="${esc(src)}">Open file</a>` : "";
    return `
      <div class="card card-pad study-card">
        ${badges ? `<div class="card-badges">${badges}</div>` : ""}
        <span class="eyebrow">${esc(it.category || it.subjectName || "Study Material")}</span>
        <h3><a href="${esc(it.file)}">${esc(it.title)}</a></h3>
        <p class="muted">${esc(it.description || "")}</p>
        <p class="study-meta">${esc(meta.join(" · "))}</p>
        ${btn ? `<p class="btn-row" style="margin-top:14px">${btn}</p>` : ""}
      </div>`;
  };

  const emptyState = (q) => `
    <div class="empty-state">
      <div class="es-icon">📖</div>
      <h3>${q ? "Nothing matches that" : "Nothing filed here yet"}</h3>
      <p>${q
        ? "No file in this subject carries that word. Try the title, the subject or a keyword."
        : "Drop a file into this subject's folder and it appears here on the next build — no page to write."}</p>
      ${q ? "" : `<p class="mt-2"><a class="btn btn-soft" href="study-material.html">All study material →</a></p>`}
    </div>`;

  /** Per-subject head tags + JSON-LD, so a subject URL has its own identity. */
  const setSubjectSeo = (name, count) => {
    const url = `${siteBase}/study?subject=${encodeURIComponent(subjectId)}`;
    const desc = `${count} file${count === 1 ? "" : "s"} of free ${name} study material for Punjab competitive exams — PDFs, notes and downloads, with language, last update and reading time on every card.`;
    if (typeof (/** @type {any} */ (HOA).seo) === "function") {
      (/** @type {any} */ (HOA).seo)({
        title: `${name} Study Material | House of Aspirants`,
        canonical: url,
        description: desc,
        ogTitle: `${name} Study Material | House of Aspirants`,
        ogDescription: desc,
      });
    }
    document.querySelectorAll('script[data-study-entity="subject"]')
      .forEach((n) => n.remove());
    const s = document.createElement("script");
    s.type = "application/ld+json";
    s.dataset.studyEntity = "subject";
    s.textContent = JSON.stringify({
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "CollectionPage",
          "@id": `${url}#webpage`,
          url,
          name: `${name} Study Material | House of Aspirants`,
          description: desc,
          isPartOf: { "@id": `${siteBase}/#website` },
          breadcrumb: { "@id": `${url}#breadcrumb` },
          inLanguage: "en-IN",
        },
        {
          "@type": "BreadcrumbList",
          "@id": `${url}#breadcrumb`,
          itemListElement: [
            { "@type": "ListItem", position: 1, name: "Home", item: `${siteBase}/` },
            { "@type": "ListItem", position: 2, name: "Study", item: `${siteBase}/study` },
            { "@type": "ListItem", position: 3, name, item: url },
          ],
        },
      ],
    }, null, 2);
    document.head.appendChild(s);
  };

  /* ============================================================== SUBJECT == */
  if (subjectId) {
    const shelfSubject = shelf.find((r) => r && r.id === subjectId);
    const indexSubject = indexSubjects.find((s) => s.id === subjectId);
    const name = (shelfSubject && shelfSubject.name) ||
                 (indexSubject && indexSubject.name) || subjectId;
    const blurb = (shelfSubject && shelfSubject.description) ||
                  (indexSubject && indexSubject.description) || "";

    if (!shelfSubject && !indexSubject) {
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
    if (answerEl) answerEl.hidden = true;

    const crumb = document.getElementById("studyBreadcrumb");
    if (crumb) {
      crumb.innerHTML =
        `<a href="index.html">Home</a><span>/</span><a href="study.html">Study</a>` +
        `<span>/</span><span>${esc(name)}</span>`;
    }

    const subjectItems = material
      .filter((it) => String(it.studySubject || "") === subjectId)
      .sort(byShelfOrder);

    /* Head copy. STEP 5: the heading is exactly "Study Material" in the
       material view, and only the chapter browser renames it. */
    // The subject owns the <h1> here, so a shelf URL, the breadcrumb and the
    // page heading all say the same word and no two headings on the page
    // carry the same text.
    const title = document.getElementById("studyTitle");
    if (title) title.textContent = name;
    const lead = document.getElementById("studyLead");
    if (lead) {
      lead.textContent =
        `Every file filed under ${name} — PDFs, notes and downloads together, ` +
        `featured and newest first. Reading only — the questions for this ` +
        `subject live on the Practice door.`;
    }
    const eyebrow = document.getElementById("studySubjectEyebrow");
    if (eyebrow) {
      eyebrow.textContent =
        `${subjectItems.length} file${subjectItems.length === 1 ? "" : "s"}` +
        (blurb ? ` · ${blurb}` : "");
    }
    const head = document.getElementById("studySubjectHead");
    if (head) head.textContent = wantsChapters ? `Chapters in ${name}` : "Study Material";
    const desc = document.getElementById("studySubjectDesc");
    if (desc) {
      desc.textContent = wantsChapters
        ? "Choose a category, then a chapter, then a part. Each part carries the notes that belong to it."
        : `${subjectItems.length} file${subjectItems.length === 1 ? "" : "s"}, ` +
          `searchable by title, keyword or file name. Nothing is split by format — ` +
          `every kind of material is listed here together.`;
    }
    const back = document.getElementById("studySubjectBack");
    if (back instanceof HTMLAnchorElement) back.href = "study.html";

    setSubjectSeo(name, subjectItems.length);

    const chaptersLink = document.getElementById("studyChapters");
    if (chaptersLink instanceof HTMLAnchorElement) {
      chaptersLink.href = `study.html?subject=${encodeURIComponent(subjectId)}&view=chapters`;
      chaptersLink.textContent = "Browse chapters →";
    }

    const matWrap = document.getElementById("studyMaterial");
    const chaptersWrap = document.getElementById("studyChaptersBody");

    /* ------------------------------------------------- chapter browser --- */
    const renderChapters = () => {
      if (!chaptersWrap) return;
      if (matWrap) matWrap.hidden = true;
      chaptersWrap.hidden = false;
      if (chaptersLink instanceof HTMLAnchorElement) {
        chaptersLink.href = `study.html?subject=${encodeURIComponent(subjectId)}`;
        chaptersLink.textContent = "← Back to Study Material";
        chaptersLink.hidden = false;
      }
      if (!indexSubject) {
        chaptersWrap.innerHTML = `
          <div class="empty-state">
            <div class="es-icon">🧭</div>
            <h3>No chapter tree for ${esc(name)} yet</h3>
            <p>This subject has no question tree yet, so there is no
               category → chapter → part path to walk. Everything it holds is
               listed under Study Material.</p>
            <p class="mt-2"><a class="btn btn-primary" href="study.html?subject=${esc(subjectId)}">Back to Study Material</a></p>
          </div>`;
        return;
      }
      const cats = categoryId
        ? indexSubject.categories.filter((c) => c.id === categoryId)
        : indexSubject.categories;
      if (!cats.length) {
        chaptersWrap.innerHTML = `
          <div class="empty-state">
            <div class="es-icon">📖</div>
            <h3>Nothing filed here yet</h3>
            <p>That category has no chapters in the index. Try another one.</p>
            <p class="mt-2"><a class="btn btn-primary" href="study.html?subject=${esc(subjectId)}&amp;view=chapters">All categories</a></p>
          </div>`;
        return;
      }
      chaptersWrap.innerHTML = cats.map((cat) => {
        const groups = new Map();
        indexSubject.topics
          .filter((t) => t.category === cat.id)
          .forEach((t) => {
            const key = chapterKey(t.id);
            if (!groups.has(key)) {
              groups.set(key, { key, name: chapterName(t.name), parts: [] });
            }
            groups.get(key).parts.push(t);
          });
        const cards = [...groups.values()].map((g) => {
          const parts = g.parts.map((p) => `<li>
              <span class="part-name">${esc(p.name)}</span>
              <span class="part-meta">${(p.availableLanguages || []).length} language(s) · ${p.count || 0} Q</span>
            </li>`).join("");
          return `
            <article class="card card-pad" style="--sc:${esc(indexSubject.color)}">
              <span class="eyebrow">Chapter</span>
              <h3>${esc(g.name)}</h3>
              <p class="part-count">${g.parts.length} part${g.parts.length === 1 ? "" : "s"}</p>
              <ul class="part-list">${parts}</ul>
            </article>`;
        }).join("");
        return `
          <section class="study-cat">
            <div class="section-head">
              <div>
                <span class="eyebrow">Category</span>
                <h3>${esc(cat.icon || "📁")} ${esc(cat.name)}</h3>
                <p>${groups.size} chapter${groups.size === 1 ? "" : "s"}</p>
              </div>
            </div>
            <div class="grid grid-2">${cards}</div>
          </section>`;
      }).join("");
    };

    /* --------------------------------------------------- the one section - */
    const renderMaterial = (q) => {
      if (!chaptersWrap) return;
      if (matWrap) matWrap.hidden = false;
      chaptersWrap.hidden = true;
      const query = q.trim().toLowerCase();
      const shown = query
        ? subjectItems.filter((it) => haystack(it).includes(query))
        : subjectItems;
      const body = document.getElementById("studyMaterialBody");
      if (body) {
        body.innerHTML = shown.length
          ? shown.map(materialCard).join("")
          : emptyState(query);
      }
      const count = document.getElementById("studyMaterialCount");
      if (count) {
        count.textContent = query
          ? `${shown.length} of ${subjectItems.length} file(s) match “${q.trim()}”`
          : `${subjectItems.length} file${subjectItems.length === 1 ? "" : "s"} · ` +
            `${subjectItems.filter((i) => i.featured).length} featured · ` +
            `${subjectItems.filter((i) => i.badges && i.badges.includes("new")).length} new`;
      }
    };

    const search = document.getElementById("studySearch");
    if (search) {
      search.addEventListener("input", () => {
        if (wantsChapters) return;
        renderMaterial(String(/** @type {HTMLInputElement} */ (search).value));
      });
    }

    if (wantsChapters) renderChapters();
    else renderMaterial("");
    return;
  }

  /* ================================================================ ROOT === */
  const grid = document.getElementById("studySubjects");
  if (!grid) return;

  if (subjEl) subjEl.hidden = true;
  if (rootEl) rootEl.hidden = false;

  /* One grid, from the manifest. A folder with no files still earns a card —
     that is where the next file goes — and it says so plainly rather than
     pretending there is something to read. */
  const rows = shelf.length
    ? shelf
    : indexSubjects.map((s) => ({
        id: s.id, name: s.name, icon: s.icon, color: s.color,
        description: s.description, order: 0, count: 0, newest: "",
        totalSize: 0,
      }));

  grid.innerHTML = rows.map((r) => {
    const n = Number(r.count) || 0;
    const newest = fmtDate(r.newest);
    return `
      <a class="card subject-card" style="--sc:${esc(r.color || "#4f46e5")}"
         href="study.html?subject=${esc(r.id)}">
        <span class="subject-icon">${esc(r.icon || "📚")}</span>
        <h3>${esc(r.name)}</h3>
        <p>${esc(r.description || "Notes, PDFs and downloads for this subject.")}</p>
        <div class="subject-meta">
          <span class="badge ${n ? "badge-success" : "badge-muted"}">${n} file${n === 1 ? "" : "s"}</span>
          ${newest ? `<span class="badge badge-muted">Updated ${newest}</span>` : ""}
          ${r.totalSize ? `<span class="badge badge-muted">${fmtSize(r.totalSize)}</span>` : ""}
        </div>
      </a>`;
  }).join("");

  const meta = document.getElementById("studySubjectsMeta");
  if (meta) {
    const total = rows.reduce((n, r) => n + (Number(r.count) || 0), 0);
    meta.textContent = total
      ? `${rows.length} subject${rows.length === 1 ? "" : "s"} · ${total} file${total === 1 ? "" : "s"} of study material · free, no sign-up`
      : `${rows.length} subject${rows.length === 1 ? "" : "s"} · material publishes as it is added`;
  }
})();

/** "Sikhism (Sikh Dharam) - Part 3" → "Sikhism (Sikh Dharam)" (chapter). */
function chapterName(name) {
  return String(name || "").replace(/\s*[-–—]\s*Part\s*\d+\s*$/i, "").trim()
    || String(name || "");
}
/** `sikhism-part3-20-mcqs` → `sikhism` (chapter key). */
function chapterKey(id) {
  return String(id || "").replace(/-part\d+(?=-|$)/i, "").trim()
    || String(id || "");
}
