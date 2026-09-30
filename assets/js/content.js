/* ============================================================================
 * content.js | House of Aspirants - Free Competitive Exam Learning Platform
 * ----------------------------------------------------------------------------
 * Behaviour for the Markdown-generated pages (notes, magazine, strategy,
 * sessions, recruitment): copy-link sharing and a table-of-contents
 * scrollspy.
 *
 * Deliberately tiny and dependency-free:
 *   • Share buttons are plain <a> links, so WhatsApp / Telegram / X sharing
 *     already works without JavaScript - this file only adds "Copy link".
 *   • No third-party SDK is ever loaded; nothing here runs before paint.
 *
 * Loaded (defer) after core.js on every generated page.
 * ========================================================================== */
(() => {
  "use strict";

  const toast = (msg) => {
    if (window.HOA && typeof HOA.toast === "function") HOA.toast(msg);
  };

  const fallbackCopy = (text) => {
    try {
      const ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.style.position = "fixed";
      ta.style.opacity = "0";
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      return false;
    }
  };

  /* ------------------------------------------------- copy the page link -- */
  document.addEventListener("click", (e) => {
    const btn = e.target.closest('[data-share="copy"]');
    if (!btn) return;
    e.preventDefault();
    const row = btn.closest("[data-share-url]");
    const url = (row && row.dataset.shareUrl) || location.href;
    const done = () => {
      toast("Link copied");
      const label = btn.textContent;
      btn.textContent = "✓ Copied";
      setTimeout(() => { btn.textContent = label; }, 1800);
    };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(done).catch(() => {
        if (fallbackCopy(url)) done();
        else toast("Copy failed - select the address bar instead");
      });
    } else if (fallbackCopy(url)) {
      done();
    } else {
      toast("Copy failed - select the address bar instead");
    }
  });

  /* ------------------------------------------------- TOC scrollspy ------- */
  /* Highlights the section currently under the reading position. Pure
     enhancement: the anchors jump correctly with this file blocked. */
  const toc = document.querySelector(".doc-toc");
  if (!toc || !("IntersectionObserver" in window)) return;

  // English pages use fragment links (#section); the Punjabi edition publishes
  // under /pa/ with <base href="/">, so its anchors carry the full page URL.
  // Both spellings resolve through `a.hash`.
  const links = Array.from(toc.querySelectorAll("a[href]"));
  const targets = links
    .map((a) => document.getElementById(decodeURIComponent(a.hash.slice(1))))
    .filter(Boolean);
  if (!targets.length) return;

  const setActive = (id) => {
    links.forEach((a) => {
      a.classList.toggle("is-active", decodeURIComponent(a.hash.slice(1)) === id);
    });
  };

  const visible = new Set();
  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((en) => {
        if (en.isIntersecting) visible.add(en.target.id);
        else visible.delete(en.target.id);
      });
      const first = targets.find((t) => visible.has(t.id));
      if (first) setActive(first.id);
    },
    { rootMargin: "-15% 0px -70% 0px", threshold: 0 }
  );
  targets.forEach((t) => io.observe(t));
  setActive(targets[0].id);
})();

/* ============================================================================
 * List filters (Phase 4)
 * ----------------------------------------------------------------------------
 * The chip bar above every listing that has something to filter. Each chip is
 * a plain <button> with aria-pressed, the rows carry their facet values as
 * data-f-* attributes, and everything runs locally on the DOM that already
 * shipped - no fetch, no layout thrash, no request.
 *
 * Selection is OR inside a facet (Punjab Police OR PSSSB) and AND across
 * facets (Punjab Police AND English), which is how an aspirant actually narrows
 * a list.
 * ========================================================================== */
