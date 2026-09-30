// @ts-check
/* ============================================================================
 * study.js | The STUDY system — subject → language → chapter → part
 * ----------------------------------------------------------------------------
 * Study is the reading half of the platform and it is deliberately closed:
 * NOTHING this file renders links to a quiz, a mock, an Expected-MCQ set or a
 * practice page. Questions belong to Practice; if you want them, use the
 * Practice door in the header. Keeping that boundary in one file makes it
 * impossible to leak a test into a notes page.
 *
 *   study.html                              → every subject folder, one grid
 *   study.html?subject=computer             → the subject's LANGUAGE CARDS
 *                                             (nothing else is listed yet)
 *   study.html?subject=computer&language=pa → that language's CHAPTERS
 *   study.html?subject=computer&language=pa&chapter=fundamentals-of-computer
 *                                           → that chapter's PARTS, in order
 *   ...&chapter=x  →  a part opens as its own page (material-*.html), which
 *                     carries Read Online, Download, Related Chapters and the
 *                     part before and after it
 *
 * Old links keep working: `&category=x` has always meant "walk the syllabus"
 * and `&view=chapters` has always meant "show me the chapters". Both are
 * resolved against the same folder tree, so neither is a special case.
 *
 * Everything is read from data, never hardcoded — no subject, language,
 * chapter, part, card, filter or count below is a literal:
 *   • subject folders, names, colours, order, counts, and the whole
 *     language → chapter → part tree → data/study-manifest.json (written by
 *     scripts/study_material.py, which walks
 *     content/study-material/<subject>/<language>/<chapter>/<part file>)
 *   • the material itself — title, description, language, dates, size,
 *     badges, reading time and search haystack → data/content-manifest.json,
 *     filtered to collection `study-material` and joined by `file`
 *
 * STEP 5 is enforced here: a subject page shows exactly ONE section. It is
 * never split into a PDFs list, a Notes list or a Guides list — the reader
 * never chose a file type, so the page never asks them to.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const params = new URLSearchParams(location.search);
  const subjectId = params.get("subject") || "";
  const langParam = params.get("language") || "";
  const chapterParam = params.get("chapter") || "";
  const categoryId = params.get("category") || "";
  const view = params.get("view") || "";

  const idx = await HOA.loadIndex();
  const siteBase = String((idx.site && idx.site.url) || "").replace(/\/+$/, "");
  const indexSubjects = idx.subjects || [];

  /* The shelf's subject list — and, inside each row, the whole
     language → chapter → part tree the content build found on disk. Missing
     is not fatal: an older cached core.js simply falls back to the subjects
     the question tree already knows, and those show an empty shelf rather
     than a broken one. */
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
  const byFile = new Map(material.map((it) => [String(it.file), it]));

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
       it.studyChapterName, it.studyLanguageName,
       (it.keywords || []).join(" ")].join(" ")).toLowerCase();

  const plural = (n, word) => `${n} ${word}${n === 1 ? "" : "s"}`;

  /** `plural` only knows how to append an "s", so words that do not obey it
      — category/categories, page/pages — name both forms themselves. */
  const many = (n, one, few) => `${n} ${n === 1 ? one : few}`;

  /** Chapters in a category that none of its declared sub heads has claimed.
      A head list is a grouping, not a filter: anything it misses stays on the
      category page rather than disappearing. */
  const unclaimedChapters = (cat) => {
    const claimed = new Set(
      Array.isArray(cat && cat.claimedChapters) ? cat.claimedChapters : []);
    const out = [];
    const seen = new Set();
    ((cat && Array.isArray(cat.languages)) ? cat.languages : []).forEach((l) =>
      (l.chapters || []).forEach((c) => {
        if (!claimed.has(c.id) && !seen.has(c.id)) {
          seen.add(c.id);
          out.push(c);
        }
      }));
    return out;
  };

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

  /** A part, as the content build describes it: the tree supplies the `file`
      and the card fields all come from the manifest row behind it. */
  const partItem = (part) =>
    byFile.get(String(part && part.file)) || {
      file: String((part && part.file) || ""),
      title: "",
      description: "",
      badges: [],
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
    const lang = it.studyLanguageName || it.languageName ||
      (it.language === "pa" ? "ਪੰਜਾਬੀ" : "English");
    const meta = [lang];
    if (it.studyChapterName) meta.push(String(it.studyChapterName));
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

  const emptyState = (icon, title, body, action) => `
    <div class="empty-state">
      <div class="es-icon">${icon}</div>
      <h3>${title}</h3>
      <p>${body}</p>
      ${action || ""}
    </div>`;

  /* ------------------------------------------------------- saved chapters -
     Study keeps its own bookmarks. `HOA.bookmarks` stores saved *questions*
     and renders them as question cards with a "Show answer" button, so a
     chapter saved there would land as an empty card; these live on the
     device, under Study, and are listed again at the top of any chapter
     list so a star always leads somewhere. Nothing leaves the browser. */
  const SAVED_KEY = "hoa.study.savedChapters";

  const savedChapters = () => {
    try {
      const v = JSON.parse(localStorage.getItem(SAVED_KEY) || "[]");
      return Array.isArray(v) ? v.filter((b) => b && b.key && b.href) : [];
    } catch {
      return [];
    }
  };

  /** false when storage is unavailable (private mode): the star still
      toggles for this page view, it just will not be waiting tomorrow. */
  const writeSaved = (list) => {
    try {
      localStorage.setItem(SAVED_KEY, JSON.stringify(list.slice(0, 200)));
      return true;
    } catch {
      return false;
    }
  };

  const toggleSaved = (entry) => {
    const list = savedChapters();
    const i = list.findIndex((b) => b.key === entry.key);
    if (i >= 0) {
      list.splice(i, 1);
      writeSaved(list);
      return false;
    }
    list.unshift(entry);
    writeSaved(list);
    return true;
  };

  /* --------------------------------------------------------- shared cards ---
     The three cards every step of Study is built from. They live up here
     rather than inside the subject branch so a deeper branch - General
     Knowledge's Region -> Category -> Sub Category steps - renders exactly
     the same markup a plain subject does. One card, one place, one look. */

  /** A language card: flag, name, what is inside it, and the two counts. */
  const languageCard = (l, href, color) => {
    const chs = l.chapters || [];
    const ch = chs.length;
    const n = Number(l.count) || 0;
    // The counts live in the badges; this line says *what* is here — the
    // chapters themselves — so the card never prints the same fact twice.
    const names = chs.slice(0, 3).map((c) => c.name).join(", ");
    const under = n
      ? (names ? `${names}${chs.length > 3 ? ` and ${chs.length - 3} more` : ""}` : `${plural(ch, "chapter")}`)
      : `No chapters in ${l.name} yet.`;
    return `
        <a class="card lang-card" style="--sc:${esc(color)}"
           href="${esc(href)}">
          <span class="lang-flag" aria-hidden="true">${esc(l.flag || "🌐")}</span>
          <h3>${esc(l.name)}</h3>
          ${l.native && l.native !== l.name
            ? `<p class="lang-native">${esc(l.native)}</p>` : ""}
          <p class="muted">${esc(under)}</p>
          <div class="subject-meta">
            <span class="badge ${ch ? "badge-success" : "badge-muted"}">${plural(ch, "chapter")}</span>
            <span class="badge ${n ? "badge-success" : "badge-muted"}">${plural(n, "file")}</span>
          </div>
        </a>`;
  };

  /* A chapter card. Without `opts` it is the plain card every subject has
     always had. With them — General Knowledge's hierarchy, and only there —
     it is the full card the brief asks for: chapter number, title, estimated
     reading time, pages, last updated, available languages, a bookmark and
     the PDF itself. Every one of those numbers is read off the part rows the
     build published, so the card cannot claim a page nobody uploaded. */
  const chapterCard = (c, href, langName, opts) => {
    const parts = (c.parts || []).length;
    if (!opts) {
      return `
        <a class="card card-pad study-card" href="${esc(href)}">
          <span class="eyebrow">${esc(langName)} · Chapter</span>
          <h3>${esc(c.name)}</h3>
          <p class="muted">${plural(parts, "part")}, in reading order.</p>
          <p class="study-meta">${esc(langName)} · ${plural(parts, "part")}</p>
        </a>`;
    }

    const rows = (c.parts || []).map(partItem);
    const mins = rows.reduce((s, p) => s + (Number(p.readingMinutes) || 0), 0);
    const updated = rows
      .map((p) => String(p.updated || p.published || "").slice(0, 10))
      .filter(Boolean).sort().slice(-1)[0] || "";
    const pages = Number(c.pages) || 0;
    const withLangs = Array.isArray(opts.languages) ? opts.languages : [];
    const pdf = rows.find((p) => p.type === "pdf" && (p.path || p.source));
    const src = String((pdf && (pdf.path || pdf.source)) || "");
    const key = href;
    const saved = savedChapters().some((b) => b.key === key);
    const badges = [
      `<span class="badge ${saved ? "badge-success" : "badge-muted"}">Chapter ${Number(opts.no) || 1} of ${Number(opts.total) || 1}</span>`,
      pages ? `<span class="badge badge-muted">${plural(pages, "page")}</span>` : "",
      mins ? `<span class="badge badge-muted">${mins} min read</span>` : "",
      updated ? `<span class="badge badge-muted">Updated ${fmtDate(updated)}</span>` : "",
      withLangs.length
        ? `<span class="badge badge-muted">🌐 ${esc(withLangs.join(", "))}</span>` : "",
    ].filter(Boolean).join("");
    return `
        <div class="card card-pad study-card">
          <div class="card-badges">${badges}</div>
          <span class="eyebrow">${esc(langName)} · Chapter</span>
          <h3><a href="${esc(href)}">${esc(c.name)}</a></h3>
          <p class="muted">${plural(parts, "part")}, in reading order${src ? " — Open PDF starts at Part 1" : ""}.</p>
          <p class="study-meta">${esc(langName)} · ${plural(parts, "part")}${pages ? ` · ${plural(pages, "page")}` : ""}</p>
          <p class="btn-row" style="margin-top:14px">
            ${src
              ? `<a class="btn btn-primary st-act" href="${esc(src)}">Open PDF</a>`
              : `<a class="btn btn-soft st-act" href="${esc(href)}">Read online</a>`}
            <button type="button" class="btn btn-soft st-act"
                    data-study-bookmark="${esc(key)}"
                    data-study-title="${esc(c.name)}"
                    aria-pressed="${saved ? "true" : "false"}">${saved ? "★ Saved" : "☆ Save"}</button>
          </p>
        </div>`;
  };

  /** The reader's own saved chapters, as one strip across the top of a
      chapter list. Absent entirely when there are none, so a first visit
      sees the same page it always did. */
  const savedStrip = () => {
    const list = savedChapters();
    if (!list.length) return "";
    return `
        <div class="st-saved">
          <p class="eyebrow">Saved on this device</p>
          <p class="muted">${plural(list.length, "chapter")} starred — the star on any chapter card adds or removes it here.</p>
          <ul class="st-saved-list">
            ${list.map((b) => `
              <li>
                <a href="${esc(b.href)}">★ ${esc(b.title)}</a>
                <button type="button" class="st-saved-x"
                        data-study-unsave="${esc(b.key)}"
                        aria-label="Remove ${esc(b.title)} from saved chapters">✕</button>
              </li>`).join("")}
          </ul>
        </div>`;
  };

  /** A part, as the content build describes it: the tree supplies the `file`
      and the card fields all come from the manifest row behind it. */
  const partRow = (part) => {
    const it = partItem(part);
    const n = Number(part.n) || 0;
    const badges = (Array.isArray(it.badges) ? it.badges : [])
      .map((b) => BADGE[String(b)]).filter(Boolean)
      .map(([cls, label]) => `<span class="badge ${cls}">${label}</span>`).join("");
    const meta = [];
    if (it.type) meta.push(String(it.type).toUpperCase());
    if (it.sizeLabel) meta.push(String(it.sizeLabel));
    if (it.readingMinutes) meta.push(`${it.readingMinutes} min read`);
    const when = fmtDate(it.updated || it.published);
    if (when) meta.push(`Updated ${when}`);
    return `
        <li>
          <a class="part-row" href="${esc(it.file)}">
            <span class="pr-head">
              <span class="pr-num">Part ${n}</span>
              ${badges ? `<span class="pr-badges">${badges}</span>` : ""}
            </span>
            ${it.description ? `<span class="pr-desc">${esc(it.description)}</span>` : ""}
            ${meta.length ? `<span class="pr-meta">${esc(meta.join(" · "))}</span>` : ""}
          </a>
        </li>`;
  };

  /* ============================================================== SUBJECT == */
  if (subjectId) {
    const shelfSubject = shelf.find((r) => r && r.id === subjectId);
    const indexSubject = indexSubjects.find((s) => s.id === subjectId);
    const name = (shelfSubject && shelfSubject.name) ||
                 (indexSubject && indexSubject.name) || subjectId;

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

    /* --- General Knowledge: one card that holds a shelf of folders ---------
       The manifest marks a subject as a hierarchy when its folders are
       grouped under it, and General Knowledge is the only one today:

           General Knowledge → Region → Category → (Sub Category) → language

       Only those three steps above the language step are new, and only this
       block knows about them. From the language step down every level still
       reads the same folder tree every other subject reads, so a category is
       nothing more than a subject row with a different name in front of it. */
    const hier = (shelfSubject && shelfSubject.hierarchy) || null;
    const ALL_SUBS = "__all__";
    let gRegion = null;
    let gCat = null;
    let gSub = null;
    let gAll = false;
    let hierStep = null; // a card still to choose, or null for a plain step

    if (hier) {
      const regions = Array.isArray(hier.regions) ? hier.regions : [];
      gRegion = regions.find((r) => r && r.id === params.get("region")) || null;
      const cats = gRegion && Array.isArray(gRegion.categories)
        ? gRegion.categories : [];
      gCat = cats.find((c) => c && c.id === params.get("cat")) || null;
      const subs = gCat && Array.isArray(gCat.subCategories)
        ? gCat.subCategories : [];
      const wanted = params.get("sub") || "";
      gSub = subs.find((s) => s && s.id === wanted) || null;
      gAll = wanted === ALL_SUBS;
      if (!gRegion) {
        hierStep = { kind: "region", list: regions, parent: null };
      } else if (!gCat) {
        hierStep = { kind: "category", list: cats, parent: gRegion };
      } else if (subs.length && !gSub && !gAll) {
        // "Everything else" is offered next to the heads so a chapter no head
        // claims is never further away than the ones that do.
        hierStep = { kind: "sub", list: subs, parent: gCat,
                     loose: unclaimedChapters(gCat).length };
      }
    }

    /** The levels already chosen, deepest last. One list feeds the
        breadcrumb, the JSON-LD trail and the head tags, so the three can
        never disagree about where this page says it is. */
    const hierSteps = () => {
      if (!hier) return [];
      const sid = encodeURIComponent(subjectId);
      const at = (q) => `study.html?subject=${sid}${q ? `&${q}` : ""}`;
      const out = [{ name, href: at(""), item: `${siteBase}/study?subject=${sid}` }];
      if (gRegion) {
        const q = `region=${encodeURIComponent(gRegion.id)}`;
        out.push({ name: gRegion.name, href: at(q),
                   item: `${siteBase}/study?subject=${sid}&${q}` });
      }
      if (gCat) {
        const q = `region=${encodeURIComponent(gRegion.id)}` +
                  `&cat=${encodeURIComponent(gCat.id)}`;
        out.push({ name: gCat.name, href: at(q),
                   item: `${siteBase}/study?subject=${sid}&${q}` });
      }
      if (gSub) {
        const q = `region=${encodeURIComponent(gRegion.id)}` +
                  `&cat=${encodeURIComponent(gCat.id)}` +
                  `&sub=${encodeURIComponent(gSub.id)}`;
        out.push({ name: gSub.name, href: at(q),
                   item: `${siteBase}/study?subject=${sid}&${q}` });
      }
      return out;
    };

    /** Every link this page hands out keeps the levels already chosen, so
        drilling down never walks the reader back up to the shelf. */
    const hierQ = [];
    if (hier && gRegion) hierQ.push(`region=${encodeURIComponent(gRegion.id)}`);
    if (hier && gCat) hierQ.push(`cat=${encodeURIComponent(gCat.id)}`);
    if (hier && gSub) hierQ.push(`sub=${encodeURIComponent(gSub.id)}`);
    if (hier && gAll && !gSub) hierQ.push(`sub=${ALL_SUBS}`);

    /** The rows every step below here reads: the node you are standing on,
        or the subject itself. */
    const active = hier ? (gSub || gCat || null) : shelfSubject;
    /** What this step is called in prose — the category you opened, never the
        card the shelf shows. The <h1> stays with the subject. */
    const nodeName = (active && active.name) || name;
    /** The folder a "nothing filed yet" message should point at. */
    const folderId = (hier && gCat && Array.isArray(gCat.folders) && gCat.folders[0])
      ? gCat.folders[0] : subjectId;

    /** The language tree the content build found for this subject. */
    const langs = (active && Array.isArray(active.languages)) ? active.languages : [];
    const subjectCount = hier
      ? Number((active && active.stats && active.stats.files) || 0)
      : Number(shelfSubject && shelfSubject.count) || 0;
    const color = (shelfSubject && shelfSubject.color) || "#4f46e5";

    /* --- which step are we on? -------------------------------------------
       A language must always be chosen before any material is listed, so
       an unknown id, an old `&category=` link or an old `&view=chapters`
       link all resolve to the furthest step they can honestly reach. */
    let languageId = langParam;
    let chapterId = chapterParam;

    if (!hier && !languageId && categoryId) {
      const hits = langs.filter((l) =>
        (l.chapters || []).some((c) => c.id === categoryId));
      if (hits.length === 1) {
        languageId = hits[0].id;
        chapterId = categoryId;
      } else {
        chapterId = "";
      }
    }
    if (!hier && !languageId && view === "chapters") {
      const withChapters = langs.filter((l) => (l.chapters || []).length);
      if (withChapters.length === 1) languageId = withChapters[0].id;
    }

    const lang = langs.find((l) => l.id === languageId);
    if (languageId && !lang) { languageId = ""; chapterId = ""; }
    const chapters = (lang && Array.isArray(lang.chapters)) ? lang.chapters : [];
    const chapter = chapters.find((c) => c.id === chapterId);
    if (chapterId && !chapter) chapterId = "";

    const step = !languageId ? "language" : !chapterId ? "chapter" : "part";
    const langName = (lang && lang.name) || "";
    const chapterName = (chapter && chapter.name) || "";
    const chapterParts = chapter && Array.isArray(chapter.parts) ? chapter.parts : [];

    /* -------------------------------------------------------- page chrome - */
    const hrefFor = (language, ch) => {
      const q = [`subject=${encodeURIComponent(subjectId)}`].concat(hierQ);
      if (language) q.push(`language=${encodeURIComponent(language)}`);
      if (ch) q.push(`chapter=${encodeURIComponent(ch)}`);
      return `study.html?${q.join("&")}`;
    };


    const crumb = document.getElementById("studyBreadcrumb");
    if (crumb) {
      // Every chosen level, deepest last: whoever reads the breadcrumb, the
      // JSON-LD and the head tags sees the same trail because all three are
      // built from this one array.
      const steps = hier ? hierSteps() : [{ name, href: hrefFor(), item: "" }];
      if (langName) steps.push({ name: langName, href: hrefFor(languageId), item: "" });
      if (chapterName) steps.push({ name: chapterName, href: hrefFor(languageId, chapterId), item: "" });
      const trail = [
        `<a href="index.html">Home</a><span>/</span>`,
        `<a href="study.html">Study</a><span>/</span>`,
      ].concat(steps.map((s, i) => i === steps.length - 1
        ? `<span>${esc(s.name)}</span>`
        : `<a href="${esc(s.href)}">${esc(s.name)}</a><span>/</span>`));
      crumb.innerHTML = trail.join("");
    }

    // The subject owns the <h1> here, so a shelf URL, the breadcrumb and the
    // page heading all say the same word and no two headings on the page
    // carry the same text.
    const title = document.getElementById("studyTitle");
    if (title) title.textContent = name;
    const lead = document.getElementById("studyLead");
    if (lead) {
      lead.textContent = hier
        ? `Region → category → language → chapter → part. ${name} is one card ` +
          `over a shelf of folders: open a region, then a category, then the ` +
          `language you want to read it in, then a chapter and its parts in ` +
          `order — online or as a download. Reading only; the questions for ` +
          `this subject live on the Practice door.`
        : `Subject → language → chapter → part. Choose the language you want to ` +
          `read ${name} in, open a chapter, then take its parts in order — ` +
          `online or as a download. Reading only; the questions for this ` +
          `subject live on the Practice door.`;
    }

    const eyebrow = document.getElementById("studyStepEyebrow");
    const head = document.getElementById("studyStepHead");
    const desc = document.getElementById("studyStepDesc");
    const back = document.getElementById("studyBack");
    const tools = document.getElementById("studyTools");
    const count = document.getElementById("studyStepCount");
    const body = document.getElementById("studyStepBody");

    // The eyebrow names where you are inside Study — never repeats the <h1>,
    // and never grows past a fixed set of words however long a subject's
    // blurb is.
    if (eyebrow) {
      eyebrow.textContent = step === "language"
        ? "Study Material"
        : `Study Material · ${langName}`;
    }
    if (head) {
      head.textContent = step === "language" ? "Choose a language"
        : step === "chapter" ? "Chapters"
        : chapterName;
    }
    if (desc) {
      desc.textContent = step === "language"
        ? `Every chapter in ${nodeName} is filed under the language it is written ` +
          `in. Nothing is listed until you choose one.`
        : step === "chapter"
          ? `${plural(chapters.length, "chapter")} published in ${langName} under ` +
             `${nodeName}. Open one to see its parts.`
          : `${plural(chapterParts.length, "part")} in reading order, in ${langName}. ` +
             `Read online or download — the part before and after it is always one tap away.`;
    }
    if (back instanceof HTMLAnchorElement) {
      let backHref = step === "language" ? "study.html"
        : step === "chapter" ? hrefFor()
        : hrefFor(languageId);
      let backLabel = step === "language" ? "← All subjects"
        : step === "chapter" ? "← Choose a language"
        : `← ${langName} chapters`;
      // Inside a hierarchy the previous card is one level up, not the shelf.
      if (step === "language" && hier && gCat) {
        const sid = encodeURIComponent(subjectId);
        backHref = `study.html?subject=${sid}&region=${encodeURIComponent(gRegion.id)}` +
          (gSub ? `&cat=${encodeURIComponent(gCat.id)}` : "");
        backLabel = gSub ? "← Choose a sub category" : "← Choose a category";
      }
      back.href = backHref;
      back.textContent = backLabel;
    }
    if (tools) tools.hidden = step === "language";

    /* ------------------------------------------------------- step bodies -- */
    const setBody = (html, klass) => {
      if (!body) return;
      body.className = klass;
      body.innerHTML = html;
    };
    const setCount = (text) => { if (count) count.textContent = text; };

    /* ------------------------------------------------- hierarchy card steps -
       Region, Category and Sub Category are all the same card: a folder
       icon, a title, the numbers measured off the files behind it, and an
       "Open →". They step aside the moment a language is chosen, from which
       point Study's own language / chapter / part renderers take over. */
    let hierSeo = null;

    const renderHierarchy = () => {
      const kind = hierStep.kind;
      const list = Array.isArray(hierStep.list) ? hierStep.list : [];
      const parent = hierStep.parent;
      const st = (n) => (n && n.stats) || {};
      const badge = (v, label, lead) => {
        const num = Number(v) || 0;
        return `<span class="badge ${num && lead ? "badge-success" : "badge-muted"}">${label(num)}</span>`;
      };
      const sid = encodeURIComponent(subjectId);
      const at = (q) => `study.html?subject=${sid}${q ? `&${q}` : ""}`;
      const nodeCard = (href, title, description, badges) => `
        <a class="card subject-card" style="--sc:${esc(color)}" href="${esc(href)}">
          <span class="subject-icon" aria-hidden="true">📁</span>
          <h3>${esc(title)}</h3>
          ${description ? `<p>${esc(description)}</p>` : ""}
          <div class="subject-meta">${badges}</div>
          <span class="ilink st-open">Open →</span>
        </a>`;

      let html = "";
      let eyebrowText = "Study Material";
      let headText = "";
      let descText = "";
      let backHref = "study.html";
      let backLabel = "← All subjects";
      let countText = "";
      let seoTitle = `${name} Study Material | House of Aspirants`;
      let seoDesc = "";

      if (kind === "region") {
        headText = "Choose a region";
        descText = `${many(list.length, "region", "regions")} sit under ${name}. ` +
          `Open one to see its categories.`;
        countText = `${many(list.length, "region", "regions")} · ` +
          `${plural(Number(hier.stats && hier.stats.files) || 0, "file")} under ${name}`;
        html = list.map((r) => nodeCard(
          at(`region=${encodeURIComponent(r.id)}`), r.name, r.description || "",
          badge(st(r).categories, (n) => many(n, "category", "categories"), true) +
          badge(st(r).chapters, (n) => plural(n, "chapter")) +
          badge(st(r).pages, (n) => plural(n, "page")))).join("");
        seoDesc = `${many(list.length, "region", "regions")} of free ${name} study ` +
          `material for Punjab competitive exams — open a region, then a category, ` +
          `then a language.`;
      } else if (kind === "category") {
        const q0 = `region=${encodeURIComponent(parent.id)}`;
        eyebrowText = `Study Material · ${parent.name}`;
        headText = "Choose a category";
        descText = `${many(list.length, "category", "categories")} in ${parent.name}. ` +
          `Open one to see its languages.`;
        backHref = at("");
        backLabel = `← ${name}`;
        countText = `${many(list.length, "category", "categories")} · ` +
          `${plural(Number(parent.stats && parent.stats.files) || 0, "file")} in ${parent.name}`;
        html = list.map((c) => {
          const subs = Array.isArray(c.subCategories) ? c.subCategories.length : 0;
          return nodeCard(at(`${q0}&cat=${encodeURIComponent(c.id)}`), c.name,
            c.description || "",
            (subs ? badge(subs, (n) => many(n, "category", "categories"), true) : "") +
            badge(st(c).chapters, (n) => plural(n, "chapter"), !subs) +
            badge(st(c).pages, (n) => plural(n, "page")));
        }).join("");
        seoTitle = `${parent.name} — ${name} | House of Aspirants`;
        seoDesc = `${many(list.length, "category", "categories")} inside ${parent.name}, ` +
          `part of ${name} — each one opens on its languages, then chapters, then parts.`;
      } else {
        const q0 = `region=${encodeURIComponent(gRegion.id)}` +
                   `&cat=${encodeURIComponent(parent.id)}`;
        eyebrowText = `Study Material · ${parent.name}`;
        headText = "Choose a sub category";
        descText = `${many(list.length, "sub category", "sub categories")} in ` +
          `${parent.name}. Open one to choose a language.`;
        backHref = at(`region=${encodeURIComponent(gRegion.id)}`);
        backLabel = "← Choose a category";
        countText = `${many(list.length, "sub category", "sub categories")} · ` +
          `${plural(Number(parent.stats && parent.stats.files) || 0, "file")} in ${parent.name}`;
        html = list.map((s) => nodeCard(
          at(`${q0}&sub=${encodeURIComponent(s.id)}`), s.name, s.description || "",
          badge(st(s).chapters, (n) => plural(n, "chapter"), true) +
          badge(st(s).pages, (n) => plural(n, "page")))).join("");
        if (hierStep.loose) {
          const loose = hierStep.loose;
          html += `<p class="mt-2"><a class="btn btn-soft" href="${esc(
            at(`${q0}&sub=${ALL_SUBS}`))}">Everything else · ${plural(loose, "chapter")} ` +
            `no head claims</a></p>`;
        }
        seoTitle = `${parent.name} — ${gRegion.name} | House of Aspirants`;
        seoDesc = `${many(list.length, "sub category", "sub categories")} inside ` +
          `${parent.name}, part of ${gRegion.name} inside ${name}.`;
      }

      if (eyebrow) eyebrow.textContent = eyebrowText;
      if (head) head.textContent = headText;
      if (desc) desc.textContent = descText;
      if (back instanceof HTMLAnchorElement) {
        back.href = backHref;
        back.textContent = backLabel;
      }
      if (tools) tools.hidden = true;
      setBody(html, "grid grid-3 subjects-grid");
      setCount(countText);
      hierSeo = { steps: hierSteps(), title: seoTitle, desc: seoDesc };
    };

    const renderLanguages = () => {
      setBody(langs.length
        ? langs.map((l) => languageCard(l, hrefFor(l.id), color)).join("")
        : emptyState("🌐", "No languages here yet",
            `Study material publishes into a language folder under ` +
            `<code>content/study-material/${esc(folderId)}/</code>. Until one ` +
            `exists there is nothing to choose.`,
            `<p class="mt-2"><a class="btn btn-soft" href="study-material.html">All study material →</a></p>`),
        "grid grid-3 subjects-grid");
      setCount(`${plural(langs.length, "language")} · ${plural(subjectCount, "file")} in ${nodeName} · nothing is listed until you choose one`);
    };

    const renderChapters = () => {
      const total = chapters.length;
      setBody((hier ? savedStrip() : "") + (total
        ? chapters.map((c, i) => chapterCard(c, hrefFor(languageId, c.id), langName,
            hier ? {
              no: i + 1,
              total,
              // The languages this same chapter is published in beside the
              // one you are reading — measured, never assumed, and with the
              // language you are standing in named first.
              languages: langs
                .filter((l) => (l.chapters || []).some((x) => x.id === c.id))
                .sort((a, b) => (a.id === languageId ? -1
                  : b.id === languageId ? 1 : 0))
                .map((l) => l.name),
            } : null)).join("")
        : emptyState("📖", `No ${langName} chapters in ${nodeName} yet`,
            `Create a chapter folder under ` +
            `<code>content/study-material/${esc(folderId)}/${esc(languageId)}/</code> ` +
            `and its parts appear here on the next build — no page to write.`,
            `<p class="mt-2"><a class="btn btn-soft" href="${esc(hrefFor())}">Choose another language</a></p>`)),
        "grid grid-3");
      setCount(`${plural(chapters.length, "chapter")} in ${langName} · ${plural(Number(lang && lang.count) || 0, "file")}`);
    };

    const renderParts = () => {
      setBody(chapterParts.length
        ? `<ol class="part-rows">${chapterParts.map(partRow).join("")}</ol>`
        : emptyState("📄", "This chapter has no parts yet",
            `Drop a file into ` +
            `<code>content/study-material/${esc(folderId)}/${esc(languageId)}/${esc(chapterId)}/</code> ` +
            `and it becomes part one on the next build.`,
            `<p class="mt-2"><a class="btn btn-soft" href="${esc(hrefFor(languageId))}">All ${esc(langName)} chapters →</a></p>`),
        "part-wrap");
      setCount(`${plural(chapterParts.length, "part")} in reading order · ${langName}`);
    };

    /* Search starts only once a language is chosen, and it stays inside that
       language: before a language is chosen there is nothing for a query to
       be honest about. */
    const renderSearch = (query) => {
      const pool = chapters
        .flatMap((c) => (c.parts || []).map((p) => partItem(p)))
        .filter((it) => it.file)
        .sort(byShelfOrder);
      const shown = pool.filter((it) => haystack(it).includes(query));
      setBody(shown.length
        ? shown.map(materialCard).join("")
        : emptyState("🔎", "Nothing matches that",
            `No file in ${nodeName} · ${langName} carries that word. Try the title, ` +
            `the chapter or a keyword.`,
            `<p class="mt-2"><a class="btn btn-soft" href="${esc(hrefFor(languageId))}">Back to the chapters</a></p>`),
        "grid grid-3");
      setCount(`${shown.length} of ${pool.length} file(s) match “${query}” in ${langName}`);
    };

    const search = document.getElementById("studySearch");
    if (search) {
      search.addEventListener("input", () => {
        const q = String(/** @type {HTMLInputElement} */ (search).value).trim();
        if (step === "language") return;
        if (q) renderSearch(q.toLowerCase());
        else if (step === "chapter") renderChapters();
        else renderParts();
      });
    }

    /* The chapter cards' two controls — the star and the removal from the
       saved strip — are bound once, on the body container, which only ever
       has its innerHTML replaced. One listener survives every re-render and
       no card ever needs its own. */
    const bodyNode = document.getElementById("studyStepBody");
    if (bodyNode) {
      bodyNode.addEventListener("click", (ev) => {
        const target = ev.target;
        if (!(target instanceof Element)) return;
        const star = /** @type {HTMLElement | null} */ (
          target.closest("[data-study-bookmark]"));
        if (star && star.dataset.studyBookmark) {
          ev.preventDefault();
          const key = String(star.dataset.studyBookmark);
          const on = toggleSaved({
            key,
            href: key,
            title: String(star.dataset.studyTitle || "Chapter"),
          });
          if (typeof HOA.toast === "function") {
            HOA.toast(on ? "Chapter saved on this device" : "Chapter removed");
          }
          renderChapters();
          return;
        }
        const drop = /** @type {HTMLElement | null} */ (
          target.closest("[data-study-unsave]"));
        if (drop && drop.dataset.studyUnsave) {
          ev.preventDefault();
          const key = String(drop.dataset.studyUnsave);
          writeSaved(savedChapters().filter((b) => b.key !== key));
          if (typeof HOA.toast === "function") HOA.toast("Chapter removed");
          renderChapters();
        }
      });
    }

    if (hierStep) {
      renderHierarchy();
      setStepSeo(hierSeo);
      return;
    }

    if (step === "language") renderLanguages();
    else if (step === "chapter") renderChapters();
    else renderParts();

    setStepSeo(hier ? {
      steps: hierSteps(),
      title: chapterName
        ? `${chapterName} (${langName}) — parts | House of Aspirants`
        : langName
          ? `${nodeName} — ${langName} chapters | House of Aspirants`
          : `${nodeName} — ${name} | House of Aspirants`,
      desc: chapterName
        ? `${chapterParts.length} part(s) of ${chapterName}, in ${langName}, under ${nodeName}. Read online or download, free for every aspirant.`
        : langName
          ? `${plural(chapters.length, "chapter")} of free ${nodeName} study material in ${langName} — read online or download, no sign-up and no paid tier.`
          : `${subjectCount} file(s) of free ${nodeName} study material inside ${name} — open a language, then a chapter, then a part.`,
    } : undefined);
    return;

    /** Per-step head tags + JSON-LD, so a URL deep in the hierarchy has its
        own identity while the subject remains the page that owns it. */
    function setStepSeo(opts) {
      const url = `${siteBase}/study?${["subject=" + encodeURIComponent(subjectId)]
        .concat(hierQ)
        .concat(languageId ? ["language=" + encodeURIComponent(languageId)] : [])
        .concat(chapterId ? ["chapter=" + encodeURIComponent(chapterId)] : [])
        .join("&")}`;
      // `steps` carries every level above the language; each keeps its own
      // URL so the JSON-LD trail describes the shelf and not just this page.
      const steps = opts && Array.isArray(opts.steps) && opts.steps.length
        ? opts.steps
        : [{ name, item: url }];
      const trail = [{ name: "Home", item: `${siteBase}/` },
                     { name: "Study", item: `${siteBase}/study` }]
        .concat(steps.map((s) => ({ name: s.name, item: s.item || url })))
        .concat(langName ? [{ name: langName, item: url }] : [])
        .concat(chapterName ? [{ name: chapterName, item: url }] : []);

      const pageTitle = (opts && opts.title) || (chapterName
        ? `${chapterName} (${langName}) — parts | House of Aspirants`
        : langName
          ? `${nodeName} — ${langName} chapters | House of Aspirants`
          : `${nodeName} Study Material | House of Aspirants`);
      const desc = (opts && opts.desc) || (chapterName
        ? `${chapterParts.length} part(s) of ${chapterName}, in ${langName}, under ${nodeName}. Read online or download, free for every aspirant.`
        : langName
          ? `${plural(chapters.length, "chapter")} of free ${nodeName} study material in ${langName} — read online or download, no sign-up and no paid tier.`
          : `${subjectCount} file(s) of free ${nodeName} study material for Punjab competitive exams — choose a language, then a chapter, then a part.`);

      if (typeof (/** @type {any} */ (HOA).seo) === "function") {
        (/** @type {any} */ (HOA).seo)({
          title: pageTitle,
          canonical: url,
          description: desc,
          ogTitle: pageTitle,
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
            name: pageTitle,
            description: desc,
            isPartOf: { "@id": `${siteBase}/#website` },
            breadcrumb: { "@id": `${url}#breadcrumb` },
            inLanguage: "en-IN",
          },
          {
            "@type": "BreadcrumbList",
            "@id": `${url}#breadcrumb`,
            itemListElement: trail.map((it, i) => ({
              "@type": "ListItem", position: i + 1, name: it.name, item: it.item,
            })),
          },
        ],
      }, null, 2);
      document.head.appendChild(s);
    }
  }

  /* ================================================================ ROOT === */
  const grid = document.getElementById("studySubjects");
  if (!grid) return;

  if (subjEl) subjEl.hidden = true;
  if (rootEl) rootEl.hidden = false;

  /* One grid, from the manifest. A folder with no files still earns a card —
     that is where the next file goes — and it says so plainly rather than
     pretending there is something to read.

     A folder a hierarchy has claimed keeps its row in the manifest — its
     material pages still link to `study.html?subject=<folder>` and that URL
     must keep resolving — but it gives up its place on the shelf, because
     the group is what the reader is asked to choose. */
  const rows = (shelf.length
    ? shelf
    : indexSubjects.map((s) => ({
        id: s.id, name: s.name, icon: s.icon, color: s.color,
        description: s.description, order: 0, count: 0, newest: "",
        totalSize: 0, languages: [],
      }))).filter((r) => r && !r.hidden);

  grid.innerHTML = rows.map((r) => {
    const n = Number(r.count) || 0;
    const newest = fmtDate(r.newest);
    const languages = (r.languages || []).filter((l) => Number(l.count) > 0);
    return `
      <a class="card subject-card" style="--sc:${esc(r.color || "#4f46e5")}"
         href="study.html?subject=${esc(r.id)}">
        <span class="subject-icon">${esc(r.icon || "📚")}</span>
        <h3>${esc(r.name)}</h3>
        <p>${esc(r.description || "Notes, PDFs and downloads for this subject.")}</p>
        <div class="subject-meta">
          <span class="badge ${n ? "badge-success" : "badge-muted"}">${plural(n, "file")}</span>
          ${languages.map((l) =>
            `<span class="badge badge-muted">${esc(l.flag || "")} ${esc(l.name)}</span>`).join("")}
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
