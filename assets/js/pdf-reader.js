// @ts-check
/* ============================================================================
 * pdf-reader.js | Read a PDF on the page instead of downloading it first
 * ----------------------------------------------------------------------------
 * Loaded on demand by content.js, only on pages that carry a reader:
 *
 *   <div class="pdf-reader" data-pdf-src="content/…/file.pdf">   inline reader
 *     <div class="pr-pages">…</div>                               (study, CA, PDF pages)
 *   </div>
 *   <button data-pdf-preview="content/…/file.pdf"                 modal reader
 *           data-pdf-title="2022 paper">                          (PYQ tables)
 *
 * PDF.js (cdnjs, the same build rank2.js uses) is fetched only when a reader
 * actually starts, and the PDF is read in ranges (disableAutoFetch), so a
 * reader who looks at page 1 never downloads the other 80 pages. Each page is
 * drawn only when it scrolls near the viewport.
 *
 * GA4 (through HOA.analytics.track, never throws):
 *   pdf_preview        a reader started   {file_name, mode, page}
 *   pdf_read_progress  25/50/75/100 % of pages seen, once each {file_name, percent}
 *   practice_click     a "Practice MCQs" link on a reading page {page}
 * pdf_download is already sent by core.js for every .pdf link.
 * ========================================================================== */