(() => {
  "use strict";
  const bar = document.querySelector("[data-filter-bar]");
  const list = document.querySelector("[data-filter-list]");
  if (!bar || !list) return;

  const rows = Array.from(list.children).filter((el) =>
    Array.from(el.attributes).some((a) => a.name.startsWith("data-f-"))
  );
  if (!rows.length) return;

  const chips = Array.from(bar.querySelectorAll("[data-filter-facet]"));
  const reset = bar.querySelector("[data-filter-reset]");
  const count = bar.querySelector("[data-filter-count]");
  const active = Object.create(null);
  const total = rows.length;

  const apply = () => {
    let shown = 0;
    for (const row of rows) {
      let ok = true;
      for (const facet of Object.keys(active)) {
        const chosen = active[facet];
        if (!chosen || !chosen.size) continue;
        const have = new Set(
          (row.getAttribute("data-f-" + facet) || "")
            .split(/\s+/)
            .filter(Boolean)
        );
        let hit = false;
        for (const v of chosen) if (have.has(v)) { hit = true; break; }
        if (!hit) { ok = false; break; }
      }
      row.classList.toggle("is-filtered-out", !ok);
      if (ok) shown += 1;
    }
    if (count) {
      count.textContent =
        shown === total ? total + " shown" : shown + " of " + total + " shown";
      count.classList.toggle("is-muted", shown === total);
    }
    if (reset) reset.hidden = !chips.some((c) => c.getAttribute("aria-pressed") === "true");
  };

  bar.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-filter-facet]");
    if (chip) {
      const facet = chip.getAttribute("data-filter-facet");
      const value = chip.getAttribute("data-filter-value");
      const chosen = active[facet] || (active[facet] = new Set());
      if (chosen.has(value)) chosen.delete(value);
      else chosen.add(value);
      chip.setAttribute("aria-pressed", chosen.has(value) ? "true" : "false");
      apply();
      return;
    }
    if (e.target.closest("[data-filter-reset]")) {
      for (const facet of Object.keys(active)) active[facet].clear();
      chips.forEach((c) => c.setAttribute("aria-pressed", "false"));
      apply();
    }
  });

  apply();
})();

/* ============================================================================
 * search.html - results over the same corpus as the Ctrl+K overlay
 * ----------------------------------------------------------------------------
 * The GET form works with JavaScript off (the query rides in ?q=). This only
 * fills the results box, after paint, with one lazy fetch - first paint never
 * waits for it.
 * ========================================================================== */
