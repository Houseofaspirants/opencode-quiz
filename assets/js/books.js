/* ============================================================================
 * books.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Renders the Books shelf from data/books.json.
 *
 * Everything this file draws comes from that payload:
 *   - `books`   one record per book: the card's copy, its cover, its providers
 *               and `search`, the pre-lowercased string the search box matches
 *               on (built by the engine from title, author, publisher, subject,
 *               keywords, topics, exams, language, difficulty and edition).
 *   - `filters` the filter dimensions. Each one carries its label, the record
 *               field it reads, how a chip applies to that field (`any` the
 *               value is in the list, `is` the field equals it, `flag` the
 *               field is truthy, `min` the number is at least it) and the rows
 *               that actually exist.
 *
 * So a new exam, subject, publisher, language or book is a content file plus a
 * rebuild: no markup edit, no JS edit, no hardcoded label anywhere in here.
 *
 * Outbound buttons are NOT constructed from a link. Every one reads a `href`
 * the engine already routed through the tracked /go/ hop, carrying the `rel`
 * from config/affiliate-links.json - the only place a destination may live.
 *
 * Loading books.html runs this; every other page ignores it.
 * ========================================================================== */
(() => {
  "use strict";
  const grid = document.getElementById("bookGrid");
  if (!grid) return;

  const searchEl = document.getElementById("bookSearch");
  const bar = document.getElementById("bookFilters");
  const facetGroup = bar && bar.querySelector("[data-facets]");
  const valueGroup = bar && bar.querySelector("[data-values]");
  const facetName = bar && bar.querySelector("[data-facet-name]");
  const countEl = bar && bar.querySelector("[data-filter-count]");
  const resetEl = bar && bar.querySelector("[data-filter-reset]");

  const esc = (s) =>
    String(s === null || s === undefined ? "" : s).replace(/[&<>"'/]/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
        "/": "&#47;" }[c]));

  /** ★ full, a dimmed ★ for a half, ☆ for the rest - no library, no images. */
  function stars(rating) {
    const r = Number(rating) || 0;
    const full = Math.floor(r);
    const half = r - full >= 0.5;
    const rest = Math.max(0, 5 - full - (half ? 1 : 0));
    return "★".repeat(full) + (half ? '<span class="star-half">★</span>' : "")
      + "☆".repeat(rest);
  }

  let books = [];
  let filters = {};
  let order = [];
  let facet = "";      // which dimension row 2 is showing
  let value = "";      // the one selected value; "" means everything
  let term = "";

  const spec = () => (facet in filters ? filters[facet] : null);

  /** Does this record satisfy one chip of one dimension? Generic on purpose. */
  function matches(book, f, id) {
    if (!f) return true;
    const raw = book[f.field];
    if (f.match === "flag") return !!raw;
    if (f.match === "min") return Number(raw || 0) >= Number(id);
    if (f.match === "any") {
      const list = Array.isArray(raw) ? raw : raw === null || raw === undefined ? [] : [raw];
      return list.some((v) => String(v) === id);
    }
    return String(raw === null || raw === undefined ? "" : raw) === id;
  }

  const matchesSearch = (book) => {
    const q = term.trim().toLowerCase();
    return !q || String(book.search || "").indexOf(q) !== -1;
  };

  const visible = () => {
    const f = spec();
    return books.filter((b) => (!value || matches(b, f, value)) && matchesSearch(b));
  };

  function providerButtons(b) {
    const list = Array.isArray(b.providers) ? b.providers : [];
    const out = list.filter((p) => p && p.external).map((p) =>
      `<a class="btn btn-soft" href="${esc(p.href)}" target="_blank" rel="${esc(p.rel || "sponsored noopener nofollow")}" data-affiliate data-book="${esc(b.id)}" data-provider="${esc(p.id)}">${esc(p.label)} →</a>`);
    for (const p of list.filter((x) => x && !x.external)) {
      out.push(`<a class="btn btn-soft" href="${esc(p.href)}">${esc(p.label)} →</a>`);
    }
    if (!out.length) out.push('<span class="btn btn-soft">Currently unavailable</span>');
    return `<p class="btn-row mt-2" style="margin-bottom:0">
        <a class="btn" href="book-${esc(b.id)}.html">Read the review →</a>${out.join("")}
      </p>`;
  }

  function card(b) {
    const title = String(b.title || "");
    const cover = b.cover
      ? `<img class="book-card-cover" src="${esc(b.cover)}" alt="${esc(title)} cover"`
        + (b.coverW && b.coverH
           ? ` width="${Number(b.coverW)}" height="${Number(b.coverH)}"` : "")
        + ' loading="lazy" decoding="async">'
      : `<div class="book-cover" aria-hidden="true"><span>${esc(title.slice(0, 2))}</span></div>`;
    const languages = (b.languages || []).join(" · ");
    const exams = (b.examLabels || []).join(" · ");

    return `
    <article class="card card-pad book-card">
      ${cover}
      <span class="eyebrow">${esc(b.subjectLabel || b.subject)} · ${esc(b.difficulty || "")}</span>
      <h3><a href="book-${esc(b.id)}.html">${esc(title)}</a></h3>
      <p class="text-sm muted">${esc(b.author)} · ${esc(b.publisher)}</p>
      <p class="book-rating text-sm" aria-label="Rated ${esc(b.rating)} out of 5">
        <span aria-hidden="true">${stars(b.rating)}</span> <strong>${esc(b.rating)}</strong>
      </p>
      <p class="text-sm">${esc(b.description)}</p>
      <ul class="book-meta text-sm muted">
        <li><span>Edition</span> ${esc(b.edition)}</li>
        <li><span>Language</span> ${esc(languages)}</li>
        <li><span>Exams</span> ${esc(exams)}</li>
        <li><span>Best for</span> ${esc(b.bestFor)}</li>
      </ul>
      <p class="text-sm"><strong>Buy it if:</strong> ${esc(b.buyIf)}</p>
      <p class="text-sm"><strong>Skip it if:</strong> ${esc(b.avoidIf)}</p>
      <p class="text-sm muted"><strong>How to use it:</strong> ${esc(b.howToUse)}</p>
      ${providerButtons(b)}
    </article>`;
  }

  function renderFacets() {
    if (!facetGroup) return;
    facetGroup.innerHTML = order
      .filter((k) => (filters[k].rows || []).length)
      .map((k) => `<button type="button" class="filter-chip" data-facet="${esc(k)}" aria-pressed="${k === facet}">${esc(filters[k].label)}</button>`)
      .join("");
  }

  function renderValues() {
    const f = spec();
    if (facetName) facetName.textContent = f ? f.label : "";
    if (valueGroup && f) {
      const rows = [{ id: "", label: "All books",
                      count: books.filter(matchesSearch).length }].concat(
        (f.rows || []).map((r) => ({
          id: String(r.id),
          label: r.label,
          count: books.filter((b) => matches(b, f, String(r.id)) && matchesSearch(b)).length,
        })));
      valueGroup.innerHTML = rows.map((r) =>
        `<button type="button" class="filter-chip" data-value="${esc(r.id)}" aria-pressed="${String(r.id) === value}">${esc(r.label)} (${r.count})</button>`).join("");
    }
    if (resetEl) resetEl.hidden = !value;
  }

  function renderCount(shown) {
    if (!countEl) return;
    const filtered = !!value || !!term.trim();
    countEl.textContent = filtered
      ? `${shown} of ${books.length} books`
      : `${books.length} books`;
    countEl.classList.toggle("is-muted", !filtered);
  }

  function apply() {
    const list = visible();
    renderCount(list.length);
    if (!list.length) {
      const what = term.trim();
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">🔎</div>
        <h3>No book matches ${what ? `“${esc(what)}”` : "this filter"}</h3>
        <p>Try another keyword, or clear the filter.</p></div>`;
      return;
    }
    grid.innerHTML = list.map(card).join("");
  }

  if (bar) {
    bar.addEventListener("click", (ev) => {
      const hit = /** @type {HTMLElement | null} */ (ev.target);
      const fBtn = hit && hit.closest ? hit.closest("[data-facet]") : null;
      if (fBtn) {
        const next = fBtn.getAttribute("data-facet") || "";
        if (next !== facet) {
          facet = next;
          value = "";          // a chip belongs to one dimension at a time
          renderFacets();
          renderValues();
          apply();
        }
        return;
      }
      const vBtn = hit && hit.closest ? hit.closest("[data-value]") : null;
      if (vBtn) {
        value = vBtn.getAttribute("data-value") || "";
        renderValues();
        apply();
        return;
      }
      const reset = hit && hit.closest ? hit.closest("[data-filter-reset]") : null;
      if (reset && value) {
        value = "";
        renderValues();
        apply();
      }
    });
  }

  if (searchEl) {
    searchEl.addEventListener("input", () => {
      term = /** @type {HTMLInputElement} */ (searchEl).value;
      renderValues();
      apply();
    });
  }

  fetch("data/books.json", { cache: "no-cache" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      books = (data && data.books) || [];
      filters = (data && data.filters) || {};
      order = Object.keys(filters);
      if (!books.length) {
        if (bar) bar.hidden = true;
        grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">📚</div>
        <h3>The shelf is being stocked</h3>
        <p>Books are added one at a time, with a note on who each one suits.
           Until the first note lands, the free study material covers the syllabus.</p></div>`;
        return;
      }
      // the exam dimension opens by default; a payload without one just opens
      // the first dimension it does carry.
      facet = (filters.exam && (filters.exam.rows || []).length ? "exam" : "")
        || order.find((k) => (filters[k].rows || []).length)
        || "";
      renderFacets();
      renderValues();
      apply();
    })
    .catch(() => {
      if (bar) bar.hidden = true;
      grid.innerHTML = `<div class="empty-state" style="grid-column:1/-1">
        <div class="es-icon">⚠️</div>
        <h3>The shelf could not load</h3>
        <p>Refresh the page, or start with the free study material.</p></div>`;
    });
})();
