// @ts-check
/* ============================================================================
 * subject.js | Subject page — 3-level hierarchy: Subject › Category › Topic
 * ----------------------------------------------------------------------------
 * The LEVEL is detected from the URL — nothing is hardcoded:
 *   subject.html?subject=gk                    → the subject's CATEGORIES
 *   subject.html?subject=gk&category=polity    → that category's TOPICS
 *   subject.html?subject=punjabi               → flat subject → TOPICS
 *
 * Categories come from data/subjects.json; topics are the JSON files the
 * build script auto-detected inside each folder. Add a file → a card
 * appears. Delete it → the card disappears. No code changes, ever.
 * ========================================================================== */
(async () => {
  "use strict";
  const { esc } = HOA;
  const params = new URLSearchParams(location.search);
  const subjectId = params.get("subject") || "";
  const categoryId = params.get("category") || "";
  const chapterParam = params.get("chapter") || "";
  const idx = await HOA.loadIndex();
  const siteBase = String((idx.site && idx.site.url) || "").replace(/\/+$/, "");
  const subject = (idx.subjects || []).find((s) => s.id === subjectId);

  const wrap = document.getElementById("topicGrid");
  const titleEl = document.getElementById("subjectTitle");
  const crumbSubject = document.getElementById("crumbSubject");
  const crumbSubjectLink = /** @type {HTMLAnchorElement | null} */ (
    document.getElementById("crumbSubjectLink")
  );
  const crumbSep = document.getElementById("crumbSep");
  const crumbCategory = document.getElementById("crumbCategory");
  const descEl = document.getElementById("subjectDesc");
  const filterEl = /** @type {HTMLInputElement | null} */ (
    document.getElementById("topicFilter")
  );
  const secEyebrow = document.getElementById("secEyebrow");
  const secTitle = document.getElementById("secTitle");
  const secHint = document.getElementById("secHint");
  const countTopics = document.getElementById("countTopics");
  const countTopicsLabel = document.getElementById("countTopicsLabel");
  const countQuizzes = document.getElementById("countQuizzes");
  const countQuestions = document.getElementById("countQuestions");

  /* ------------------------------------------------------- Subject not found */
  if (!subject) {
    titleEl.textContent = "Subject not found";
    descEl.textContent = "Pick a subject from the home page.";
    if (crumbSubject) crumbSubject.textContent = "Not found";
    document.getElementById("practiceSection")?.setAttribute("hidden", "");
    wrap.innerHTML = `<div class="empty-state"><div class="es-icon">🤔</div>
      <h3>Unknown subject</h3>
      <p>This subject is not in your configuration. Check <code>data/subjects.json</code> or the folder name inside <code>questions/</code>.</p>
      <p class="mt-2"><a class="btn btn-primary" href="./">Back to Home</a></p></div>`;
    /* Soft-404: a bare /subject or an unknown ?subject= must not be indexed
       (same handling as an unknown ?category=). */
    HOA.seo({ robots: "noindex, nofollow" });
    const ldBad = document.getElementById("ldDynamic");
    if (ldBad) ldBad.textContent = "";
    return;
  }

  /* -------------------------------------------------------- Determine level */
  const categories = Array.isArray(subject.categories) ? subject.categories : [];
  const hierarchical = categories.length > 0;
  const category = categoryId ? categories.find((c) => c.id === categoryId) : null;
  // A ?category= that matches nothing → show the subject root, but noindex it.
  const badCategory = hierarchical && !!categoryId && !category;
  // "root" = subject with categories (show categories)
  // "category" = inside one category (show its topics)
  // "flat" = subject without categories (show its topics directly)
  const level = !hierarchical ? "flat" : category ? "category" : "root";

  /* -------------------------------------------------------- Category groups -
   * The data model is Subject > Category > Topic — there is no fourth level,
   * and inventing one would mean new routes and a new build step. So a group
   * is a PRESENTATION relationship only: the parent category keeps its own
   * landing page, every child keeps its own, and no URL changes. What changes
   * is that a student opening General Knowledge sees
   *   History  ->  Ancient / Medieval / Modern History
   * instead of ten sibling cards with no hint of the syllabus nesting.
   *
   * An entry applies only when EVERY id it names is present in
   * data/index.json, so renaming or deleting a category in
   * data/subjects.json falls back to the flat list rather than leaving a
   * dead heading or a broken link. Keys are subject ids from that file. */
  const CATEGORY_GROUPS = {
    gk: [
      {
        parent: "history",
        children: ["ancient-history", "medieval-history", "modern-history"],
      },
      /* Punjab GK owns the five state lanes. Its own folder still holds the
         published Sikhism sets, so the parent card reports both:
         "5 categories · 4 topics · 95 questions". */
      {
        parent: "punjab-gk",
        children: [
          "history-of-punjab",
          "culture-of-punjab",
          "punjab-literature",
          "geography-of-punjab",
          "economy-of-punjab",
        ],
      },
    ],
  };

  /** Groups whose parent AND every child are in `list` (post-filter). */
  function resolveGroups(list) {
    const byId = new Map(list.map((c) => [c.id, c]));
    return (CATEGORY_GROUPS[subject.id] || [])
      .map(({ parent, children }) => {
        const p = byId.get(parent);
        const kids = children.map((id) => byId.get(id)).filter(Boolean);
        // A filter can remove the parent or some children; unless all of the
        // group survives, render it flat so nothing disappears silently.
        return p && kids.length === children.length ? { parent: p, kids } : null;
      })
      .filter(Boolean);
  }

  /* ------------------------------------------------- SEO + page header -----
   * When the build has generated a static landing page for this entity
   * (subject.landing / category.landing in data/index.json, written by
   * scripts/build_landing_pages.py) the query-string URL canonicalises ONTO
   * it, so the app view and the landing page never compete in the index.
   * No landing page in the manifest = self-canonical, exactly as before. */
  let canonical = subject.landing
    ? `${siteBase}${subject.landing}`
    : `${siteBase}/subject?subject=${encodeURIComponent(subject.id)}`;
  let docTitle = `${subject.name} Expected MCQs - House of Aspirants`;
  let h1 = subject.name;
  let desc = subject.description || "Topic-wise MCQ practice.";
  let icon = subject.icon;

  if (level === "category") {
    canonical = category.landing
      ? `${siteBase}${category.landing}`
      : `${siteBase}/subject?subject=${encodeURIComponent(subject.id)}&category=${encodeURIComponent(category.id)}`;
    docTitle = `${category.name} - ${subject.name} Expected MCQs - House of Aspirants`;
    h1 = category.name;
    desc = `All ${category.name} expected MCQs inside ${subject.name} — every topic in the folder is detected automatically.`;
    icon = category.icon || subject.icon;
  }
  /* SERP meta description sized for the 140-160 snippet window — the short
     `desc` above remains the visible subtitle under the h1. */
  const metaDesc =
    level === "category"
      ? `${category.name} expected MCQs inside ${subject.name} - pick any topic and start free MCQ practice instantly for Punjab Police, PSSSB and competitive exams.`
      : `Free ${subject.name} expected MCQs with instant results and answer review - topic wise MCQ practice for Punjab Police, PSSSB and Punjab Government exam aspirants.`;
  HOA.seo({
    title: docTitle,
    canonical,
    robots: badCategory ? "noindex, nofollow" : "index, follow",
    ogTitle: docTitle,
    ogDescription: desc,
    description: metaDesc,
  });
  titleEl.textContent = h1;
  descEl.textContent = desc;
  document.getElementById("subjectIcon").textContent = icon;

  /* ------------------------------------------------------------ Breadcrumb -
   * Toggle flat siblings — never nest spans (the shared rule
   * `.breadcrumb span { opacity: .6 }` would multiply per nesting level). */
  if (level === "category") {
    if (crumbSubject) crumbSubject.classList.add("hidden");
    if (crumbSubjectLink) {
      crumbSubjectLink.textContent = subject.name;
      crumbSubjectLink.href = `subject?subject=${encodeURIComponent(subject.id)}`;
      crumbSubjectLink.classList.remove("hidden");
    }
    if (crumbSep) crumbSep.classList.remove("hidden");
    if (crumbCategory) {
      crumbCategory.textContent = category.name;
      crumbCategory.classList.remove("hidden");
    }
  } else if (crumbSubject) {
    crumbSubject.textContent = subject.name;
  }

  /* -------------------------------------------------------------- JSON-LD -
   * Rebuilds the head's <script id="ldDynamic"> so the structured data
   * matches EXACTLY the level that is rendered: a CollectionPage of what the
   * grid shows + a BreadcrumbList with the same names the visible trail
   * shows. A noindex render (?category= mismatch) clears the block.
   * (topicHref is a function declaration further down — hoisted to scope.) */
  const ldEl = document.getElementById("ldDynamic");
  if (ldEl) {
    if (badCategory) {
      ldEl.textContent = "";
    } else {
      const subjectUrl = `${siteBase}/subject?subject=${encodeURIComponent(subject.id)}`;
      const crumbList = [
        { name: "Home", url: `${siteBase}/` },
        { name: "Subjects", url: `${siteBase}/#subjects` },
        { name: subject.name, url: subjectUrl },
      ];
      if (level === "category") crumbList.push({ name: category.name, url: canonical });

      let items = [];
      if (level === "root") {
        items = categories.map((c) => ({
          name: c.name,
          url: `${subjectUrl}&category=${encodeURIComponent(c.id)}`,
        }));
      } else {
        const list = (level === "category" ? category.topics : subject.topics) || [];
        items = list
          .filter((t) => t.available)
          .map((t) => ({
            name: t.name,
            // JSON-LD links the canonical URL; the anchor keeps its .html
            // form so the static host keeps serving it without rewrites.
            url: `${siteBase}/${topicHref(t).replace("quiz.html?", "quiz?")}`,
          }));
      }

      const page = {
        "@type": "CollectionPage",
        "@id": `${canonical}#webpage`,
        url: canonical,
        name:
          level === "category"
            ? `${category.name} - ${subject.name} Expected MCQs`
            : `${subject.name} Expected MCQs`,
        description: metaDesc,
        isPartOf: { "@id": `${siteBase}/#website` },
        publisher: { "@id": `${siteBase}/#organization` },
        inLanguage: "en-IN",
        breadcrumb: { "@id": `${canonical}#breadcrumb` },
      };
      // Schema.org nodes are deliberately shapeless: each @type carries only
      // the fields that apply to it, so the array is not one fixed interface.
      const graph = /** @type {any[]} */ ([page]);
      if (items.length) {
        page.mainEntity = { "@id": `${canonical}#list` };
        graph.push({
          "@type": "ItemList",
          "@id": `${canonical}#list`,
          name:
            level === "root"
              ? `${subject.name} categories`
              : `${level === "category" ? category.name : subject.name} topics`,
          numberOfItems: items.length,
          itemListElement: items.map((it, i) => ({
            "@type": "ListItem",
            position: i + 1,
            name: it.name,
            item: it.url,
          })),
        });
      }
      const breadcrumb = {
        "@type": "BreadcrumbList",
        "@id": `${canonical}#breadcrumb`,
        itemListElement: crumbList.map((c, i) => ({
          "@type": "ListItem",
          position: i + 1,
          name: c.name,
          item: c.url,
        })),
      };
      graph.push(breadcrumb);
      ldEl.textContent = JSON.stringify(
        { "@context": "https://schema.org", "@graph": graph },
        null,
        2
      );
    }
  }

  /* ----------------------------------------------------------------- Stats -
   * At the category level the counts scope down to that category; a
   * hierarchical subject root shows how many CATEGORIES it has. */
  const topicList = level === "category" ? category.topics : subject.topics;

  /* -------------------------------------------------------------- Chapters -
   * Same shape as the Study shelf: chapter folders first, the chapter's
   * parts (one MCQ set each) inside. A chapter is the topic id with its
   * `-part-N` tail removed, so `04-guru-teg-bahadur-…-part-2` files under
   * `04-guru-teg-bahadur-…`. Presentation only — quiz URLs are unchanged and
   * `&chapter=` merely opens one folder. */
  const PART_RE = /-part-?(\d+)(?:-.*)?$/i;
  const SMALL = new Set(["and", "of", "the", "in", "to", "a", "an", "for", "on"]);
  const WORDS = { mcqs: "MCQs", mcq: "MCQ", dpsp: "DPSP", gk: "GK" };
  const humanize = (key) =>
    key
      .replace(/^\d+[-_]/, "")
      .split(/[-_\s]+/)
      .filter(Boolean)
      .map((w, i) => {
        const lw = w.toLowerCase();
        if (WORDS[lw]) return WORDS[lw];
        if (i && SMALL.has(lw)) return lw;
        return lw.charAt(0).toUpperCase() + lw.slice(1);
      })
      .join(" ");
  const partOf = (t) => {
    const m = PART_RE.exec(String(t.id));
    return m ? Number(m[1]) : 0;
  };
  const chapterCollator = new Intl.Collator(undefined, { numeric: true, sensitivity: "base" });
  /** @type {{id: string, name: string, num: number, topics: any[]}[]} */
  const chapterList = [];
  if (level !== "root") {
    const byKey = new Map();
    for (const t of topicList || []) {
      const key = String(t.id).replace(PART_RE, "") || String(t.id);
      if (!byKey.has(key)) {
        const num = /^(\d+)[-_]/.exec(key);
        const ch = { id: key, name: humanize(key) || t.name, num: num ? Number(num[1]) : 0, topics: [] };
        byKey.set(key, ch);
        chapterList.push(ch);
      }
      byKey.get(key).topics.push(t);
    }
    chapterList.forEach((c) =>
      c.topics.sort((a, b) => partOf(a) - partOf(b) || chapterCollator.compare(a.id, b.id))
    );
    // Numbered chapters in syllabus order, then the rest A-Z.
    chapterList.sort(
      (a, b) =>
        (a.num ? 0 : 1) - (b.num ? 0 : 1) ||
        a.num - b.num ||
        chapterCollator.compare(a.name, b.name)
    );
  }
  const chapter = chapterList.find((c) => c.id === chapterParam) || null;
  const chapterBase =
    level === "category"
      ? `subject?subject=${encodeURIComponent(subject.id)}&category=${encodeURIComponent(category.id)}`
      : `subject?subject=${encodeURIComponent(subject.id)}`;
  const chapterHref = (c) => `${chapterBase}&chapter=${encodeURIComponent(c.id)}`;

  /* Chapter crumb: the last crumb becomes a link back to the folder list and
     the chapter name follows it — flat siblings, as the markup requires. */
  if (chapter) {
    const last = document.getElementById(level === "category" ? "crumbCategory" : "crumbSubject");
    if (last) {
      const a = document.createElement("a");
      a.href = chapterBase;
      a.textContent = last.textContent;
      const sep = document.createElement("span");
      sep.textContent = "/";
      const cur = document.createElement("span");
      cur.textContent = chapter.name;
      last.replaceWith(a, sep, cur);
    }
    titleEl.textContent = chapter.name;
    descEl.textContent = `${chapter.topics.length} MCQ set${chapter.topics.length === 1 ? "" : "s"} in this chapter — open one to start.`;
  }
  /* Zero means "nothing here yet" — drop the card rather than printing a 0. */
  const setStat = (el, value) => {
    if (!el) return;
    if (value > 0) el.textContent = value;
    else el.closest(".stat-card")?.setAttribute("hidden", "");
  };
  if (countTopics && countTopicsLabel) {
    countTopicsLabel.textContent =
      level === "root" ? "Categories" : chapter ? "Parts" : "Chapters";
    setStat(
      countTopics,
      level === "root" ? categories.length : chapter ? chapter.topics.length : chapterList.length
    );
  }
  const statList = chapter ? chapter.topics : topicList;
  setStat(countQuizzes, statList.filter((t) => t.available).length);
  setStat(countQuestions, statList.reduce((n, t) => n + t.count, 0));

  /* --------------------------------------------------------- Section head --
   * STUDY MATERIAL - the first of the subject's two halves. The label is the
   * student's, not the pipeline's: "categories" and "topics" are how the
   * folders are built, "study material" is what a candidate came here for. */
  const folderPath =
    level === "category"
      ? `questions/${subject.id}/${category.folder || category.id}/`
      : `questions/${subject.id}/`;
  if (secEyebrow && secTitle && secHint) {
    secEyebrow.textContent = "Study Material";
    if (level === "root") {
      secTitle.textContent = "Pick a category to study";
      secHint.textContent =
        "Each category opens its chapters — every JSON file inside the category folder appears automatically.";
    } else if (chapter) {
      secTitle.textContent = "Pick a part to start";
      secHint.innerHTML = `<a href="${esc(chapterBase)}">← All chapters</a>`;
    } else if (level === "category") {
      secTitle.textContent = "Pick a chapter to study";
      secHint.innerHTML =
        `Chapters appear automatically when a JSON file is added to <code>${esc(folderPath)}</code>.`;
    } else {
      secTitle.textContent = "Pick a chapter to study";
      secHint.textContent =
        "Chapters appear automatically when a JSON file is added to this subject folder.";
    }
  }
  if (filterEl && level === "root") {
    filterEl.placeholder = "Filter categories…";
    filterEl.setAttribute("aria-label", "Filter categories");
  } else if (filterEl && !chapter) {
    filterEl.placeholder = "Filter chapters…";
    filterEl.setAttribute("aria-label", "Filter chapters");
  }

  /* ------------------------------------------------------------- Practice -
   * Every subject has exactly two halves: Study Material above, and these
   * four doors below. This is wayfinding on the subject page — the quiz
   * engine, its routes and its internal labels are untouched, and a student
   * meets the same four options in the same order everywhere on the site. */
  const practiceGrid = document.getElementById("practiceGrid");
  if (practiceGrid) {
    const shown = level === "category" ? category.topics : subject.topics;
    const live = shown.filter((t) => t.available).length;
    const qs = shown.reduce((n, t) => n + (t.count || 0), 0);
    const doors = [
      {
        eyebrow: "1 · Learn then test",
        title: "Expected MCQs",
        body: live
          ? `${live} chapter set${live === 1 ? "" : "s"} ready in ${subject.name} — ${qs} question${qs === 1 ? "" : "s"}, each with its explanation.`
          : `Chapter-wise forecast sets for ${subject.name}, written from the syllabus and the recent pattern.`,
        href: "expected-mcqs.html",
      },
      {
        eyebrow: "2 · Under exam conditions",
        title: "Mock Tests",
        body: `Build a timed paper mixing ${subject.name} with the rest of the syllabus, then read every answer back.`,
        href: "mock.html",
      },
      {
        eyebrow: "3 · What the paper really asks",
        title: "Previous Year Questions",
        body: "Exam-wise old papers, year by year, with solved versions and official answer keys.",
        href: "pyq.html",
      },
      {
        eyebrow: "4 · Bring it back",
        title: "Revision Tests",
        body: `Re-attempt a ${subject.name} chapter cold, days after you studied it, before the facts fade.`,
        href: "revision.html",
      },
    ];
    practiceGrid.innerHTML = doors
      .map(
        (d) => `
    <a class="card card-pad" href="${d.href}">
      <span class="eyebrow">${esc(d.eyebrow)}</span>
      <h3>${esc(d.title)}</h3>
      <p class="text-sm muted">${esc(d.body)}</p>
      <p class="ilink">Open &rarr;</p>
    </a>`
      )
      .join("");
  }

  /* -------------------------------------------------------- Render helpers - */
  const showCategories = level === "root";

  function categoryCard(c, subOverride) {
    const n = c.topics.length;
    const q = c.topics.reduce((a, t) => a + t.count, 0);
    const sub =
      subOverride ||
      (!n
        ? "No MCQ sets yet — add a JSON file"
        : `${n} topic${n === 1 ? "" : "s"} · ${q} question${q === 1 ? "" : "s"} · Open →`);
    return `
    <a class="card quiz-card" href="subject?subject=${encodeURIComponent(subject.id)}&category=${encodeURIComponent(c.id)}">
      <span class="qc-icon">${c.icon || "📁"}</span>
      <span>
        <h3>${esc(c.name)}</h3>
        <span class="qc-sub">${sub}</span>
      </span>
      <span class="qc-go">→</span>
    </a>`;
  }

  /* A parent category that owns sub-categories: its own card first, then the
     children on the same card grid behind a rule that reads as nesting. */
  function groupBlock(g) {
    const parts = [];
    parts.push(`${g.kids.length} categor${g.kids.length === 1 ? "y" : "ies"}`);
    const n = g.parent.topics.length;
    if (n) {
      const q = g.parent.topics.reduce((a, t) => a + t.count, 0);
      parts.push(`${n} topic${n === 1 ? "" : "s"} · ${q} question${q === 1 ? "" : "s"}`);
    }
    parts.push("Open →");
    return `<div class="cat-group" role="group" aria-label="${esc(g.parent.name)}">
      ${categoryCard(g.parent, parts.join(" · "))}
      <div class="grid grid-3 cat-group-kids">
        ${g.kids.map((k) => categoryCard(k)).join("")}
      </div>
    </div>`;
  }

  /** Categories in configured order, with each group emitted where its parent sits. */
  function categoryMarkup(list) {
    const groups = resolveGroups(list);
    if (!groups.length) return list.map((c) => categoryCard(c)).join("");
    const byParent = new Map(groups.map((g) => [g.parent.id, g]));
    const grouped = new Set(groups.flatMap((g) => g.kids.map((k) => k.id)));
    return list
      .map((c) => {
        const g = byParent.get(c.id);
        if (g) return groupBlock(g);
        if (grouped.has(c.id)) return ""; // already rendered inside its parent
        return categoryCard(c);
      })
      .join("");
  }

  /** Categorized topics link with &category= (matches the sitemap canonical). */
  function topicHref(t) {
    const cat = t.category ? `&category=${encodeURIComponent(t.category)}` : "";
    return `quiz.html?subject=${encodeURIComponent(subject.id)}&topic=${encodeURIComponent(t.id)}${cat}`;
  }

  /** One chapter folder. A single-set chapter links straight to its quiz,
      as the Study shelf does — no folder page to click through. */
  function chapterCard(c) {
    const n = c.topics.length;
    const q = c.topics.reduce((a, t) => a + (t.count || 0), 0);
    const only = n === 1 ? c.topics[0] : null;
    if (only && !only.available) return topicCard(only, c.name);
    const href = only ? topicHref(only) : chapterHref(c);
    const bits = [];
    if (c.num) bits.push(`Chapter ${c.num}`);
    bits.push(only ? "1 set" : `${n} parts`);
    bits.push(`${q} question${q === 1 ? "" : "s"}`);
    bits.push(only ? "Start set →" : "Open →");
    return `
    <a class="card quiz-card" href="${esc(href)}">
      <span class="qc-icon">📂</span>
      <span>
        <h3>${esc(c.name)}${only ? HOA.langBadge(only.variants, { single: true }) : ""}</h3>
        <span class="qc-sub">${bits.join(" · ")}</span>
      </span>
      <span class="qc-go">→</span>
    </a>`;
  }

  /** Inside a chapter: "Part N" leads, the set's own subtitle follows. */
  function partCard(t) {
    const n = partOf(t);
    if (!n) return topicCard(t);
    const sub = String(t.name).replace(/\s*[-–:]\s*Part\s*\d+\s*$/i, "").trim();
    return topicCard(t, `Part ${n}`, sub);
  }

  function topicCard(t, heading, subtitle) {
    const clickable = t.available;
    const tag = clickable ? "a" : "div";
    const href = clickable ? topicHref(t) : "javascript:void(0)";
    return `
    <${tag} class="card quiz-card${clickable ? "" : " disabled"}" href="${href}"
       ${clickable ? "" : 'aria-disabled="true"'}>
      <span class="qc-icon">${icon}</span>
      <span>
        <h3>${esc(heading || t.name)}${HOA.langBadge(t.variants, { single: true })}</h3>
        <span class="qc-sub">${
          clickable
            ? `${subtitle ? `${esc(subtitle)} · ` : ""}${t.count} question${t.count === 1 ? "" : "s"} · Start set →`
            : `No questions available yet.`
        }</span>
      </span>
      <span class="qc-go">${clickable ? "→" : "⏳"}</span>
    </${tag}>`;
  }

  const noMatch = (what) =>
    `<div class="empty-state"><div class="es-icon">🔎</div>
      <h3>No ${what} matches “${esc(filterEl.value)}”</h3>
      <p>Try a different keyword.</p></div>`;

  function emptyTopics() {
    if (level === "category") {
      return `<div class="empty-state"><div class="es-icon">📂</div>
        <h3>No topics added yet.</h3>
        <p>Create a file like <code>${esc(folderPath)}your-topic.json</code>
        (copy <code>templates/topic-template.json</code>) and it will appear here automatically — no code changes.</p>
        <p class="mt-2"><a class="btn btn-soft" href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">Join Telegram for updates</a></p></div>`;
    }
    return `<div class="empty-state"><div class="es-icon">📂</div>
      <h3>No topics added yet.</h3>
      <p>Create a file like <code>questions/${esc(subject.id)}/your-topic.json</code>
      (copy <code>templates/topic-template.json</code>) and it will appear here automatically — no code changes.</p>
      <p class="mt-2"><a class="btn btn-soft" href="https://t.me/HouseOfAspirant" target="_blank" rel="noopener">Join Telegram for updates</a></p></div>`;
  }

  function render(list) {
    if (badCategory) {
      wrap.innerHTML = `<div class="empty-state"><div class="es-icon">🤔</div>
        <h3>Category not found</h3>
        <p><code>${esc(categoryId)}</code> is not a category of ${esc(subject.name)}.
        Pick one from the subject page.</p>
        <p class="mt-2"><a class="btn btn-primary" href="subject?subject=${encodeURIComponent(subject.id)}">Back to ${esc(subject.name)}</a></p></div>`;
      return;
    }
    if (showCategories) {
      wrap.innerHTML = list.length ? categoryMarkup(list) : noMatch("category");
      return;
    }
    const full = level === "category" ? category.topics : subject.topics;
    if (!full.length) {
      wrap.innerHTML = emptyTopics();
      return;
    }
    if (chapter) {
      wrap.innerHTML = list.length ? list.map(partCard).join("") : noMatch("part");
      return;
    }
    wrap.innerHTML = list.length ? list.map(chapterCard).join("") : noMatch("chapter");
  }

  const initial = showCategories ? categories : chapter ? chapter.topics : chapterList;
  render(initial);

  /* ------------------------------------------------- Instant filter (same) - */
  filterEl.addEventListener("input", () => {
    const term = filterEl.value.trim().toLowerCase();
    const match = (item) =>
      item.name.toLowerCase().includes(term) ||
      (item.description || "").toLowerCase().includes(term) ||
      // A chapter folder also matches on the sets inside it.
      (item.topics || []).some((t) => String(t.name).toLowerCase().includes(term));
    render(!term ? initial : initial.filter(match));
  });
})();