(() => {
  "use strict";
  const box = document.querySelector("[data-search-results]");
  if (!box) return;
  const input = document.getElementById("search-q");
  const q = new URLSearchParams(location.search).get("q") || "";
  const term = q.trim();
  if (input) input.value = q;
  if (!term) return;

  const esc = (s) =>
    String(s == null ? "" : s).replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
    );
  const LABEL = {
    notes: "Study note", "current-affairs": "Current affairs",
    magazine: "Magazine issue", strategy: "Strategy", sessions: "Live session",
    recruitment: "Recruitment", blogs: "Blog", news: "News",
    announcements: "Announcement", "personal-notes": "Personal note",
    "subject-guides": "Subject guide", "topic-guides": "Topic guide",
    "daily-practice": "Daily practice", "success-stories": "Success story",
    "book-recommendations": "Book recommendation", guide: "Study guide",
    exam: "Exam",
  };

  /* Structural destinations come from HOA.searchEntries(), the same builder
     the Ctrl+K overlay uses. Before this, search.html only ever searched the
     document corpus, so the platform's own subjects, chapters and sections
     were invisible here — typing "General Knowledge" or "Mock Tests" found
     nothing. `topic` reads as Expected MCQs because that is what a set is. */
  const KIND = {
    subject: "Subject", category: "Category", topic: "Expected MCQs",
    hub: "Section", book: "Book",
  };

  box.innerHTML = '<p class="search-meta">Searching…</p>';
  const toks = term.toLowerCase().split(/\s+/).filter(Boolean);
  const every = (hay) => toks.every((t) => hay.includes(t));
  const corpusReq = fetch("data/search-index.json")
    .then((r) => (r.ok ? r.json() : { items: [] }))
    .catch(() => ({ items: [] }));
  const entriesReq =
    window.HOA && typeof window.HOA.searchEntries === "function"
      ? window.HOA.searchEntries()
      : Promise.resolve([]);

  Promise.all([corpusReq, entriesReq])
    .then(([data, entries]) => {
      /* Destinations rank first: when a student types the exact name of a
         subject or a section, that is what they meant, and a document that
         merely mentions it is a lesser answer. A row may carry its own
         `hay` (the books do, so an author or a publisher finds them) and
         falls back to its label exactly as it always has. */
      const dest = entries
        .filter((e) => every(String(e.hay || e.label || "").toLowerCase()))
        .map((e) => ({
          href: e.href,
          eyebrow:
            (KIND[e.type] || "Section") +
            (e.type === "topic" && e.count ? " · " + e.count + " Q" : ""),
          title: e.label,
          desc: e.sub || "",
        }));

      /* Weighted exactly as the overlay is: every word of the query must land
         somewhere, and a title hit outranks a word buried in a body
         paragraph — so both surfaces also agree on the order. */
      const docs = (data.items || [])
        .map((row) => {
          const hay = {
            title: String(row.t || "").toLowerCase(),
            fields: [(row.g || []).join(" "), (row.s || []).join(" "),
                     (row.e || []).join(" "), row.c || "",
                     (row.w || []).join(" "), row.a || "", row.f || ""]
              .join(" ").toLowerCase(),
            desc: (String(row.d || "") + " " + String(row.m || "")).toLowerCase(),
            body: String(row.b || "").toLowerCase(),
          };
          let s = 0;
          for (const tk of toks) {
            let t = 0;
            if (hay.title.includes(tk)) t = 6;
            else if (hay.fields.includes(tk)) t = 4;
            else if (hay.desc.includes(tk)) t = 2;
            else if (hay.body.includes(tk)) t = 1;
            if (!t) { s = 0; break; }
            s += t;
          }
          return s ? { row, s } : null;
        })
        .filter(Boolean)
        .sort((a, b) => b.s - a.s || String(a.row.t).localeCompare(String(b.row.t)))
        .map((x) => x.row);

      if (!dest.length && !docs.length) {
        box.innerHTML =
          '<div class="empty-state"><span class="es-icon" aria-hidden="true">🔎</span>' +
          "<h3>No match for &ldquo;" + esc(term) + "&rdquo;</h3>" +
          "<p>Try a subject (Punjab GK), an exam (Punjab Police) or a tag " +
          "(current affairs) - subjects, chapters, sections and the document " +
          "corpus are all searched by title, summary, keywords, subject, " +
          "category, author and body.</p></div>";
        return;
      }
      box.innerHTML =
        '<p class="search-meta">' + (dest.length + docs.length) +
        " result(s) for &ldquo;" + esc(term) + "&rdquo;</p>" +
        '<div class="grid grid-3">' +
        dest.map((r) =>
          '<a class="card card-pad" href="' + esc(r.href) + '">' +
          '<span class="eyebrow">' + esc(r.eyebrow) + "</span>" +
          "<h3>" + esc(r.title) + "</h3>" +
          '<p class="muted">' + esc(r.desc) + "</p>" +
          '<p class="ilink">Open →</p></a>'
        ).join("") +
        docs.slice(0, 60).map((row) => {
          const href = String(row.u || "").replace(/^\//, "");
          return (
            '<a class="card card-pad" href="' + esc(href) + '">' +
            '<span class="eyebrow">' + esc(LABEL[row.k] || "Document") +
            (row.a ? " · " + esc(row.a) : "") + "</span>" +
            "<h3>" + esc(row.t || "") + "</h3>" +
            '<p class="muted">' + esc(row.d || "") + "</p>" +
            '<p class="ilink">Read →</p></a>'
          );
        }).join("") +
        "</div>";
    })
    .catch(() => {
      box.innerHTML =
        '<p class="search-meta">The search index could not be loaded - ' +
        'use the archives to browse everything published.</p>';
    });
})();
