/* ============================================================================
 * books.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Renders the Books shelf from data/books.json as a RECOMMENDATION LIST, not
 * a catalogue. A card carries exactly four things - cover, title, author and
 * the book's one-line `recommendation` - under a single "View on Amazon"
 * button. No price, no rating, no publisher, no difficulty, no language, no
 * "buy it if". The page exists to send a reader to the shop in one click.
 *
 * Two lists, both read from the payload:
 *
 *   1. `books`   one record per book: its cover, its `group` (the subject it
 *                files itself under), the `recommendation` line, `providers`
 *                and `search`, the pre-lowercased string the search box
 *                matches on (built by the engine from title, author, group,
 *                recommendation, keywords and the rest of the file).
 *
 *   2. `filters.group.rows`  the subject chips and their order, derived at
 *                build time from the books that exist. A new subject is a
 *                book carrying it - never an edit to this file, and never a
 *                hardcoded chip list.
 *
 * The CTA's href comes straight from the payload: the engine already pointed
 * it at the store and already merged the UTM parameters and the Associates
 * tag onto it, and it carries the `rel` read from config/affiliate-links.json.
 * It opens in a new tab, so there is no popup and no intermediate page - and
 * the URL itself is never printed as visible text.
 *
 * Loading books.html runs this; every other page ignores it.
 * ========================================================================== */
(() => {
  "use strict";
  const shelf = document.getElementById("bookShelf");
  const grid = document.getElementById("bookGrid");
  if (!shelf || !grid) return;

  const groupsEl = document.getElementById("bookGroups");
  const searchEl = document.getElementById("bookSearch");

  const esc = (s) =>
    String(s === null || s === undefined ? "" : s).replace(/[&<>"'/]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "/": "&#47;" }[c]));

  let books = [];
  let rows = [];   // subject groups, in the order the engine derived them
  let active = ""; // "" = every subject
  let term = "";

  const query = () => term.trim().toLowerCase();
  const matchesSearch = (b) =>
    !query() || String(b.search || "").indexOf(query()) !== -1;

  /** The one button on the card: the book's first available provider. */
  function cta(b) {
    const list = Array.isArray(b.providers) ? b.providers : [];
    const p = list[0];
    if (!p) {
      return '<span class="btn btn-primary book-cta" aria-disabled="true">'
           + "Currently unavailable</span>";
    }
    const attrs = p.external
      ? ` target="_blank" rel="${esc(p.rel || "sponsored noopener nofollow")}"`
        + ` data-affiliate data-book="${esc(b.id)}"`
        + ` data-provider="${esc(p.id)}"`
      : ' rel="noopener"';
    return `<a class="btn btn-primary book-cta" href="${esc(p.href)}"${attrs}>`
         + `${esc(p.label)}</a>`;
  }

  /** Large cover when one exists; the initials block until you drop one in. */
  function media(b) {
    const title = String(b.title || "");
    if (!b.cover) {
      return `<div class="book-cover" aria-hidden="true">`
           + `<span>${esc(title.slice(0, 2))}</span></div>`;
    }
    const dims = b.coverW && b.coverH
      ? ` width="${Number(b.coverW)}" height="${Number(b.coverH)}"` : "";
    return `<img class="book-card-cover" src="${esc(b.cover)}" `
         + `alt="${esc(title)} cover"${dims} loading="lazy" decoding="async">`;
  }

  function card(b) {
    const title = String(b.title || "");
    const rec = String(b.recommendation || "");
    return `
    <article class="card book-card">
      <div class="book-card-media">${media(b)}</div>
      <div class="book-card-body">
        <h3><a href="book-${esc(b.id)}.html">${esc(title)}</a></h3>
        <p class="book-card-author">${esc(b.author)}</p>
        ${rec ? `<p class="book-card-rec">${esc(rec)}</p>` : ""}
        ${cta(b)}
      </div>
    </article>`;
  }

  /** Counts per subject, so a chip that would land on nothing disappears. */
  function hitCounts() {
    const counts = new Map();
    let total = 0;
    for (const b of books) {
      if (!matchesSearch(b)) continue;
      total += 1;
      counts.set(b.group, (counts.get(b.group) || 0) + 1);
    }
    return { counts, total };
  }

  function renderChips(counts, total) {
    if (!groupsEl) return;
    const chips = [{ id: "", label: "All books", n: total }].concat(
      rows.map((r) => ({ id: r.id, label: r.label, n: counts.get(r.id) || 0 }))
    ).filter((r) => r.id === "" || r.n > 0);
    groupsEl.innerHTML = chips.map((r) =>
      `<button type="button" class="filter-chip" data-group="${esc(r.id)}"`
      + ` aria-pressed="${r.id === active}">${esc(r.label)} (${r.n})</button>`
    ).join("");
    groupsEl.hidden = chips.length <= 1;
  }

  function emptyState(what) {
    return `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div><h3>${what}</h3>
        <p>Try another keyword, or pick a different subject above.</p></div>`;
  }

  function apply() {
    const { counts, total } = hitCounts();
    renderChips(counts, total);

    const visible = books.filter(
      (b) => matchesSearch(b) && (!active || b.group === active));
    if (!visible.length) {
      const what = query();
      grid.className = "grid grid-3";
      grid.innerHTML = what
        ? emptyState(`No book matches “${esc(what)}”`)
        : emptyState("Nothing filed under this subject yet");
      return;
    }

    // One <section> per subject, in the engine's order: subjects with no
    // matching book are skipped rather than shown as an empty heading.
    const order = rows.map((r) => r.id).concat(
      [...new Set(visible.map((b) => b.group))].filter((g) => !rows.some((r) => r.id === g)));
    grid.className = "";
    grid.innerHTML = order.map((group) => {
      const inGroup = visible.filter((b) => b.group === group);
      if (!inGroup.length) return "";
      return `<section class="book-group">
          <h2 class="book-group-title">${esc(group)}</h2>
          <div class="grid grid-3">${inGroup.map(card).join("")}</div>
        </section>`;
    }).join("");
  }

  if (groupsEl) {
    groupsEl.addEventListener("click", (ev) => {
      const hit = /** @type {HTMLElement | null} */ (ev.target);
      const chip = hit && hit.closest ? hit.closest("[data-group]") : null;
      if (!chip) return;
      active = chip.getAttribute("data-group") || "";
      apply();
    });
  }

  if (searchEl) {
    searchEl.addEventListener("input", () => {
      term = /** @type {HTMLInputElement} */ (searchEl).value;
      apply();
    });
  }

  fetch("data/books.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      books = (data && data.books) || [];
      rows = (((data && data.filters) || {}).group || {}).rows || [];
      if (!books.length) {
        if (groupsEl) groupsEl.hidden = true;
        grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">📚</div><h3>The shelf is being stocked</h3>
        <p>Books are added one at a time. Until the first one lands, the free
           study material covers the syllabus.</p></div>`;
        return;
      }
      apply();
    })
    .catch(() => {
      if (groupsEl) groupsEl.hidden = true;
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">⚠️</div><h3>The shelf could not load</h3>
        <p>Refresh the page, or start with the free study material.</p></div>`;
    });
})();
