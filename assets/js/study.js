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

  /* ------------------------------------------------------- shared cards ---
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

  const chapterCard = (c, href, langName) => {
    const parts = (c.parts || []).length;
    return `
        <a class="card card-pad study-card" href="${esc(href)}">
          <span class="eyebrow">${esc(langName)} · Chapter</span>
          <h3>${esc(c.name)}</h3>
          <p class="muted">${plural(parts, "part")}, in reading order.</p>
          <p class="study-meta">${esc(langName)} · ${plural(parts, "part")}</p>
        </a>`;
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

    /** The language tree the content build found for this subject. */
    const langs = (shelfSubject && Array.isArray(shelfSubject.languages))
      ? shelfSubject.languages : [];
    const subjectCount = Number(shelfSubject && shelfSubject.count) || 0;
    const color = (shelfSubject && shelfSubject.color) || "#4f46e5";

    /* --- which step are we on? -------------------------------------------
       A language must always be chosen before any material is listed, so
       an unknown id, an old `&category=` link or an old `&view=chapters`
       link all resolve to the furthest step they can honestly reach. */
    let languageId = langParam;
    let chapterId = chapterParam;

    if (!languageId && categoryId) {
      const hits = langs.filter((l) =>
        (l.chapters || []).some((c) => c.id === categoryId));
      if (hits.length === 1) {
        languageId = hits[0].id;
        chapterId = categoryId;
      } else {
        chapterId = "";
      }
    }
    if (!languageId && view === "chapters") {
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
      const q = [`subject=${encodeURIComponent(subjectId)}`];
      if (language) q.push(`language=${encodeURIComponent(language)}`);
      if (ch) q.push(`chapter=${encodeURIComponent(ch)}`);
      return `study.html?${q.join("&")}`;
    };

    const crumb = document.getElementById("studyBreadcrumb");
    if (crumb) {
      const trail = [
        `<a href="index.html">Home</a><span>/</span>`,
        `<a href="study.html">Study</a><span>/</span>`,
        step === "language"
          ? `<span>${esc(name)}</span>`
          : `<a href="${esc(hrefFor())}">${esc(name)}</a><span>/</span>`,
      ];
      if (step !== "language") {
        trail.push(step === "chapter"
          ? `<span>${esc(langName)}</span>`
          : `<a href="${esc(hrefFor(languageId))}">${esc(langName)}</a><span>/</span>`);
      }
      if (step === "part") trail.push(`<span>${esc(chapterName)}</span>`);
      crumb.innerHTML = trail.join("");
    }

    // The subject owns the <h1> here, so a shelf URL, the breadcrumb and the
    // page heading all say the same word and no two headings on the page
    // carry the same text.
    const title = document.getElementById("studyTitle");
    if (title) title.textContent = name;
    const lead = document.getElementById("studyLead");
    if (lead) {
      lead.textContent =
        `Subject → language → chapter → part. Choose the language you want to ` +
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
        ? `Every chapter in ${name} is filed under the language it is written ` +
          `in. Nothing is listed until you choose one.`
        : step === "chapter"
          ? `${plural(chapters.length, "chapter")} published in ${langName} under ` +
             `${name}. Open one to see its parts.`
          : `${plural(chapterParts.length, "part")} in reading order, in ${langName}. ` +
             `Read online or download — the part before and after it is always one tap away.`;
    }
    if (back instanceof HTMLAnchorElement) {
      back.href = step === "language" ? "study.html"
        : step === "chapter" ? hrefFor()
        : hrefFor(languageId);
      back.textContent = step === "language" ? "← All subjects"
        : step === "chapter" ? "← Choose a language"
        : `← ${langName} chapters`;
    }
    if (tools) tools.hidden = step === "language";

    /* ------------------------------------------------------- step bodies -- */
    const setBody = (html, klass) => {
      if (!body) return;
      body.className = klass;
      body.innerHTML = html;
    };
    const setCount = (text) => { if (count) count.textContent = text; };

    const languageCard = (l) => {
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
           href="${esc(hrefFor(l.id))}">
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

    const chapterCard = (c) => {
      const parts = (c.parts || []).length;
      return `
        <a class="card card-pad study-card" href="${esc(hrefFor(languageId, c.id))}">
          <span class="eyebrow">${esc(langName)} · Chapter</span>
          <h3>${esc(c.name)}</h3>
          <p class="muted">${plural(parts, "part")}, in reading order.</p>
          <p class="study-meta">${esc(langName)} · ${plural(parts, "part")}</p>
        </a>`;
    };

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

    const renderLanguages = () => {
      setBody(langs.length
        ? langs.map(languageCard).join("")
        : emptyState("🌐", "No languages here yet",
            `Study material publishes into a language folder under ` +
            `<code>content/study-material/${esc(subjectId)}/</code>. Until one ` +
            `exists there is nothing to choose.`,
            `<p class="mt-2"><a class="btn btn-soft" href="study-material.html">All study material →</a></p>`),
        "grid grid-3 subjects-grid");
      setCount(`${plural(langs.length, "language")} · ${plural(subjectCount, "file")} in ${name} · nothing is listed until you choose one`);
    };

    const renderChapters = () => {
      setBody(chapters.length
        ? chapters.map(chapterCard).join("")
        : emptyState("📖", `No ${langName} chapters in ${name} yet`,
            `Create a chapter folder under ` +
            `<code>content/study-material/${esc(subjectId)}/${esc(languageId)}/</code> ` +
            `and its parts appear here on the next build — no page to write.`,
            `<p class="mt-2"><a class="btn btn-soft" href="${esc(hrefFor())}">Choose another language</a></p>`),
        "grid grid-3");
      setCount(`${plural(chapters.length, "chapter")} in ${langName} · ${plural(Number(lang && lang.count) || 0, "file")}`);
    };

    const renderParts = () => {
      setBody(chapterParts.length
        ? `<ol class="part-rows">${chapterParts.map(partRow).join("")}</ol>`
        : emptyState("📄", "This chapter has no parts yet",
            `Drop a file into ` +
            `<code>content/study-material/${esc(subjectId)}/${esc(languageId)}/${esc(chapterId)}/</code> ` +
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
            `No file in ${name} · ${langName} carries that word. Try the title, ` +
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

    if (step === "language") renderLanguages();
    else if (step === "chapter") renderChapters();
    else renderParts();

    setStepSeo();
    return;

    /** Per-step head tags + JSON-LD, so a URL deep in the hierarchy has its
        own identity while the subject remains the page that owns it. */
    function setStepSeo() {
      const url = `${siteBase}/study?${["subject=" + encodeURIComponent(subjectId)]
        .concat(languageId ? ["language=" + encodeURIComponent(languageId)] : [])
        .concat(chapterId ? ["chapter=" + encodeURIComponent(chapterId)] : [])
        .join("&")}`;
      const trail = [{ name: "Home", item: `${siteBase}/` },
                     { name: "Study", item: `${siteBase}/study` },
                     { name, item: url }];
      if (langName) trail.push({ name: langName, item: url });
      if (chapterName) trail.push({ name: chapterName, item: url });

      const pageTitle = chapterName
        ? `${chapterName} (${langName}) — parts | House of Aspirants`
        : langName
          ? `${name} — ${langName} chapters | House of Aspirants`
          : `${name} Study Material | House of Aspirants`;
      const desc = chapterName
        ? `${chapterParts.length} part(s) of ${chapterName}, in ${langName}, under ${name}. Read online or download, free for every aspirant.`
        : langName
          ? `${plural(chapters.length, "chapter")} of free ${name} study material in ${langName} — read online or download, no sign-up and no paid tier.`
          : `${subjectCount} file(s) of free ${name} study material for Punjab competitive exams — choose a language, then a chapter, then a part.`;

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
     pretending there is something to read. */
  const rows = shelf.length
    ? shelf
    : indexSubjects.map((s) => ({
        id: s.id, name: s.name, icon: s.icon, color: s.color,
        description: s.description, order: 0, count: 0, newest: "",
        totalSize: 0, languages: [],
      }));

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
