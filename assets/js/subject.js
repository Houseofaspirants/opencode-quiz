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
  const idx = await HOA.loadIndex();
  const siteBase = String((idx.site && idx.site.url) || "").replace(/\/+$/, "");
  const subject = (idx.subjects || []).find((s) => s.id === subjectId);

  const wrap = document.getElementById("topicGrid");
  const titleEl = document.getElementById("subjectTitle");
  const crumbSubject = document.getElementById("crumbSubject");
  const crumbSubjectLink = document.getElementById("crumbSubjectLink");
  const crumbSep = document.getElementById("crumbSep");
  const crumbCategory = document.getElementById("crumbCategory");
  const descEl = document.getElementById("subjectDesc");
  const filterEl = document.getElementById("topicFilter");
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
    wrap.innerHTML = `<div class="empty-state"><div class="es-icon">🤔</div>
      <h3>Unknown subject</h3>
      <p>This subject is not in your configuration. Check <code>data/subjects.json</code> or the folder name inside <code>questions/</code>.</p>
      <p class="mt-2"><a class="btn btn-primary" href="index.html">Back to Home</a></p></div>`;
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

  /* ------------------------------------------------- SEO + page header ----- */
  let canonical = `${siteBase}/subject?subject=${encodeURIComponent(subject.id)}`;
  let docTitle = `${subject.name} Quiz - House of Aspirants`;
  let h1 = subject.name;
  let desc = subject.description || "Topic-wise MCQ practice.";
  let icon = subject.icon;

  if (level === "category") {
    canonical += `&category=${encodeURIComponent(category.id)}`;
    docTitle = `${category.name} - ${subject.name} Quiz - House of Aspirants`;
    h1 = category.name;
    desc = `All ${category.name} quizzes inside ${subject.name} — every topic in the folder is detected automatically.`;
    icon = category.icon || subject.icon;
  }
  HOA.seo({
    title: docTitle,
    canonical,
    robots: badCategory ? "noindex, nofollow" : "index, follow",
    ogTitle: docTitle,
    ogDescription: desc,
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
      crumbSubjectLink.href = `subject.html?subject=${encodeURIComponent(subject.id)}`;
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

  /* ----------------------------------------------------------------- Stats -
   * At the category level the counts scope down to that category; a
   * hierarchical subject root shows how many CATEGORIES it has. */
  const topicList = level === "category" ? category.topics : subject.topics;
  if (countTopics && countTopicsLabel) {
    countTopics.textContent = level === "root" ? categories.length : topicList.length;
    countTopicsLabel.textContent = level === "root" ? "Categories" : "Topics";
  }
  if (countQuizzes) countQuizzes.textContent = topicList.filter((t) => t.available).length;
  if (countQuestions) countQuestions.textContent = topicList.reduce((n, t) => n + t.count, 0);

  /* --------------------------------------------------------- Section head -- */
  const folderPath =
    level === "category"
      ? `questions/${subject.id}/${category.folder || category.id}/`
      : `questions/${subject.id}/`;
  if (secEyebrow && secTitle && secHint) {
    if (level === "root") {
      secEyebrow.textContent = "Categories";
      secTitle.textContent = "Pick a category to start";
      secHint.textContent =
        "Each category opens its quiz topics — every JSON file inside the category folder appears automatically.";
    } else if (level === "category") {
      secEyebrow.textContent = "Topics";
      secTitle.textContent = "Pick a topic to start";
      secHint.innerHTML =
        `Topics appear automatically when a JSON file is added to <code>${esc(folderPath)}</code>.`;
    } else {
      secEyebrow.textContent = "Topics";
      secTitle.textContent = "Pick a topic to start";
      secHint.textContent =
        "Topics appear automatically when a JSON file is added to this subject folder.";
    }
  }
  if (filterEl && level === "root") {
    filterEl.placeholder = "Filter categories…";
    filterEl.setAttribute("aria-label", "Filter categories");
  }

  /* -------------------------------------------------------- Render helpers - */
  const showCategories = level === "root";

  function categoryCard(c) {
    const n = c.topics.length;
    const q = c.topics.reduce((a, t) => a + t.count, 0);
    const sub = !n
      ? "No quizzes yet — add a JSON file"
      : `${n} topic${n === 1 ? "" : "s"} · ${q} question${q === 1 ? "" : "s"} · Open →`;
    return `
    <a class="card quiz-card" href="subject.html?subject=${encodeURIComponent(subject.id)}&category=${encodeURIComponent(c.id)}">
      <span class="qc-icon">${c.icon || "📁"}</span>
      <span>
        <h4>${esc(c.name)}</h4>
        <span class="qc-sub">${sub}</span>
      </span>
      <span class="qc-go">→</span>
    </a>`;
  }

  /** Categorized topics link with &category= (matches the sitemap canonical). */
  function topicHref(t) {
    const cat = t.category ? `&category=${encodeURIComponent(t.category)}` : "";
    return `quiz.html?subject=${encodeURIComponent(subject.id)}&topic=${encodeURIComponent(t.id)}${cat}`;
  }

  function topicCard(t) {
    const clickable = t.available;
    const tag = clickable ? "a" : "div";
    const href = clickable ? topicHref(t) : "javascript:void(0)";
    return `
    <${tag} class="card quiz-card${clickable ? "" : " disabled"}" href="${href}"
       ${clickable ? "" : 'aria-disabled="true"'}>
      <span class="qc-icon">${icon}</span>
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
        <p class="mt-2"><a class="btn btn-primary" href="subject.html?subject=${encodeURIComponent(subject.id)}">Back to ${esc(subject.name)}</a></p></div>`;
      return;
    }
    if (showCategories) {
      wrap.innerHTML = list.length ? list.map(categoryCard).join("") : noMatch("category");
      return;
    }
    const full = level === "category" ? category.topics : subject.topics;
    if (!full.length) {
      wrap.innerHTML = emptyTopics();
      return;
    }
    wrap.innerHTML = list.length ? list.map(topicCard).join("") : noMatch("topic");
  }

  const initial = showCategories ? categories : topicList;
  render(initial);

  /* ------------------------------------------------- Instant filter (same) - */
  filterEl.addEventListener("input", () => {
    const term = filterEl.value.trim().toLowerCase();
    const match = (item) =>
      item.name.toLowerCase().includes(term) ||
      (item.description || "").toLowerCase().includes(term);
    render(!term ? initial : initial.filter(match));
  });
})();
