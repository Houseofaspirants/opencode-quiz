/* ============================================================================
 * content.js | House of Aspirants Quiz Portal
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

  const links = Array.from(toc.querySelectorAll('a[href^="#"]'));
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