(() => {
  "use strict";

  const BASE = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/3.11.174/";
  /** @type {Promise<any> | null} */
  let libP = null;
  const loadLib = () => {
    if (!libP) {
      libP = new Promise((resolve, reject) => {
        const w = /** @type {any} */ (window);
        if (w.pdfjsLib) { resolve(w.pdfjsLib); return; }
        const s = document.createElement("script");
        s.src = `${BASE}pdf.min.js`;
        s.async = true;
        s.onload = () => {
          const lib = w.pdfjsLib;
          if (!lib) { reject(new Error("pdf.js did not register")); return; }
          lib.GlobalWorkerOptions.workerSrc = `${BASE}pdf.worker.min.js`;
          resolve(lib);
        };
        s.onerror = () => reject(new Error("pdf.js could not be downloaded"));
        document.head.appendChild(s);
      });
      libP.catch(() => { libP = null; });   // a network hiccup is retried next time
    }
    return libP;
  };

  const track = (name, params) => {
    try {
      const H = /** @type {any} */ (window).HOA;
      if (H && H.analytics && typeof H.analytics.track === "function") H.analytics.track(name, params);
    } catch { /* analytics never breaks reading */ }
  };

  const fileName = (src) => decodeURIComponent(String(src).split("/").pop() || String(src));
  const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c] || c));

  /**
   * Render a PDF into `box` (a .pr-pages element), page by page as it scrolls in.
   * @param {HTMLElement} box
   * @param {string} src
   * @param {string} mode
   * @param {HTMLElement | null} scroller  the scrolling element (modal) or null (page)
   */
  async function mount(box, src, mode, scroller) {
    box.innerHTML = '<p class="pr-msg">Opening the PDF…</p>';
    track("pdf_preview", { file_name: fileName(src), mode, page: location.pathname });
    let pdf;
    try {
      const lib = await loadLib();
      pdf = await lib.getDocument({
        url: src, disableAutoFetch: true, disableStream: true, rangeChunkSize: 262144,
      }).promise;
    } catch {
      box.innerHTML = `<p class="pr-msg">The reader could not open this file here. ` +
        `<a href="${esc(src)}" target="_blank" rel="noopener">Open the PDF in a new tab</a></p>`;
      return;
    }
    const total = pdf.numPages;
    const first = await pdf.getPage(1);
    const vp1 = first.getViewport({ scale: 1 });
    const ratio = vp1.height / vp1.width;

    box.innerHTML = "";
    const frag = document.createDocumentFragment();
    for (let n = 1; n <= total; n++) {
      const d = document.createElement("div");
      d.className = "pr-page";
      d.dataset.n = String(n);
      d.style.aspectRatio = `1 / ${ratio.toFixed(4)}`;
      d.innerHTML = `<span class="pr-num">${n} / ${total}</span>`;
      frag.appendChild(d);
    }
    box.appendChild(frag);

    const seen = new Set();
    const sent = new Set();
    const progress = (n) => {
      seen.add(n);
      const pct = Math.floor((seen.size / total) * 100);
      for (const mark of [25, 50, 75, 100]) {
        if (pct >= mark && !sent.has(mark)) {
          sent.add(mark);
          track("pdf_read_progress", { file_name: fileName(src), percent: mark });
        }
      }
    };

    /** @param {HTMLElement} el */
    const draw = async (el) => {
      if (el.dataset.drawn) return;
      el.dataset.drawn = "1";
      const n = Number(el.dataset.n);
      try {
        const page = n === 1 ? first : await pdf.getPage(n);
        const width = el.clientWidth || box.clientWidth || 600;
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        const scale = (width / page.getViewport({ scale: 1 }).width) * dpr;
        const vp = page.getViewport({ scale });
        const cv = document.createElement("canvas");
        cv.width = Math.floor(vp.width);
        cv.height = Math.floor(vp.height);
        cv.setAttribute("aria-label", `Page ${n} of ${total}`);
        const ctx = cv.getContext("2d");
        if (!ctx) return;
        await page.render({ canvasContext: ctx, viewport: vp }).promise;
        el.prepend(cv);
      } catch {
        delete el.dataset.drawn;     // try again when it scrolls back in
      }
    };

    const pages = /** @type {HTMLElement[]} */ (Array.from(box.querySelectorAll(".pr-page")));
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((entries) => {
        for (const e of entries) {
          if (e.isIntersecting) draw(/** @type {HTMLElement} */ (e.target));
        }
      }, { root: scroller, rootMargin: "800px 0px" });
      pages.forEach((p) => io.observe(p));
      // Progress counts a page once half of it has really been on screen,
      // not when it was drawn ahead of time.
      const seenIO = new IntersectionObserver((entries) => {
        for (const e of entries) {
          if (e.isIntersecting) { progress(Number(/** @type {HTMLElement} */ (e.target).dataset.n)); seenIO.unobserve(e.target); }
        }
      }, { root: scroller, threshold: 0.5 });
      pages.forEach((p) => seenIO.observe(p));
    } else {
      pages.slice(0, 5).forEach(draw);
    }
  }

  /* ---------------------------------------------------- inline readers -- */
  const readers = /** @type {HTMLElement[]} */ (Array.from(document.querySelectorAll(".pdf-reader[data-pdf-src]")));
  readers.forEach((r) => {
    const box = /** @type {HTMLElement | null} */ (r.querySelector(".pr-pages"));
    const src = r.getAttribute("data-pdf-src") || "";
    if (!box || !src) return;
    let started = false;
    const start = () => {
      if (started) return;
      started = true;
      const art = r.closest("article");
      if (art) art.classList.add("pr-on");     // the cover image steps aside
      mount(box, src, "inline", null);
    };
    // Starts by itself as the reader nears the screen, or at once from the
    // hero's "Read Online" button / the reader's own start button.
    if ("IntersectionObserver" in window) {
      const io = new IntersectionObserver((es) => {
        if (es.some((e) => e.isIntersecting)) { io.disconnect(); start(); }
      }, { rootMargin: "300px 0px" });
      io.observe(r);
    }
    document.addEventListener("click", (ev) => {
      const t = /** @type {HTMLElement | null} */ (ev.target);
      if (t && t.closest && t.closest("[data-pdf-open]")) start();
    });
  });

  /* ------------------------------------------------------ modal reader -- */
  /** @type {HTMLElement | null} */
  let lastFocus = null;
  const close = () => {
    const m = document.querySelector(".pr-modal");
    if (m) m.remove();
    document.documentElement.classList.remove("pr-lock");
    if (lastFocus) lastFocus.focus();
  };
  const openModal = (src, title) => {
    close();
    lastFocus = /** @type {HTMLElement | null} */ (document.activeElement);
    const m = document.createElement("div");
    m.className = "pr-modal";
    m.setAttribute("role", "dialog");
    m.setAttribute("aria-modal", "true");
    m.setAttribute("aria-label", title || "PDF reader");
    m.innerHTML = `<div class="pdf-reader">
        <div class="pr-head"><span class="pr-label">📖 ${esc(title || fileName(src))}</span>
          <span class="pr-tools"><a class="pr-dl" href="${esc(src)}" download>⬇ Download</a>
          <button type="button" class="pr-x" aria-label="Close reader">✕</button></span></div>
        <div class="pr-pages"></div></div>`;
    document.body.appendChild(m);
    document.documentElement.classList.add("pr-lock");
    const x = /** @type {HTMLElement | null} */ (m.querySelector(".pr-x"));
    if (x) x.focus();
    const box = /** @type {HTMLElement} */ (m.querySelector(".pr-pages"));
    mount(box, src, "modal", box);
  };
  document.addEventListener("click", (ev) => {
    const t = /** @type {HTMLElement | null} */ (ev.target);
    if (!t || !t.closest) return;
    const p = t.closest("[data-pdf-preview]");
    if (p) {
      ev.preventDefault();
      openModal(p.getAttribute("data-pdf-preview") || "", p.getAttribute("data-pdf-title") || "");
      return;
    }
    if (t.closest(".pr-x") || t.classList.contains("pr-modal")) { close(); return; }
    if (t.closest("[data-practice-link]")) track("practice_click", { page: location.pathname });
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && document.querySelector(".pr-modal")) close();
  });
})();
